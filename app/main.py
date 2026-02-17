from fastapi import FastAPI, Depends, Request, Form, UploadFile, File, Cookie, Response, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional
import shutil
import os
import uuid
import aiofiles
import logging

from . import models, schemas, crud
from .database import engine, get_db

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="宝宝的私房菜馆")

@app.on_event("startup")
def on_startup():
    # Create database tables on startup (skip if testing)
    if os.getenv("TESTING") != "1":
        models.Base.metadata.create_all(bind=engine)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Dependency to get current user
async def get_current_user(db: Session = Depends(get_db), user_id: Optional[str] = Cookie(None)):
    if not user_id:
        return None
    try:
        user = crud.get_user(db, int(user_id))
        return user
    except (ValueError, TypeError):
        return None

# Dependency that requires login
async def login_required(user: Optional[models.User] = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=303, detail="Not logged in", headers={"Location": "/login"})
    return user

# Exception handler for login redirect
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 303 and exc.headers and "Location" in exc.headers:
        return RedirectResponse(url=exc.headers["Location"], status_code=303)
    return templates.TemplateResponse("error.html", {"request": request, "detail": exc.detail}, status_code=exc.status_code)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global error: {exc}", exc_info=True)
    return templates.TemplateResponse("error.html", {"request": request, "detail": "系统出现意外错误，请稍后再试。"}, status_code=500)

# Helper to get common context
def get_common_context(db: Session, current_user: Optional[models.User] = None):
    users = crud.get_users(db)
    return {
        "users": users,
        "current_user": current_user,
        "current_user_id": current_user.id if current_user else None
    }

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(
    name: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = crud.authenticate_user(db, name, password)
    if not user:
        return RedirectResponse(url="/login?error=1", status_code=303)
    
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(key="user_id", value=str(user.id), httponly=True, samesite="lax")
    return response

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key="user_id")
    return response

@app.get("/", response_class=HTMLResponse)
async def read_root(
    request: Request, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(login_required)
):
    context = get_common_context(db, current_user)
    dishes = crud.get_dishes(db)
    current_order = crud.get_current_order(db)
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "dishes": dishes, 
        "current_order": current_order,
        **context
    })

@app.get("/users", response_class=HTMLResponse)
async def users_page(
    request: Request, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(login_required)
):
    context = get_common_context(db, current_user)
    return templates.TemplateResponse("users.html", {
        "request": request,
        **context
    })

async def save_upload_file(file: UploadFile, destination_dir: str) -> str:
    os.makedirs(destination_dir, exist_ok=True)
    file_extension = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4()}{file_extension}"
    filepath = os.path.join(destination_dir, filename)
    
    async with aiofiles.open(filepath, 'wb') as out_file:
        while content := await file.read(1024 * 1024):  # 1MB chunks
            await out_file.write(content)
            
    return f"/{filepath}"

@app.post("/create-user")
async def create_user(
    name: str = Form(...),
    password: str = Form("666"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required)
):
    user_data = schemas.UserCreate(name=name, password=password)
    crud.create_user(db, user_data)
    return RedirectResponse(url="/users?msg= 新成员已加入！", status_code=303)

@app.post("/update-user/{target_user_id}")
async def update_user(
    target_user_id: int,
    name: str = Form(None),
    password: str = Form(None),
    background_file: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required)
):
    update_data = {}
    if name: update_data["name"] = name
    if password: update_data["password"] = password
    
    if background_file and background_file.filename:
        old_target_user = crud.get_user(db, target_user_id)
        if old_target_user and old_target_user.background_image_url:
            delete_old_image(old_target_user.background_image_url)

        image_url = await save_upload_file(background_file, "static/backgrounds")
        update_data["background_image_url"] = image_url
    
    crud.update_user(db, target_user_id, update_data, current_user.id)
    return RedirectResponse(url="/users?msg= 信息已更新", status_code=303)

@app.post("/delete-user/{target_user_id}")
async def delete_user(
    target_user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required)
):
    if current_user.id == target_user_id:
        return RedirectResponse(url="/users?error=self_delete", status_code=303)
        
    crud.delete_user(db, target_user_id, current_user.id)
    return RedirectResponse(url="/users?msg= 用户已移除", status_code=303)

@app.get("/order", response_class=HTMLResponse)
async def order_page(
    request: Request, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(login_required)
):
    context = get_common_context(db, current_user)
    current_order = crud.get_current_order(db)
    if not current_order:
        current_order = crud.create_order(db, schemas.OrderCreate(created_by=current_user.id))
    
    dishes = crud.get_dishes(db)
    return templates.TemplateResponse("order.html", {
        "request": request, 
        "current_order": current_order, 
        "dishes": dishes,
        **context
    })

@app.post("/add-item")
async def add_item(
    request: Request,
    dish_id: int = Form(...),
    taste: str = Form(None),
    preferred_time: str = Form(None),
    location: str = Form(None),
    ingredients: str = Form(None),
    remarks: str = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required)
):
    current_order = crud.get_current_order(db)
    if not current_order:
        current_order = crud.create_order(db, schemas.OrderCreate(created_by=current_user.id))
    
    item_data = schemas.OrderItemCreate(
        order_id=current_order.id,
        dish_id=dish_id,
        user_id=current_user.id,
        taste=taste,
        preferred_time=preferred_time,
        location=location,
        ingredients=ingredients,
        remarks=remarks
    )
    crud.add_order_item(db, item_data)
    return RedirectResponse(url="/my-orders?msg=点餐成功！", status_code=303)

