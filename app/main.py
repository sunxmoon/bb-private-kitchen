import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import models
from .csrf import CSRF_COOKIE_NAME, generate_csrf_token
from .database import engine
from .dependencies import templates
from .routers import admin, auth, dishes, history, orders, recipes
from .security import is_production


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _migrate_background_to_theme(engine):
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    if "users" in insp.get_table_names():
        columns = {c["name"] for c in insp.get_columns("users")}
        if "background_image_url" in columns and "theme_color" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN theme_color VARCHAR(20) DEFAULT '#f97316'"))
                conn.execute(text("ALTER TABLE users DROP COLUMN background_image_url"))


def _migrate_add_role_column(engine):
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    if "users" not in insp.get_table_names():
        return
    columns = {c["name"] for c in insp.get_columns("users")}
    if "role" not in columns:
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'user' NOT NULL"
            ))
            conn.execute(text(
                "UPDATE users SET role = 'admin' WHERE id = (SELECT MIN(id) FROM users)"
            ))
        logger.info("Migration: added role column, first user set as admin")


def _migrate_add_indexes(engine):
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    if "orders" in insp.get_table_names():
        idx_names = {i["name"] for i in insp.get_indexes("orders")}
        if "ix_orders_status" not in idx_names:
            with engine.begin() as conn:
                conn.execute(text("CREATE INDEX ix_orders_status ON orders (status)"))
            logger.info("Migration: created index ix_orders_status")
    if "order_items" in insp.get_table_names():
        idx_names = {i["name"] for i in insp.get_indexes("order_items")}
        if "ix_order_items_status" not in idx_names:
            with engine.begin() as conn:
                conn.execute(text("CREATE INDEX ix_order_items_status ON order_items (status)"))
            logger.info("Migration: created index ix_order_items_status")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv("TESTING") != "1":
        models.Base.metadata.create_all(bind=engine)
        _migrate_background_to_theme(engine)
        _migrate_add_role_column(engine)
        _migrate_add_indexes(engine)
        from .ai_client import ai_client
        available = await ai_client.check_available()
        if available:
            logger.info("AGY CLI is available")
        else:
            logger.warning("AGY CLI is NOT available — AI features disabled")
    yield


app = FastAPI(title="宝宝的私房菜馆", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router)
app.include_router(dishes.router)
app.include_router(orders.router)
app.include_router(recipes.router)
app.include_router(admin.router)
app.include_router(history.router)


@app.middleware("http")
async def set_csrf_cookie(request: Request, call_next):
    if not request.cookies.get(CSRF_COOKIE_NAME):
        token = generate_csrf_token()
        request.state.csrf_token = token
    response = await call_next(request)
    if not request.cookies.get(CSRF_COOKIE_NAME):
        token = getattr(request.state, "csrf_token", generate_csrf_token())
        response.set_cookie(
            key=CSRF_COOKIE_NAME, value=token,
            httponly=True, samesite="lax",
            max_age=86400, secure=is_production(),
        )
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if 300 <= exc.status_code < 400 and exc.headers and "Location" in exc.headers:
        return RedirectResponse(url=exc.headers["Location"], status_code=exc.status_code)
    return templates.TemplateResponse(request, "error.html", {"detail": exc.detail}, status_code=exc.status_code)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global error: {exc}", exc_info=True)
    return templates.TemplateResponse(request, "error.html", {"detail": "系统出现意外错误，请稍后再试。"}, status_code=500)
