import re

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .. import crud, models
from ..csrf import get_csrf_token
from ..database import get_db
from ..dependencies import login_required, templates

router = APIRouter(tags=["settings"])


@router.get("/settings")
async def settings_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required),
):
    return templates.TemplateResponse(request, "settings.html", {
        "csrf_token": get_csrf_token(request),
        "current_user": current_user,
    })


@router.post("/settings")
async def update_settings(
    request: Request,
    password: str = Form(None),
    theme_color: str = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required),
):
    update_data = {}
    if password:
        if len(password) < 8:
            return RedirectResponse(url="/settings?msg=密码至少需要8个字符", status_code=303)
        update_data["password"] = password
    if theme_color:
        if not re.match(r'^#[0-9a-fA-F]{6}$', theme_color):
            return RedirectResponse(url="/settings?msg=无效的主题色", status_code=303)
        update_data["theme_color"] = theme_color

    if update_data:
        crud.update_user(db, current_user.id, update_data, current_user.id)
        return RedirectResponse(url="/settings?msg=已保存", status_code=303)
    return RedirectResponse(url="/settings", status_code=303)
