import re
from collections import defaultdict

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..broadcaster import order_broadcaster
from ..database import get_db
from ..dependencies import get_common_context, login_required, redirect_with_flash, require_admin, templates

router = APIRouter(tags=["orders"])


@router.get("/orders/stream")
async def orders_stream():
    return StreamingResponse(order_broadcaster.subscribe(), media_type="text/event-stream")


@router.get("/order")
def order_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required),
):
    context = get_common_context(request, db, current_user)
    current_order = crud.get_or_create_current_order(db, current_user.id)
    dishes = crud.get_dishes(db)
    top_dishes = crud.get_user_top_dishes(db, current_user.id)
    return templates.TemplateResponse(
        request,
        "order.html",
        {
            "current_order": current_order,
            "dishes": dishes,
            "top_dishes": top_dishes,
            **context,
        },
    )


@router.post("/add-item")
def add_item(
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
        return redirect_with_flash(url="/order", msg="菜品不存在或已下架")
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
    order_broadcaster.broadcast("update")
    return redirect_with_flash(url="/my-orders", msg="点餐成功！")


@router.post("/api/orders/batch")
def batch_add_items(
    request: Request,
    payload: schemas.BatchOrderRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required),
):
    if not payload.items:
        raise HTTPException(status_code=400, detail="点餐篮为空")

    current_order = crud.get_or_create_current_order(db, current_user.id)
    added_count = 0
    for it in payload.items:
        dish = crud.get_dish(db, it.dish_id)
        if not dish or not dish.is_active:
            continue
        qty = max(1, min(it.quantity, 20))
        taste = it.taste or payload.global_taste
        preferred_time = it.preferred_time or payload.global_time
        location = it.location or payload.global_location
        remarks = it.remarks or payload.global_remarks
        for _ in range(qty):
            item_data = schemas.OrderItemCreate(
                order_id=current_order.id,
                dish_id=it.dish_id,
                user_id=current_user.id,
                taste=taste,
                preferred_time=preferred_time,
                location=location,
                ingredients=it.ingredients,
                remarks=remarks,
            )
            crud.add_order_item(db, item_data, allow_duplicate=True)
            added_count += 1

    if added_count > 0:
        order_broadcaster.broadcast("update")

    return {"success": True, "added_count": added_count, "order_id": current_order.id}


@router.get("/my-orders")
def my_orders_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required),
):
    context = get_common_context(request, db, current_user)
    current_order = crud.get_current_order(db)
    return templates.TemplateResponse(
        request,
        "my_orders.html",
        {
            "current_order": current_order,
            **context,
        },
    )


@router.post("/update-item/{item_id}")
def update_item(
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
        return redirect_with_flash(url="/my-orders", msg="订单项不存在")
    if item.user_id != current_user.id and current_user.role != "admin":
        return redirect_with_flash(url="/my-orders", msg="只能修改自己的点单")
    VALID_STATUSES = {"pending", "completed", "delayed"}
    query_status = request.query_params.get("status")
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
    order_broadcaster.broadcast("update")
    return redirect_with_flash(url="/my-orders", msg="已更新")


@router.post("/complete-item/{item_id}")
def complete_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required),
):
    item = crud.get_order_item(db, item_id)
    if not item:
        return redirect_with_flash(url="/my-orders", msg="订单项不存在")
    if item.user_id != current_user.id and current_user.role != "admin":
        return redirect_with_flash(url="/my-orders", msg="只能完成自己的点单")
    crud.update_order_item(db, item_id, {"status": "completed"}, current_user.id)
    order_broadcaster.broadcast("update")
    return redirect_with_flash(url="/my-orders", msg="祝你好胃口！")


@router.post("/delay-item/{item_id}")
def delay_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required),
):
    item = crud.get_order_item(db, item_id)
    if not item:
        return redirect_with_flash(url="/my-orders", msg="订单项不存在")
    if item.user_id != current_user.id and current_user.role != "admin":
        return redirect_with_flash(url="/my-orders", msg="只能延期自己的点单")
    crud.update_order_item(db, item_id, {"status": "delayed"}, current_user.id)
    order_broadcaster.broadcast("update")
    return redirect_with_flash(url="/my-orders", msg="已延期")


@router.post("/delete-item/{item_id}")
def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required),
):
    item = crud.get_order_item(db, item_id)
    if not item:
        return redirect_with_flash(url="/my-orders", msg="订单项不存在")
    if item.user_id != current_user.id and current_user.role != "admin":
        return redirect_with_flash(url="/my-orders", msg="只能取消自己的点单")
    crud.delete_order_item(db, item_id, current_user.id)
    order_broadcaster.broadcast("update")
    return redirect_with_flash(url="/my-orders", msg="已取消")


