from sqlalchemy.orm import Session
from . import models, schemas, security
from typing import Dict, Any, Optional
from datetime import datetime

def json_serializable(data: Dict[str, Any]):
    """Convert non-serializable objects (like datetime) to strings."""
    if not data:
        return data
    serializable_data = {}
    for key, value in data.items():
        if isinstance(value, datetime):
            serializable_data[key] = value.isoformat()
        else:
            serializable_data[key] = value
    return serializable_data

def create_audit_log(db: Session, user_id: int, action: str, table_name: str, record_id: int, old_values: Dict[str, Any] = None, new_values: Dict[str, Any] = None, commit: bool = True):
    db_log = models.AuditLog(
        user_id=user_id,
        action=action,
        table_name=table_name,
        record_id=record_id,
        old_values=json_serializable(old_values),
        new_values=json_serializable(new_values)
    )
    db.add(db_log)
    if commit:
        db.commit()

# User CRUD
def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_name(db: Session, name: str):
    return db.query(models.User).filter(models.User.name == name).first()

def authenticate_user(db: Session, name: str, password: str):
    user = get_user_by_name(db, name)
    if not user:
        return False
    if not security.verify_password(password, user.password):
        return False
    return user

def get_users(db: Session):
    return db.query(models.User).all()

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = security.get_password_hash(user.password)
    db_user = models.User(name=user.name, password=hashed_password)
    db.add(db_user)
    db.flush() # Get ID before commit
    create_audit_log(db, db_user.id, "创建用 户", "users", db_user.id, None, {"name": db_user.name}, commit=False)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user(db: Session, user_id: int, user_data: Dict[str, Any], actor_id: int):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        return None
    
    old_values = {c.name: getattr(db_user, c.name) for c in db_user.__table__.columns}
    
    if "password" in user_data and user_data["password"]:
        user_data["password"] = security.get_password_hash(user_data["password"])
    elif "password" in user_data:
        del user_data["password"] # Don't update if empty/None
        
    for key, value in user_data.items():
        if hasattr(db_user, key):
            setattr(db_user, key, value)
    
    new_values = {c.name: getattr(db_user, c.name) for c in db_user.__table__.columns}
    create_audit_log(db, actor_id, "更新用户", "users", user_id, old_values, new_values, commit=False)
    db.commit()
    db.refresh(db_user)
    return db_user

def delete_user(db: Session, user_id: int, actor_id: int):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        return None
    
    old_values = {c.name: getattr(db_user, c.name) for c in db_user.__table__.columns}
    db.delete(db_user)
    create_audit_log(db, actor_id, "删除用户", "users", user_id, old_values, None, commit=False)
    db.commit()
    return True

# Dish CRUD
def get_dishes(db: Session):
    return db.query(models.Dish).filter(models.Dish.is_active == True).all()

def get_dish(db: Session, dish_id: int):
    return db.query(models.Dish).filter(models.Dish.id == dish_id).first()

def create_dish(db: Session, dish: schemas.DishCreate):
    db_dish = models.Dish(**dish.model_dump())
    db.add(db_dish)
    db.flush()
    create_audit_log(db, dish.created_by, f" 创造了新菜《{db_dish.name}》", "dishes", db_dish.id, None, dish.model_dump(), commit=False)
    db.commit()
    db.refresh(db_dish)
    return db_dish

def update_dish(db: Session, dish_id: int, dish_data: Dict[str, Any], user_id: int):
    db_dish = db.query(models.Dish).filter(models.Dish.id == dish_id).first()
    if not db_dish:
        return None
    
    old_values = {c.name: getattr(db_dish, c.name) for c in db_dish.__table__.columns}
    for key, value in dish_data.items():
        setattr(db_dish, key, value)
    
    new_values = {c.name: getattr(db_dish, c.name) for c in db_dish.__table__.columns}
    create_audit_log(db, user_id, f"修改了菜 品《{db_dish.name}》", "dishes", dish_id, old_values, new_values, commit=False)
    db.commit()
    db.refresh(db_dish)
    return db_dish

