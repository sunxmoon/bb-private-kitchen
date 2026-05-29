from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..ai_client import ai_client
from ..csrf import get_csrf_token
from ..database import get_db
from ..dependencies import delete_old_image, get_common_context, login_required, save_upload_file, templates


def _parse_recipe_from_form(
    recipe_ingredients: str | None,
    recipe_steps: str | None,
    recipe_cook_time: str | None,
    recipe_difficulty: str | None,
    recipe_tips: str | None,
) -> dict | None:
    ingredients = []
    if recipe_ingredients:
        for line in recipe_ingredients.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split(None, 1)
            if len(parts) == 2:
                ingredients.append({"amount": parts[0], "name": parts[1]})
            else:
                ingredients.append({"amount": "", "name": parts[0]})
    steps = [s.strip() for s in recipe_steps.strip().split("\n") if s.strip()] if recipe_steps else []
    if not ingredients and not steps:
        return None

    tips = []
    if recipe_tips:
        tips = [t.strip() for t in recipe_tips.strip().split("\n") if t.strip()]

    content = {
        "ingredients": ingredients,
        "steps": steps,
        "cook_time": recipe_cook_time.strip() if recipe_cook_time else "",
        "difficulty": recipe_difficulty.strip() if recipe_difficulty else "",
        "tips": tips if tips else "",
    }
    return content


def _save_recipe_form(db, dish_id, recipe_ingredients, recipe_steps, recipe_cook_time, recipe_difficulty, recipe_tips, user_id):
    content = _parse_recipe_from_form(recipe_ingredients, recipe_steps, recipe_cook_time, recipe_difficulty, recipe_tips)
    if content:
        crud.create_or_update_recipe(db, dish_id, content, user_id)

router = APIRouter(tags=["dishes"])


@router.get("/", response_class=HTMLResponse)
async def read_root(
    request: Request,
    q: str = "",
    cat: str = "",
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required),
):
    context = get_common_context(request, db, current_user)
    dishes = crud.search_dishes(db, q, cat) if (q or cat) else crud.get_dishes(db)
    categories = crud.get_dish_categories(db)
    current_order = crud.get_current_order(db)
    return templates.TemplateResponse(request, "index.html", {
        "dishes": dishes,
        "categories": categories,
        "current_order": current_order,
        "ai_available": await ai_client.check_available(),
        "search_query": q,
        "current_category": cat,
        **context,
    })


@router.get("/dish-detail/{dish_id}", response_class=HTMLResponse)
async def dish_detail(
    request: Request,
    dish_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required),
):
    dish = crud.get_dish(db, dish_id)
    if not dish:
        return HTMLResponse("菜品不存在", status_code=404)
    return templates.TemplateResponse(request, "dish_detail_modal.html", {
        "dish": dish,
        "csrf_token": get_csrf_token(request),
    })


@router.post("/create-dish")
async def create_dish(
    name: str = Form(...),
    description: str = Form(None),
    category: str = Form(""),
    file: UploadFile = File(None),
    recipe_ingredients: str = Form(None),
    recipe_steps: str = Form(None),
    recipe_cook_time: str = Form(None),
    recipe_difficulty: str = Form(None),
    recipe_tips: str = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required),
):
    image_url = None
    if file and file.filename:
        image_url = await save_upload_file(file, "static/uploads")
    dish_data = schemas.DishCreate(
        name=name,
        description=description,
        image_url=image_url,
        category=category,
        created_by=current_user.id,
    )
    dish = crud.create_dish(db, dish_data)
    if dish.image_url and dish.image_url != image_url and image_url:
        delete_old_image(image_url)
    if recipe_ingredients or recipe_steps:
        _save_recipe_form(
            db, dish.id, recipe_ingredients, recipe_steps,
            recipe_cook_time, recipe_difficulty, recipe_tips, current_user.id,
        )
    return RedirectResponse(url="/?msg=新菜品已收录！", status_code=303)


@router.get("/get-preference/{dish_id}")
async def get_preference(
    dish_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required),
):
    pref = crud.get_last_item_preference(db, current_user.id, dish_id)
    if pref:
        return {
            "taste": pref.taste,
            "preferred_time": pref.preferred_time,
            "location": pref.location,
            "ingredients": pref.ingredients,
            "remarks": pref.remarks,
        }
    return {}


@router.post("/update-dish/{dish_id}")
async def update_dish(
    dish_id: int,
    name: str = Form(...),
    description: str = Form(None),
    file: UploadFile = File(None),
    recipe_ingredients: str = Form(None),
    recipe_steps: str = Form(None),
    recipe_cook_time: str = Form(None),
    recipe_difficulty: str = Form(None),
    recipe_tips: str = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required),
):
    dish = crud.get_dish(db, dish_id)
    if not dish:
        return RedirectResponse(url="/?msg=菜品不存在", status_code=404)
    if dish.created_by != current_user.id and current_user.role != "admin":
        return RedirectResponse(url="/?msg=只能修改自己创建的菜品", status_code=303)
    dish_data = {"name": name}
    if description is not None:
        dish_data["description"] = description
    if file and file.filename:
        if dish.image_url:
            delete_old_image(dish.image_url)
        image_url = await save_upload_file(file, "static/uploads")
        dish_data["image_url"] = image_url
    crud.update_dish(db, dish_id, dish_data, current_user.id)
    if recipe_ingredients or recipe_steps:
        _save_recipe_form(
            db, dish_id, recipe_ingredients, recipe_steps,
            recipe_cook_time, recipe_difficulty, recipe_tips, current_user.id,
        )
    return RedirectResponse(url="/?msg=菜品已更新", status_code=303)


@router.post("/delete-dish/{dish_id}")
async def delete_dish(
    dish_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required),
):
    dish = crud.get_dish(db, dish_id)
    if not dish:
        return RedirectResponse(url="/?msg=菜品不存在", status_code=404)
    if dish.created_by != current_user.id and current_user.role != "admin":
        return RedirectResponse(url="/?msg=只能下架自己创建的菜品", status_code=303)
    try:
        crud.delete_dish(db, dish_id, current_user.id)
    except ValueError as e:
        return RedirectResponse(url=f"/?msg={str(e)}", status_code=303)
    return RedirectResponse(url="/?msg=菜品已下架", status_code=303)