@router.post("/delete-order/{order_id}")
def delete_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    result = crud.delete_order(db, order_id, current_user.id)
    order_broadcaster.broadcast("update")
    if not result:
        return redirect_with_flash(url="/my-orders", msg="订单不存在")
    return redirect_with_flash(url="/my-orders", msg="订单已清空")


@router.post("/complete-order")
def complete_order(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required),
):
    order = crud.get_current_order(db)
    if not order or not order.items:
        return redirect_with_flash(url="/my-orders", msg="当前无订单")
    pending = [i for i in order.items if i.status != "completed"]
    if pending:
        return RedirectResponse(url=f"/my-orders?msg=还有 {len(pending)} 道菜未完成", status_code=303)
    crud.complete_order(db, order.id, current_user.id)
    order_broadcaster.broadcast("update")
    return redirect_with_flash(url="/my-orders", msg="订单已完成！")


def _parse_quantity(text: str):
    """Extract numeric value and unit from ingredient quantity string."""
    match = re.match(r"([\d.]+)\s*(\S+)", text.strip())
    if match:
        try:
            return float(match.group(1)), match.group(2)
        except (ValueError, TypeError):
            return None, None
    return None, None


@router.post("/rate-item/{item_id}")
def rate_item(
    item_id: int,
    request: Request,
    rating: int = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required),
):
    if rating < 1 or rating > 5:
        return redirect_with_flash(url="/my-orders", msg="评分无效")
    item = crud.get_order_item(db, item_id)
    if not item:
        return redirect_with_flash(url="/my-orders", msg="订单项不存在")
    if item.user_id != current_user.id and current_user.role != "admin":
        return redirect_with_flash(url="/my-orders", msg="只能评价自己的点单")
    result = crud.rate_dish(db, item_id, rating, current_user.id)
    order_broadcaster.broadcast("update")
    if not result:
        return redirect_with_flash(url="/my-orders", msg="评分失败")
    return redirect_with_flash(url="/my-orders", msg="已评分")


@router.get("/shopping-list", response_class=HTMLResponse)
def shopping_list(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required),
):
    context = get_common_context(request, db, current_user)
    order = crud.get_current_order(db)

    aggregated = defaultdict(lambda: {"qty": 0, "unit": "", "dishes": set()})

    if order:
        for item in order.items:
            if item.status == "completed":
                continue
            if not item.dish or not item.dish.recipe:
                continue
            recipe_content = item.dish.recipe.content
            if not isinstance(recipe_content, dict):
                continue
            for ing in recipe_content.get("ingredients", []):
                name = ing.get("name", "").strip()
                amount_str = ing.get("amount", "")
                if not name:
                    continue
                qty, unit = _parse_quantity(amount_str)
                aggregated[name]["dishes"].add(item.dish.name)
                if qty is not None:
                    if unit and aggregated[name]["unit"] and aggregated[name]["unit"] != unit:
                        aggregated[name]["qty"] = None
                        aggregated[name]["unit"] = f"{aggregated[name]['unit']}+{unit}"
                    else:
                        if aggregated[name]["qty"] is not None:
                            aggregated[name]["qty"] += qty
                        aggregated[name]["unit"] = unit

    CATEGORIES = {
        "肉禽类": ["肉", "鸡", "鸭", "牛", "羊", "排", "翅", "腿", "骨", "肠", "丸", "蛋", "猪"],
        "水产海鲜": ["鱼", "虾", "蟹", "贝", "蛤", "鱿", "鲜", "生蚝", "海带", "螺"],
        "蔬菜菌菇": ["菜", "菇", "瓜", "豆角", "萝卜", "茄", "葱", "蒜", "姜", "椒", "笋", "菌", "耳", "薯", "芋", "藕"],
        "调味干货": ["油", "盐", "糖", "酱", "醋", "酒", "精", "料", "香", "八角", "桂皮", "花椒", "干", "孜然", "淀粉"],
        "主食豆品": ["米", "面", "粉", "豆", "腐", "饼", "糕", "卷"],
    }

    def get_category(name: str) -> str:
        for cat, keywords in CATEGORIES.items():
            if any(kw in name for kw in keywords):
                return cat
        return "其他"

    categorized_items = defaultdict(list)
    for name, data in sorted(aggregated.items()):
        qty = data["qty"]
        unit = data["unit"]
        if qty is not None:
            qty_str = f"{qty:g}{unit}" if unit else str(qty)
        else:
            qty_str = unit if unit else "—"

        cat = get_category(name)
        categorized_items[cat].append(
            {
                "name": name,
                "qty": qty_str,
                "dishes": sorted(data["dishes"]),
            }
        )

    shopping_items = [{"category": cat, "items": items} for cat, items in categorized_items.items()]

    return templates.TemplateResponse(
        request,
        "shopping_list.html",
        {
            "shopping_items": shopping_items,
            "order_id": order.id if order else None,
            **context,
        },
    )
