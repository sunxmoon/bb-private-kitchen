from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime

class UserBase(BaseModel):
    name: str

class UserCreate(UserBase):
    password: str = "666"

class UserUpdate(BaseModel):
    name: Optional[str] = None
    password: Optional[str] = None

class User(UserBase):
    id: int
    created_at: datetime
    class Config:
        orm_mode = True

class DishBase(BaseModel):
    name: str
    description: Optional[str] = None
    image_url: Optional[str] = None

class DishCreate(DishBase):
    created_by: int

class Dish(DishBase):
    id: int
    created_by: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    class Config:
        orm_mode = True

class OrderItemBase(BaseModel):
    dish_id: int
    user_id: int
    taste: Optional[str] = None
    preferred_time: Optional[str] = None
    location: Optional[str] = None
    ingredients: Optional[str] = None
    remarks: Optional[str] = None
    status: Optional[str] = "pending"
    custom_data: Optional[Any] = None

class OrderItemCreate(OrderItemBase):
    order_id: int

class OrderItem(OrderItemBase):
    id: int
    order_id: int
    created_at: datetime
    updated_at: datetime
    class Config:
        orm_mode = True

class OrderBase(BaseModel):
    status: str = "open"

class OrderCreate(OrderBase):
    created_by: int

class Order(OrderBase):
    id: int
    created_by: int
    created_at: datetime
    updated_at: datetime
    items: List[OrderItem] = []
    class Config:
        orm_mode = True

class AuditLogBase(BaseModel):
    user_id: int
    action: str
    table_name: str
    record_id: int
    old_values: Optional[Any] = None
    new_values: Optional[Any] = None

class AuditLog(AuditLogBase):
    id: int
    timestamp: datetime
    class Config:
        orm_mode = True
