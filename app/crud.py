from datetime import datetime, timedelta
from typing import Any, Dict

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from . import models, schemas, security

SENSITIVE_FIELDS = {"password", "token", "secret"}

def json_serializable(data: Dict[str, Any]):
    """Convert non-serializable objects (like datetime) to strings, filtering sensitive fields."""
    if not data:
        return data
    serializable_data = {}
    for key, value in data.items():
        if key in SENSITIVE_FIELDS:
            continue
        if isinstance(value, datetime):
            serializable_data[key] = value.isoformat()
        else:
            serializable_data[key] = value
    return serializable_data

def create_audit_log(
    db: Session, user_id: int, action: str, table_name: str, record_id: int,
    old_values: Dict[str, Any] = None, new_values: Dict[str, Any] = None, commit: bool = True,
):
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
        return None
    if not security.verify_password(password, user.password):
        return None
    return user

def get_users(db: Session):
    return db.query(models.User).all()

def create_user(db: Session, user: schemas.UserCreate, actor_id: int = 0):
    hashed_password = security.get_password_hash(user.password)
    db_user = models.User(name=user.name, password=hashed_password)
    db.add(db_user)
    db.flush() # Get ID before commit
    create_audit_log(db, actor_id or db_user.id, "创建用户", "users", db_user.id, None, {"name": db_user.name}, commit=False)
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
    return db.query(models.Dish).options(selectinload(models.Dish.recipe)).filter(models.Dish.is_active).all()

def get_dish(db: Session, dish_id: int):
    return db.query(models.Dish).filter(models.Dish.id == dish_id).first()

def create_dish(db: Session, dish: schemas.DishCreate):
    # Idempotency check: Don't create same dish twice in 10 seconds
    now = datetime.now()
    ten_seconds_ago = now - timedelta(seconds=10)
    existing = db.query(models.Dish).filter(
        models.Dish.name == dish.name,
        models.Dish.created_by == dish.created_by,
        models.Dish.created_at >= ten_seconds_ago
    ).first()
    if existing:
        return existing

    db_dish = models.Dish(**dish.model_dump(), created_at=now)
    db.add(db_dish)
    db.flush()
    create_audit_log(
        db, dish.created_by, f"创造了新菜《{db_dish.name}》", "dishes", db_dish.id, None, dish.model_dump(), commit=False,
    )
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
    create_audit_log(db, user_id, f"修改了菜品《{db_dish.name}》", "dishes", dish_id, old_values, new_values, commit=False)
    db.commit()
    db.refresh(db_dish)
    return db_dish

def delete_dish(db: Session, dish_id: int, user_id: int):
    db_dish = db.query(models.Dish).filter(models.Dish.id == dish_id).first()
    if not db_dish:
        return None

    pending = db.query(models.OrderItem).filter(
        models.OrderItem.dish_id == dish_id,
        models.OrderItem.status.in_(["pending", "delayed"])
    ).count()
    if pending > 0:
        raise ValueError(f"该菜品还有 {pending} 个未完成的点单，无法下架")

    old_values = {c.name: getattr(db_dish, c.name) for c in db_dish.__table__.columns}
    db_dish.is_active = False
    create_audit_log(
        db, user_id, f"下架了菜品《{db_dish.name}》", "dishes", dish_id, old_values, {"is_active": False}, commit=False,
    )
    db.commit()
    return db_dish

# Order CRUD
def get_current_order(db: Session):
    return db.query(models.Order).options(
        selectinload(models.Order.items).selectinload(models.OrderItem.dish),
        selectinload(models.Order.items).selectinload(models.OrderItem.user),
    ).filter(models.Order.status == "open").order_by(models.Order.created_at.desc()).first()

def get_or_create_current_order(db: Session, user_id: int):
        order = get_current_order(db)
        if not order:
            order = models.Order(status="open", created_by=user_id)
            db.add(order)
            db.flush()
            create_audit_log(
                db, user_id, "创建订单", "orders", order.id, None, {"status": "open", "created_by": user_id}, commit=False,
            )
            db.commit()
            db.refresh(order)
        return order

def create_order(db: Session, order: schemas.OrderCreate):
    db_order = models.Order(**order.model_dump())
    db.add(db_order)
    db.flush()
    create_audit_log(db, order.created_by, "创建订单", "orders", db_order.id, None, order.model_dump(), commit=False)
    db.commit()
    db.refresh(db_order)
    return db_order