@app.post("/create-dish")
async def create_dish(
    name: str = Form(...),
    description: str = Form(None),
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required)
):
    image_url = None
    if file and file.filename:
        image_url = await save_upload_file(file, "static/uploads")
    
    dish_data = schemas.DishCreate(
        name=name,
        description=description,
        image_url=image_url,
        created_by=current_user.id
    )
    crud.create_dish(db, dish_data)
    return RedirectResponse(url="/?msg=新菜品已收录！", status_code=303)

@app.get("/get-preference/{dish_id}")
async def get_preference(
    dish_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required)
):
    pref = crud.get_last_item_preference(db, current_user.id, dish_id)
    if pref:
        return {
            "taste": pref.taste,
            "preferred_time": pref.preferred_time,
            "location": pref.location,
            "ingredients": pref.ingredients,
            "remarks": pref.remarks
        }
    return {}

@app.get("/history", response_class=HTMLResponse)
async def history_page(
    request: Request, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(login_required)
):
    context = get_common_context(db, current_user)
    orders = crud.get_order_history(db)
    logs = crud.get_audit_logs(db)
    
    # Calculate some statistics
    all_items = []
    for o in orders:
        all_items.extend(o.items)
    
    dish_counts = {}
    for item in all_items:
        dish_counts[item.dish.name] = dish_counts.get(item.dish.name, 0) + 1
    
    top_dishes = sorted(dish_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    
    user_counts = {}
    for item in all_items:
        user_counts[item.user.name] = user_counts.get(item.user.name, 0) + 1
    
    active_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:3]

    return templates.TemplateResponse("history.html", {
        "request": request, 
        "orders": orders, 
        "logs": logs,
        "stats": {
            "total_orders": len(orders),
            "total_items": len(all_items),
            "top_dishes": top_dishes,
            "active_users": active_users
        },
        **context
    })

@app.get("/my-orders", response_class=HTMLResponse)
async def my_orders_page(
    request: Request, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(login_required)
):
    context = get_common_context(db, current_user)
    current_order = crud.get_current_order(db)
    return templates.TemplateResponse("my_orders.html", {
        "request": request,
        "current_order": current_order,
        **context
    })

@app.post("/update-item/{item_id}")
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
    current_user: models.User = Depends(login_required)
):
    # Check query params for status/msg (used by swipe gestures)
    query_status = request.query_params.get("status")
    query_msg = request.query_params.get("msg", "已更新")
    
    item_data = {
        "taste": taste,
        "preferred_time": preferred_time,
        "location": location,
        "ingredients": ingredients,
        "remarks": remarks
    }
    
    # Prioritize form status if provided, otherwise use query status
    final_status = status or query_status
    if final_status:
        item_data["status"] = final_status
        
    crud.update_order_item(db, item_id, item_data, current_user.id)
    return RedirectResponse(url=f"/my-orders?msg={query_msg}", status_code=303)

@app.post("/complete-item/{item_id}")
async def complete_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required)
):
    crud.update_order_item(db, item_id, {"status": "completed"}, current_user.id)
    return RedirectResponse(url="/my-orders?msg=祝你好胃口！", status_code=303)

@app.post("/delay-item/{item_id}")
async def delay_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required)
):
    crud.update_order_item(db, item_id, {"status": "delayed"}, current_user.id)
    return RedirectResponse(url="/my-orders?msg=已延期", status_code=303)

@app.post("/delete-item/{item_id}")
async def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required)
):
    crud.delete_order_item(db, item_id, current_user.id)
    return RedirectResponse(url="/my-orders?msg=已取消", status_code=303)

@app.post("/delete-order/{order_id}")
async def delete_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required)
):
    crud.delete_order(db, order_id, current_user.id)
    return RedirectResponse(url="/my-orders?msg=订单已清空", status_code=303)

def delete_old_image(image_url: Optional[str]):
    if image_url and (image_url.startswith("/static/uploads/") or image_url.startswith("/static/backgrounds/")):
        relative_path = image_url.lstrip("/")
        if os.path.exists(relative_path):
            try:
                os.remove(relative_path)
            except Exception as e:
                logger.error(f"Error deleting file {relative_path}: {e}")

@app.post("/update-dish/{dish_id}")
async def update_dish(
    dish_id: int,
    name: str = Form(...),
    description: str = Form(None),
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required)
):
    dish_data = {"name": name, "description": description}
    
    if file and file.filename:
        old_dish = crud.get_dish(db, dish_id)
        if old_dish and old_dish.image_url:
            delete_old_image(old_dish.image_url)

        image_url = await save_upload_file(file, "static/uploads")
        dish_data["image_url"] = image_url
    
    crud.update_dish(db, dish_id, dish_data, current_user.id)
    return RedirectResponse(url="/?msg=菜品已更新", status_code=303)

@app.post("/delete-dish/{dish_id}")
async def delete_dish(
    dish_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(login_required)
):
    crud.delete_dish(db, dish_id, current_user.id)
    return RedirectResponse(url="/?msg=菜品已下架", status_code=303)
