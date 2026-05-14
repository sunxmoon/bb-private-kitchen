from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from .. import crud, models
from ..database import get_db
from ..dependencies import get_common_context, login_required, templates

router = APIRouter(tags=["history"])


@router.get("/history", response_class=HTMLResponse)
async def history_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required),
):
    context = get_common_context(request, db, current_user)
    # Get all items for stats calculation
    orders = crud.get_order_history(db, page=1, limit=1000) # Get a large batch for stats
    total_orders = crud.get_order_history_count(db)

    all_items = []
    for o in orders:
        all_items.extend(o.items)

    dish_counts = {}
    for item in all_items:
        dish_name = item.dish.name if item.dish else "已删除的菜品"
        dish_counts[dish_name] = dish_counts.get(dish_name, 0) + 1

    top_dishes = sorted(dish_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    user_counts = {}
    for item in all_items:
        user_name = item.user.name if item.user else "已退出的用户"
        user_counts[user_name] = user_counts.get(user_name, 0) + 1

    active_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    return templates.TemplateResponse(request, "history.html", {
        "stats": {
            "total_orders": total_orders,
            "total_items": len(all_items),
            "top_dishes": top_dishes,
            "active_users": active_users,
        },
        **context,
    })
