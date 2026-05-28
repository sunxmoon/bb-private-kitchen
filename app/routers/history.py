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
    stats = crud.get_order_stats(db)
    return templates.TemplateResponse(request, "history.html", {
        "stats": stats,
        **context,
    })
