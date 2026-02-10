from fastapi import FastAPI, Depends, Request, Form, UploadFile, File, Cookie, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional
import shutil
import os
import uuid

from . import models, schemas, crud
from .database import engine, get_db

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="宝宝的私房菜馆")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Helper to get common context
def get_common_context(db: Session, user_id: Optional[int] = None):
    users = crud.get_users(db)
    current_user = None
    if user_id:
        current_user = crud.get_user(db, int(user_id))
    
    # If no current user and users exist, we don't default anymore to force login if needed
    # but for existing templates that expect current_user_id, we'll provide it if possible
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
    response: Response,
    name: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = crud.authenticate_user(db, name, password)
    if not user:
        return RedirectResponse(url="/login?error=1", status_code=303)
    
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(key="user_id", value=str(user.id))
    return response

@app.get("/logout")
async def logout(response: Response):
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key="user_id")
    return response

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, db: Session = Depends(get_db), user_id: Optional[str] = Cookie(None)):
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
    context = get_common_context(db, user_id)
    if not context["current_user"]:
        return RedirectResponse(url="/login", status_code=303)
    dishes = crud.get_dishes(db)
    current_order = crud.get_current_order(db)
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "dishes": dishes, 
        "current_order": current_order,
        **context
    })

@app.get("/users", response_class=HTMLResponse)
async def users_page(request: Request, db: Session = Depends(get_db), user_id: Optional[str] = Cookie(None)):
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
    context = get_common_context(db, user_id)
    return templates.TemplateResponse("users.html", {
        "request": request,
        **context
    })

@app.post("/create-user")
async def create_user(
    name: str = Form(...),
    password: str = Form("666"),
    db: Session = Depends(get_db),
    user_id: Optional[str] = Cookie(None)
):
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
    user_data = schemas.UserCreate(name=name, password=password)
    crud.create_user(db, user_data)
    return RedirectResponse(url="/users", status_code=303)

@app.post("/update-user/{target_user_id}")
async def update_user(
    target_user_id: int,
    name: str = Form(None),
    password: str = Form(None),
    db: Session = Depends(get_db),
    user_id: Optional[str] = Cookie(None)
):
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
    update_data = {}
    if name: update_data["name"] = name
    if password: update_data["password"] = password
    
    crud.update_user(db, target_user_id, update_data, int(user_id))
    return RedirectResponse(url="/users", status_code=303)

@app.post("/delete-user/{target_user_id}")
async def delete_user(
    target_user_id: int,
    db: Session = Depends(get_db),
    user_id: Optional[str] = Cookie(None)
):
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
    
    # Don't delete yourself
    if int(user_id) == target_user_id:
        return RedirectResponse(url="/users?error=self_delete", status_code=303)
        
    crud.delete_user(db, target_user_id, int(user_id))
    return RedirectResponse(url="/users", status_code=303)

@app.get("/order", response_class=HTMLResponse)
async def order_page(request: Request, db: Session = Depends(get_db), user_id: Optional[str] = Cookie(None)):
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
    context = get_common_context(db, user_id)
    if not context["current_user"]:
        return RedirectResponse(url="/login", status_code=303)
    
    current_order = crud.get_current_order(db)
    if not current_order:
        current_order = crud.create_order(db, schemas.OrderCreate(created_by=context["current_user_id"]))
    
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
    user_id: Optional[str] = Cookie(None)
):
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
    current_user_id = int(user_id)
    current_order = crud.get_current_order(db)
    if not current_order:
        current_order = crud.create_order(db, schemas.OrderCreate(created_by=current_user_id))
    
    item_data = schemas.OrderItemCreate(
        order_id=current_order.id,
        dish_id=dish_id,
        user_id=current_user_id,
        taste=taste,
        preferred_time=preferred_time,
        location=location,
        ingredients=ingredients,
        remarks=remarks
    )
    crud.add_order_item(db, item_data)
    return RedirectResponse(url="/my-orders", status_code=303)

@app.post("/create-dish")
async def create_dish(
    name: str = Form(...),
    description: str = Form(None),
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
    user_id: Optional[str] = Cookie(None)
):
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
    current_user_id = int(user_id)
    image_url = None
    if file and file.filename:
        file_extension = os.path.splitext(file.filename)[1]
        filename = f"{uuid.uuid4()}{file_extension}"
        filepath = os.path.join("static/uploads", filename)
        os.makedirs("static/uploads", exist_ok=True)
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        image_url = f"/static/uploads/{filename}"
    
    dish_data = schemas.DishCreate(
        name=name,
        description=description,
        image_url=image_url,
        created_by=current_user_id
    )
    crud.create_dish(db, dish_data)
    return RedirectResponse(url="/", status_code=303)

