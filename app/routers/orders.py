from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..csrf import csrf_guard
from ..database import get_db
from ..dependencies import get_common_context, login_required, require_admin, templates

router = APIRouter(tags=["orders"])


@router.get("/order")
async def order_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required),
):
    context = get_common_context(request, db, current_user)
    current_order = crud.get_or_create_current_order(db, current_user.id)
    dishes = crud.get_dishes(db)
    top_dishes = crud.get_user_top_dishes(db, current_user.id)
    return templates.TemplateResponse(request, "order.html", {
        "current_order": current_order,
        "dishes": dishes,
        "top_dishes": top_dishes,
        **context,
    })


@router.post("/add-item")
async def add_item(
    request: Request,
    dish_id: int = Form(...),
    taste: str = Form(None),
    preferred_time: str = Form(None),
    location: str = Form(None),
    ingredients: str = Form(None),
    remarks: str = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required),
):
    dish = crud.get_dish(db, dish_id)
    if not dish or not dish.is_active:
        return RedirectResponse(url="/order?msg=菜品不存在或已下架", status_code=303)
    current_order = crud.get_or_create_current_order(db, current_user.id)
    item_data = schemas.OrderItemCreate(
        order_id=current_order.id,
        dish_id=dish_id,
        user_id=current_user.id,
        taste=taste,
        preferred_time=preferred_time,
        location=location,
        ingredients=ingredients,
        remarks=remarks,
    )
    crud.add_order_item(db, item_data)
    return RedirectResponse(url="/my-orders?msg=点餐成功！", status_code=303)


@router.get("/my-orders")
async def my_orders_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required),
):
    context = get_common_context(request, db, current_user)
    current_order = crud.get_current_order(db)
    return templates.TemplateResponse(request, "my_orders.html", {
        "current_order": current_order,
        **context,
    })


@router.post("/update-item/{item_id}")
async def update_item(
    item_id: int,
    request: Request,
    taste: str = Form(None),
    preferred_time: str = Form(None),
    location: str = Form(None),
    ingredients: str = Form(None),
    remarks: str = Form(None),
    status: str = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required),
):
    item = crud.get_order_item(db, item_id)
    if not item:
        return RedirectResponse(url="/my-orders?msg=订单项不存在", status_code=404)
    if item.user_id != current_user.id and current_user.role != "admin":
        return RedirectResponse(url="/my-orders?msg=只能修改自己的点单", status_code=303)
    VALID_STATUSES = {"pending", "completed", "delayed"}
    query_status = request.query_params.get("status")
    query_msg = request.query_params.get("msg", "已更新")
    item_data = {
        "taste": taste,
        "preferred_time": preferred_time,
        "location": location,
        "ingredients": ingredients,
        "remarks": remarks,
    }
    final_status = status or query_status
    if final_status and final_status in VALID_STATUSES:
        item_data["status"] = final_status
    crud.update_order_item(db, item_id, item_data, current_user.id)
    return RedirectResponse(url=f"/my-orders?msg={query_msg}", status_code=303)


@router.post("/complete-item/{item_id}")
async def complete_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required),
):
    item = crud.get_order_item(db, item_id)
    if not item:
        return RedirectResponse(url="/my-orders?msg=订单项不存在", status_code=404)
    if item.user_id != current_user.id and current_user.role != "admin":
        return RedirectResponse(url="/my-orders?msg=只能完成自己的点单", status_code=303)
    crud.update_order_item(db, item_id, {"status": "completed"}, current_user.id)
    return RedirectResponse(url="/my-orders?msg=祝你好胃口！", status_code=303)


@router.post("/delay-item/{item_id}")
async def delay_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required),
):
    item = crud.get_order_item(db, item_id)
    if not item:
        return RedirectResponse(url="/my-orders?msg=订单项不存在", status_code=404)
    if item.user_id != current_user.id and current_user.role != "admin":
        return RedirectResponse(url="/my-orders?msg=只能延期自己的点单", status_code=303)
    crud.update_order_item(db, item_id, {"status": "delayed"}, current_user.id)
    return RedirectResponse(url="/my-orders?msg=已延期", status_code=303)


@router.post("/delete-item/{item_id}")
async def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required),
):
    item = crud.get_order_item(db, item_id)
    if not item:
        return RedirectResponse(url="/my-orders?msg=订单项不存在", status_code=404)
    if item.user_id != current_user.id and current_user.role != "admin":
        return RedirectResponse(url="/my-orders?msg=只能取消自己的点单", status_code=303)
    crud.delete_order_item(db, item_id, current_user.id)
    return RedirectResponse(url="/my-orders?msg=已取消", status_code=303)


@router.post("/delete-order/{order_id}")
async def delete_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    result = crud.delete_order(db, order_id, current_user.id)
    if not result:
        return RedirectResponse(url="/my-orders?msg=订单不存在", status_code=404)
    return RedirectResponse(url="/my-orders?msg=订单已清空", status_code=303)


@router.post("/complete-order")
async def complete_order(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required),
):
    await csrf_guard(request)
    order = crud.get_current_order(db)
    if not order or not order.items:
        return RedirectResponse(url="/my-orders?msg=当前无订单", status_code=303)
    pending = [i for i in order.items if i.status != "completed"]
    if pending:
        return RedirectResponse(url=f"/my-orders?msg=还有 {len(pending)} 道菜未完成", status_code=303)
    crud.complete_order(db, order.id, current_user.id)
    return RedirectResponse(url="/my-orders?msg=订单已完成！", status_code=303)