def delete_dish(db: Session, dish_id: int, user_id: int):
    db_dish = db.query(models.Dish).filter(models.Dish.id == dish_id).first()
    if not db_dish:
        return None
    
    old_values = {c.name: getattr(db_dish, c.name) for c in db_dish.__table__.columns}
    db_dish.is_active = False
    create_audit_log(db, user_id, f"下架了菜 品《{db_dish.name}》", "dishes", dish_id, old_values, {"is_active": False}, commit=False)
    db.commit()
    return db_dish

# Order CRUD
def get_current_order(db: Session):
    return db.query(models.Order).filter(models.Order.status == "open").order_by(models.Order.created_at.desc()).first()

def create_order(db: Session, order: schemas.OrderCreate):
    db_order = models.Order(**order.model_dump())
    db.add(db_order)
    db.flush()
    create_audit_log(db, order.created_by, " 创建订单", "orders", db_order.id, None, order.model_dump(), commit=False)
    db.commit()
    db.refresh(db_order)
    return db_order

def add_order_item(db: Session, item: schemas.OrderItemCreate):
    db_item = models.OrderItem(**item.model_dump())
    db.add(db_item)
    db.flush()
    
    # Enrich log with dish name
    dish = get_dish(db, item.dish_id)
    dish_name = dish.name if dish else "未知 菜品"
    new_values = item.model_dump()
    new_values["dish_name"] = dish_name
    
    create_audit_log(db, item.user_id, f"点了《{dish_name}》", "order_items", db_item.id, None, new_values, commit=False)
    db.commit()
    db.refresh(db_item)
    return db_item

def update_order_item(db: Session, item_id: int, item_data: Dict[str, Any], user_id: int):
    db_item = db.query(models.OrderItem).filter(models.OrderItem.id == item_id).first()
    if not db_item:
        return None
    
    old_values = {c.name: getattr(db_item, c.name) for c in db_item.__table__.columns}
    for key, value in item_data.items():
        if key in old_values:
            setattr(db_item, key, value)
    
    # Enrich log with dish name
    dish_name = db_item.dish.name if db_item.dish else "未知菜品"
    new_values = {c.name: getattr(db_item, c.name) for c in db_item.__table__.columns}
    new_values["dish_name"] = dish_name
    
    create_audit_log(db, user_id, f"修改了《{dish_name}》", "order_items", item_id, old_values, new_values, commit=False)
    db.commit()
    db.refresh(db_item)
    return db_item

def delete_order_item(db: Session, item_id: int, user_id: int):
    db_item = db.query(models.OrderItem).filter(models.OrderItem.id == item_id).first()
    if not db_item:
        return None
    
    # Enrich log with dish name
    dish_name = db_item.dish.name if db_item.dish else "未知菜品"
    old_values = {c.name: getattr(db_item, c.name) for c in db_item.__table__.columns}
    old_values["dish_name"] = dish_name
    
    db.delete(db_item)
    create_audit_log(db, user_id, f"取消了《{dish_name}》", "order_items", item_id, old_values, None, commit=False)
    db.commit()
    return True

def delete_order(db: Session, order_id: int, user_id: int):
    db_order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not db_order:
        return None
    
    old_values = {c.name: getattr(db_order, c.name) for c in db_order.__table__.columns}
    db.query(models.OrderItem).filter(models.OrderItem.order_id == order_id).delete()
    db.delete(db_order)
    create_audit_log(db, user_id, "删除订单", "orders", order_id, old_values, None, commit=False)
    db.commit()
    return True

def get_order_history(db: Session):
    return db.query(models.Order).order_by(models.Order.created_at.desc()).all()

def get_audit_logs(db: Session):
    return db.query(models.AuditLog).order_by(models.AuditLog.timestamp.desc()).all()

def get_last_item_preference(db: Session, user_id: int, dish_id: int):
    return db.query(models.OrderItem)\
        .filter(models.OrderItem.user_id == user_id)\
        .filter(models.OrderItem.dish_id == dish_id)\
        .order_by(models.OrderItem.created_at.desc())\
        .first()
