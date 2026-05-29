from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from .. import crud
from ..csrf import csrf_guard, get_csrf_token
from ..database import get_db
from ..dependencies import templates
from ..rate_limit import login_rate_limit
from ..security import is_production, sign_cookie_value

router = APIRouter(tags=["auth"])


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "login.html", {
        "csrf_token": get_csrf_token(request),
    })


@router.post("/login")
async def login(
    request: Request,
    name: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    await login_rate_limit(request)
    await csrf_guard(request)
    user = crud.get_user_by_name(db, name)
    if not user:
        crud.create_audit_log(db, 0, f"登录失败(用户不存在): {name}", "users", 0)
        return RedirectResponse(url="/login?error=invalid_credentials", status_code=303)
    if not crud.authenticate_user(db, name, password):
        crud.create_audit_log(db, user.id, "登录失败(密码错误)", "users", user.id)
        return RedirectResponse(url="/login?error=invalid_credentials", status_code=303)
    crud.create_audit_log(db, user.id, "登录成功", "users", user.id)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key="user_id",
        value=sign_cookie_value(str(user.id)),
        httponly=True, samesite="lax", max_age=86400,
        secure=is_production(),
    )
    return response


@router.post("/logout")
async def logout(request: Request):
    await csrf_guard(request)
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key="user_id", secure=is_production())
    return response
