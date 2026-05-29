import logging
import os
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .csrf import CSRF_COOKIE_NAME, generate_csrf_token
from .database import engine
from .dependencies import templates
from .routers import admin, auth, dishes, history, orders, recipes
from .security import is_production


def _configure_logging():
    log_level = logging.INFO
    if os.getenv("TESTING") == "1":
        log_level = logging.WARNING

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer() if not is_production() else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(format="%(message)s", level=log_level, force=True)


_configure_logging()
logger = logging.getLogger(__name__)


def _run_migrations():
    """Run Alembic migrations. Stamps existing databases on first use."""
    from alembic.config import Config
    from sqlalchemy import inspect

    from alembic import command

    alembic_cfg = Config("alembic.ini")
    insp = inspect(engine)

    # Existing database without alembic_version table — stamp as current
    if "users" in insp.get_table_names() and "alembic_version" not in insp.get_table_names():
        logger.info("Existing database detected, stamping current Alembic revision")
        command.stamp(alembic_cfg, "head")
    else:
        command.upgrade(alembic_cfg, "head")


def _seed_database():
    """Create initial users if database is empty."""
    from . import models, security
    from .database import SessionLocal

    db = SessionLocal()
    try:
        if db.query(models.User).count() == 0:
            users = [
                models.User(name="哥哥", password=security.get_password_hash("666"), role="admin"),
                models.User(name="姐姐", password=security.get_password_hash("666")),
                models.User(name="宝宝", password=security.get_password_hash("666")),
            ]
            db.add_all(users)
            db.commit()
            logger.info("Database seeded with initial users")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv("TESTING") != "1":
        _run_migrations()
        _seed_database()
        from .ai_client import ai_client
        available = await ai_client.check_available()
        if available:
            logger.info("AGY CLI is available")
        else:
            logger.warning("AGY CLI is NOT available — AI features disabled")
    yield


app = FastAPI(title="宝宝的私房菜馆", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/health")
async def health_check():
    from sqlalchemy import text
    db_ok = False
    try:
        from .database import SessionLocal
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_ok = True
    except Exception:
        pass
    ai_ok = False
    try:
        from .ai_client import ai_client
        ai_ok = await ai_client.check_available()
    except Exception:
        pass
    status_code = 200 if db_ok else 503
    from fastapi.responses import JSONResponse
    return JSONResponse(
        content={"status": "healthy" if db_ok else "degraded", "db": db_ok, "ai": ai_ok},
        status_code=status_code,
    )

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


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline' fonts.googleapis.com cdnjs.cloudflare.com unpkg.com; "
        "font-src fonts.gstatic.com cdnjs.cloudflare.com; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' unpkg.com; "
        "img-src 'self' data:; "
        "connect-src 'self'"
    )
    if is_production():
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    # Static file caching
    path = request.url.path
    if path.startswith("/static/css/") or path.startswith("/static/js/"):
        response.headers["Cache-Control"] = "public, max-age=86400"
    elif path.startswith("/static/uploads/"):
        response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if 300 <= exc.status_code < 400 and exc.headers and "Location" in exc.headers:
        return RedirectResponse(url=exc.headers["Location"], status_code=exc.status_code)
    return templates.TemplateResponse(request, "error.html", {"detail": exc.detail}, status_code=exc.status_code)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global error: {exc}", exc_info=True)
    detail = "系统出现意外错误，请稍后再试。" if is_production() else str(exc)
    return templates.TemplateResponse(request, "error.html", {"detail": detail}, status_code=500)
