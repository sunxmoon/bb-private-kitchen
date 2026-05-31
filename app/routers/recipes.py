import logging

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from .. import crud, models
from ..ai_client import ai_client
from ..csrf import get_csrf_token
from ..database import get_db
from ..dependencies import login_required, templates
from ..recipe_utils import parse_recipe_from_form

logger = logging.getLogger(__name__)

router = APIRouter(tags=["recipes"])


@router.get("/recipe-editor/{dish_id}", response_class=HTMLResponse)
async def recipe_editor(
    request: Request,
    dish_id: int,
    edit: int = 0,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required),
):
    dish = crud.get_dish(db, dish_id)
    if not dish:
        return RedirectResponse(url="/?msg=菜品不存在", status_code=303)
    recipe = crud.get_recipe_by_dish(db, dish_id)
    return templates.TemplateResponse(request, "recipe_modal.html", {
        "dish": dish,
        "recipe": recipe.content if recipe else None,
        "edit_mode": bool(edit),
        "ai_available": await ai_client.check_available(),
        "csrf_token": get_csrf_token(request),
    })


@router.post("/update-recipe/{dish_id}", response_class=HTMLResponse)
async def update_recipe(
    request: Request,
    dish_id: int,
    recipe_ingredients: str = Form(None),
    recipe_steps: str = Form(None),
    recipe_cook_time: str = Form(None),
    recipe_difficulty: str = Form(None),
    recipe_tips: str = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required),
):
    content = parse_recipe_from_form(recipe_ingredients, recipe_steps, recipe_cook_time, recipe_difficulty, recipe_tips)
    if content:
        crud.create_or_update_recipe(db, dish_id, content, current_user.id)

    # Return back to view mode
    response = await recipe_editor(request, dish_id, edit=0, db=db, current_user=current_user)
    response.headers["HX-Trigger"] = "dishUpdated"
    return response


@router.post("/generate-recipe-modal/{dish_id}", response_class=HTMLResponse)
async def generate_recipe_modal(
    request: Request,
    dish_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required),
):
    dish = crud.get_dish(db, dish_id)
    if not dish:
        return RedirectResponse(url="/?msg=菜品不存在", status_code=303)

    try:
        recipe_data = await ai_client.generate_recipe(dish.name, dish.description)
        crud.create_or_update_recipe(db, dish_id, recipe_data, current_user.id)
        recipe = crud.get_recipe_by_dish(db, dish_id)
    except Exception as e:
        logger.error("Recipe generation failed: %s", e)
        recipe = crud.get_recipe_by_dish(db, dish_id)
        return templates.TemplateResponse(request, "recipe_modal.html", {
            "dish": dish,
            "recipe": recipe.content if recipe else None,
            "edit_mode": True,
            "ai_available": await ai_client.check_available(),
            "csrf_token": get_csrf_token(request),
            "error": "菜谱生成失败，请稍后重试",
        }, headers={"HX-Trigger": "dishUpdated"})

    return templates.TemplateResponse(request, "recipe_modal.html", {
        "dish": dish,
        "recipe": recipe.content if recipe else None,
        "edit_mode": True,
        "ai_available": await ai_client.check_available(),
        "csrf_token": get_csrf_token(request),
    }, headers={"HX-Trigger": "dishUpdated"})


@router.get("/api/ai-status")
async def ai_status():
    available = await ai_client.check_available()
    return {"available": available}


@router.post("/generate-recipe/{dish_id}")
async def generate_recipe(
    request: Request,
    dish_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required),
):
    dish = crud.get_dish(db, dish_id)
    if not dish:
        return templates.TemplateResponse(request, "_recipe_content.html", {
            "dish_id": dish_id, "has_recipe": False,
        })

    if not await ai_client.check_available():
        return templates.TemplateResponse(request, "_recipe_content.html", {
            "dish_id": dish_id, "has_recipe": False,
        })

    try:
        recipe_data = await ai_client.generate_recipe(dish.name, dish.description)
        crud.create_or_update_recipe(db, dish_id, recipe_data, current_user.id)
        recipe = crud.get_recipe_by_dish(db, dish_id)
        return templates.TemplateResponse(request, "_recipe_content.html", {
            "recipe": recipe.content if recipe else None,
            "dish_id": dish_id,
        })
    except Exception as e:
        logger.error("Recipe generation failed for dish %s: %s", dish.name, e)
        return templates.TemplateResponse(request, "_recipe_content.html", {
            "dish_id": dish_id, "has_recipe": False,
        })


@router.post("/generate-recipe-form/{dish_id}")
async def generate_recipe_form(
    request: Request,
    dish_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required),
):
    dish = crud.get_dish(db, dish_id)
    if not dish:
        return templates.TemplateResponse(request, "_recipe_form_fields.html", {
            "recipe": None,
            "ai_generate_url": f"/generate-recipe-form/{dish_id}",
            "ai_available": False,
        })

    if not await ai_client.check_available():
        return templates.TemplateResponse(request, "_recipe_form_fields.html", {
            "recipe": None,
            "ai_generate_url": f"/generate-recipe-form/{dish_id}",
            "ai_available": False,
        })

    try:
        recipe_data = await ai_client.generate_recipe(dish.name, dish.description)
        crud.create_or_update_recipe(db, dish_id, recipe_data, current_user.id)
        recipe = crud.get_recipe_by_dish(db, dish_id)
    except Exception as e:
        logger.error("Recipe generation failed: %s", e)
        return templates.TemplateResponse(request, "_recipe_form_fields.html", {
            "recipe": None,
            "ai_generate_url": f"/generate-recipe-form/{dish_id}",
            "ai_available": True,
            "error": "菜谱生成失败，请重试",
        })

    return templates.TemplateResponse(request, "_recipe_form_fields.html", {
        "recipe": recipe.content if recipe else None,
        "ai_generate_url": f"/generate-recipe-form/{dish_id}",
        "ai_available": True,
        "msg": "菜谱已生成"
    })


@router.post("/generate-recipe-form")
async def generate_recipe_form_new(
    request: Request,
    name: str = Form(...),
    description: str = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required),
):
    if not await ai_client.check_available():
        return templates.TemplateResponse(request, "_recipe_form_fields.html", {
            "recipe": None,
            "ai_generate_url": "/generate-recipe-form",
            "ai_available": False,
        })

    try:
        recipe_data = await ai_client.generate_recipe(name, description)
    except Exception as e:
        logger.error("Recipe form generation failed for new dish %s: %s", name, e)
        return templates.TemplateResponse(request, "_recipe_form_fields.html", {
            "recipe": None,
            "ai_generate_url": "/generate-recipe-form",
            "ai_available": True,
        })

    return templates.TemplateResponse(request, "_recipe_form_fields.html", {
        "recipe": recipe_data,
        "ai_generate_url": "/generate-recipe-form",
        "ai_available": True,
    })


@router.get("/recipe-content/{dish_id}")
async def recipe_content(
    request: Request,
    dish_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required),
):
    recipe = crud.get_recipe_by_dish(db, dish_id)
    return templates.TemplateResponse(request, "_recipe_content.html", {
        "recipe": recipe.content if recipe else None,
        "dish_id": dish_id,
        "has_recipe": recipe is not None,
    })
