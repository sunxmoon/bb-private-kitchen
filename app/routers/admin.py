import re

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..database import get_db
from ..dependencies import get_common_context, require_admin, templates

router = APIRouter(tags=["admin"])


@router.get("/admin", response_class=HTMLResponse)
async def admin_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
    page: int = 1,
):
    page = max(1, page)
    context = get_common_context(request, db, current_user)
    orders = crud.get_order_history(db, page=page)
    total_orders = crud.get_order_history_count(db)
    total_pages = max(1, (total_orders + crud.PAGE_SIZE - 1) // crud.PAGE_SIZE)
    logs = crud.get_audit_logs(db)

    return templates.TemplateResponse(request, "admin.html", {
        "users": context["users"],
        "orders": orders,
        "logs": logs,
        "page": page,
        "total_pages": total_pages,
        **context
    })


@router.get("/users")
async def users_redirect():
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/create-user")
async def create_user(
    name: str = Form(...),
    password: str = Form("666"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    user_data = schemas.UserCreate(name=name, password=password)
    crud.create_user(db, user_data, actor_id=current_user.id)
    return RedirectResponse(url="/admin?msg=新成员已加入！", status_code=303)


@router.post("/update-user/{target_user_id}")
async def update_user(
    target_user_id: int,
    name: str = Form(None),
    password: str = Form(None),
    theme_color: str = Form(None),
    role: str = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    if not crud.get_user(db, target_user_id):
        return RedirectResponse(url="/admin?msg=用户不存在", status_code=404)
    update_data = {}
    if name:
        update_data["name"] = name
    if password:
        update_data["password"] = password
    if theme_color:
        if not re.match(r'^#[0-9a-fA-F]{6}$', theme_color):
            return RedirectResponse(url="/admin?msg=无效的主题色", status_code=303)
        update_data["theme_color"] = theme_color
    if role:
        update_data["role"] = role
    crud.update_user(db, target_user_id, update_data, current_user.id)
    return RedirectResponse(url="/admin?msg=信息已更新", status_code=303)


@router.post("/delete-user/{target_user_id}")
async def delete_user(
    target_user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    if current_user.id == target_user_id:
        return RedirectResponse(url="/admin?error=self_delete", status_code=303)
    target = crud.get_user(db, target_user_id)
    if not target:
        return RedirectResponse(url="/admin?msg=用户不存在", status_code=404)
    crud.delete_user(db, target_user_id, current_user.id)
    return RedirectResponse(url="/admin?msg=用户已移除", status_code=303)