def add_order_item(db: Session, item: schemas.OrderItemCreate):
    # Idempotency check: Don't allow same user to add same dish with same remarks in 10 seconds
    now = datetime.now()
    ten_seconds_ago = now - timedelta(seconds=10)
    existing = db.query(models.OrderItem).filter(
        models.OrderItem.order_id == item.order_id,
        models.OrderItem.dish_id == item.dish_id,
        models.OrderItem.user_id == item.user_id,
        models.OrderItem.remarks == item.remarks,
        models.OrderItem.created_at >= ten_seconds_ago
    ).first()

    if existing:
        return existing

    db_item = models.OrderItem(**item.model_dump(), created_at=now)
    db.add(db_item)
    db.flush()

    # Enrich log with dish name
    dish = get_dish(db, item.dish_id)
    dish_name = dish.name if dish else "未知菜品"
    new_values = item.model_dump()
    new_values["dish_name"] = dish_name

    create_audit_log(db, item.user_id, f"点了《{dish_name}》", "order_items", db_item.id, None, new_values, commit=False)
    db.commit()
    db.refresh(db_item)
    return db_item


def get_order_item(db: Session, item_id: int):
    return db.query(models.OrderItem).filter(models.OrderItem.id == item_id).first()


ORDER_ITEM_EDITABLE_FIELDS = {"taste", "preferred_time", "location", "ingredients", "remarks", "status"}

def update_order_item(db: Session, item_id: int, item_data: Dict[str, Any], user_id: int):
    db_item = db.query(models.OrderItem).filter(models.OrderItem.id == item_id).first()
    if not db_item:
        return None

    old_values = {c.name: getattr(db_item, c.name) for c in db_item.__table__.columns}
    for key, value in item_data.items():
        if key in ORDER_ITEM_EDITABLE_FIELDS:
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

def complete_order(db: Session, order_id: int, user_id: int):
    db_order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not db_order:
        return None
    old_values = {c.name: getattr(db_order, c.name) for c in db_order.__table__.columns}
    db_order.status = "completed"
    new_values = {c.name: getattr(db_order, c.name) for c in db_order.__table__.columns}
    create_audit_log(db, user_id, "完成了订单", "orders", order_id, old_values, new_values, commit=False)
    db.commit()
    return db_order

PAGE_SIZE = 20

def get_order_history(db: Session, page: int = 1, limit: int = None):
    fetch_limit = limit or PAGE_SIZE
    return (
        db.query(models.Order)
        .options(
            selectinload(models.Order.items).selectinload(models.OrderItem.dish),
            selectinload(models.Order.items).selectinload(models.OrderItem.user),
        )
        .order_by(models.Order.created_at.desc())
        .offset((page - 1) * fetch_limit)
        .limit(fetch_limit)
        .all()
    )

def get_order_history_count(db: Session) -> int:
    return db.query(models.Order).count()

def get_audit_logs(db: Session, limit: int = 100):
    return db.query(models.AuditLog).order_by(models.AuditLog.timestamp.desc()).limit(limit).all()

def get_last_item_preference(db: Session, user_id: int, dish_id: int):
    return db.query(models.OrderItem)\
        .filter(models.OrderItem.user_id == user_id)\
        .filter(models.OrderItem.dish_id == dish_id)\
        .order_by(models.OrderItem.created_at.desc())\
        .first()

# Recipe CRUD
def get_recipe_by_dish(db: Session, dish_id: int):
    return db.query(models.Recipe).filter(models.Recipe.dish_id == dish_id).first()

def create_or_update_recipe(db: Session, dish_id: int, content: dict, user_id: int):
    existing = get_recipe_by_dish(db, dish_id)
    dish = get_dish(db, dish_id)
    dish_name = dish.name if dish else f"菜品#{dish_id}"
    if existing:
        old = existing.content
        existing.content = content
        existing.generated_by = user_id
        create_audit_log(
            db, user_id, f"更新了《{dish_name}》的菜谱", "recipes", existing.id,
            {"content": old}, {"content": content}, commit=False,
        )
    else:
        existing = models.Recipe(dish_id=dish_id, content=content, generated_by=user_id)
        db.add(existing)
        db.flush()
        create_audit_log(
            db, user_id, f"为《{dish_name}》创建菜谱", "recipes", existing.id,
            None, {"content": content}, commit=False,
        )
    db.commit()
    db.refresh(existing)
    return existing


def get_order_stats(db: Session):
    """Get order statistics using SQL aggregation instead of loading all records."""
    total_orders = db.query(func.count(models.Order.id)).scalar() or 0
    total_items = db.query(func.count(models.OrderItem.id)).scalar() or 0

    top_dishes = (
        db.query(models.Dish.name, func.count(models.OrderItem.id).label("count"))
        .join(models.OrderItem, models.OrderItem.dish_id == models.Dish.id)
        .group_by(models.Dish.name)
        .order_by(func.count(models.OrderItem.id).desc())
        .limit(5)
        .all()
    )

    active_users = (
        db.query(models.User.name, func.count(models.OrderItem.id).label("count"))
        .join(models.OrderItem, models.OrderItem.user_id == models.User.id)
        .group_by(models.User.name)
        .order_by(func.count(models.OrderItem.id).desc())
        .limit(5)
        .all()
    )

    return {
        "total_orders": total_orders,
        "total_items": total_items,
        "top_dishes": [(name, count) for name, count in top_dishes],
        "active_users": [(name, count) for name, count in active_users],
    }