@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request, db: Session = Depends(get_db), user_id: Optional[str] = Cookie(None)):
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
    context = get_common_context(db, user_id)
    orders = crud.get_order_history(db)
    logs = crud.get_audit_logs(db)
    return templates.TemplateResponse("history.html", {
        "request": request, 
        "orders": orders, 
        "logs": logs,
        **context
    })

@app.get("/my-orders", response_class=HTMLResponse)
async def my_orders_page(request: Request, db: Session = Depends(get_db), user_id: Optional[str] = Cookie(None)):
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
    context = get_common_context(db, user_id)
    current_order = crud.get_current_order(db)
    return templates.TemplateResponse("my_orders.html", {
        "request": request,
        "current_order": current_order,
        **context
    })

@app.post("/update-item/{item_id}")
async def update_item(
    item_id: int,
    taste: str = Form(None),
    preferred_time: str = Form(None),
    location: str = Form(None),
    ingredients: str = Form(None),
    remarks: str = Form(None),
    status: str = Form(None),
    db: Session = Depends(get_db),
    user_id: Optional[str] = Cookie(None)
):
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
    current_user_id = int(user_id)
    item_data = {
        "taste": taste,
        "preferred_time": preferred_time,
        "location": location,
        "ingredients": ingredients,
        "remarks": remarks
    }
    if status:
        item_data["status"] = status
    crud.update_order_item(db, item_id, item_data, current_user_id)
    return RedirectResponse(url="/my-orders", status_code=303)

@app.post("/complete-item/{item_id}")
async def complete_item(
    item_id: int,
    db: Session = Depends(get_db),
    user_id: Optional[str] = Cookie(None)
):
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
    current_user_id = int(user_id)
    crud.update_order_item(db, item_id, {"status": "completed"}, current_user_id)
    return RedirectResponse(url="/my-orders", status_code=303)

@app.post("/delay-item/{item_id}")
async def delay_item(
    item_id: int,
    db: Session = Depends(get_db),
    user_id: Optional[str] = Cookie(None)
):
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
    current_user_id = int(user_id)
    crud.update_order_item(db, item_id, {"status": "delayed"}, current_user_id)
    return RedirectResponse(url="/my-orders", status_code=303)

@app.post("/delete-item/{item_id}")
async def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    user_id: Optional[str] = Cookie(None)
):
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
    current_user_id = int(user_id)
    crud.delete_order_item(db, item_id, current_user_id)
    return RedirectResponse(url="/my-orders", status_code=303)

@app.post("/delete-order/{order_id}")
async def delete_order(
    order_id: int,
    db: Session = Depends(get_db),
    user_id: Optional[str] = Cookie(None)
):
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
    current_user_id = int(user_id)
    crud.delete_order(db, order_id, current_user_id)
    return RedirectResponse(url="/my-orders", status_code=303)

def delete_old_image(image_url: Optional[str]):
    if image_url and image_url.startswith("/static/uploads/"):
        relative_path = image_url.lstrip("/")
        if os.path.exists(relative_path):
            os.remove(relative_path)

@app.post("/update-dish/{dish_id}")
async def update_dish(
    dish_id: int,
    name: str = Form(...),
    description: str = Form(None),
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
    user_id: Optional[str] = Cookie(None)
):
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
    current_user_id = int(user_id)
    dish_data = {"name": name, "description": description}
    
    if file and file.filename:
        # Get old dish to delete old image
        old_dish = crud.get_dish(db, dish_id)
        if old_dish and old_dish.image_url:
            delete_old_image(old_dish.image_url)

        file_extension = os.path.splitext(file.filename)[1]
        filename = f"{uuid.uuid4()}{file_extension}"
        filepath = os.path.join("static/uploads", filename)
        os.makedirs("static/uploads", exist_ok=True)
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        dish_data["image_url"] = f"/static/uploads/{filename}"
    
    crud.update_dish(db, dish_id, dish_data, current_user_id)
    return RedirectResponse(url="/", status_code=303)

@app.post("/delete-dish/{dish_id}")
async def delete_dish(
    dish_id: int,
    db: Session = Depends(get_db),
    user_id: Optional[str] = Cookie(None)
):
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
    current_user_id = int(user_id)
    # We keep the image for soft-deleted dishes in audit logs usually, 
    # but if needed we could delete it here. Since it's a soft delete, 
    # we'll keep the image so it shows up in history/logs if needed.
    crud.delete_dish(db, dish_id, current_user_id)
    return RedirectResponse(url="/", status_code=303)
