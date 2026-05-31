from collections import defaultdict

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from .. import crud, models
from ..database import get_db
from ..dependencies import get_common_context, login_required, templates

router = APIRouter(tags=["history"])

VALID_VIEWS = {"list", "timeline"}


@router.get("/history", response_class=HTMLResponse)
async def history_page(
    request: Request,
    view: str = "list",
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required),
):
    context = get_common_context(request, db, current_user)
    stats = crud.get_order_stats(db)
    view = view if view in VALID_VIEWS else "list"
    orders = crud.get_order_history(db, limit=50)

    timeline = []
    if view == "timeline":
        grouped = defaultdict(list)
        for order in orders:
            date_key = order.created_at.strftime("%Y-%m-%d") if order.created_at else "unknown"
            grouped[date_key].append(order)
        for date_key in sorted(grouped.keys(), reverse=True):
            day_orders = grouped[date_key]
            items_summary = []
            for order in day_orders:
                for item in order.items:
                    dish_name = item.dish.name if item.dish else "已删除"
                    items_summary.append(dish_name)
            timeline.append({
                "date": date_key,
                "orders": day_orders,
                "dishes": items_summary,
                "total": len(items_summary),
            })

    return templates.TemplateResponse(request, "history.html", {
        "stats": stats,
        "orders": orders if view == "list" else [],
        "timeline": timeline if view == "timeline" else [],
        "current_view": view,
        **context,
    })
