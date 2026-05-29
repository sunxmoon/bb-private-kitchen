from datetime import datetime
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class UserBase(BaseModel):
    name: str = Field(min_length=1, max_length=50)

class UserCreate(UserBase):
    password: str = "666"

class UserUpdate(BaseModel):
    name: Optional[str] = None
    password: Optional[str] = None
    theme_color: Optional[str] = None
    role: Optional[Literal["admin", "user"]] = None

class User(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    theme_color: Optional[str] = "#f97316"
    role: str = "user"
    created_at: datetime

class DishBase(BaseModel):
    name: str
    description: Optional[str] = None
    image_url: Optional[str] = None

class DishCreate(DishBase):
    created_by: int

class Dish(DishBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_by: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

class OrderItemBase(BaseModel):
    dish_id: int
    user_id: int
    taste: Optional[str] = None
    preferred_time: Optional[str] = None
    location: Optional[str] = None
    ingredients: Optional[str] = None
    remarks: Optional[str] = None
    status: Optional[str] = "pending"

class OrderItemCreate(OrderItemBase):
    order_id: int

class OrderItem(OrderItemBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    order_id: int
    created_at: datetime
    updated_at: datetime

class OrderBase(BaseModel):
    status: str = "open"

class OrderCreate(OrderBase):
    created_by: int

class Order(OrderBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_by: int
    created_at: datetime
    updated_at: datetime
    items: List[OrderItem] = []

class AuditLogBase(BaseModel):
    user_id: int
    action: str
    table_name: str
    record_id: int
    old_values: Optional[Any] = None
    new_values: Optional[Any] = None

class RecipeIngredient(BaseModel):
    name: str
    amount: str

class RecipeContent(BaseModel):
    ingredients: List[RecipeIngredient]
    steps: List[str]
    cook_time: str
    difficulty: str
    tips: Optional[str] = None

class RecipeBase(BaseModel):
    dish_id: int
    content: RecipeContent
    generated_by: int

class RecipeCreate(RecipeBase):
    pass

class Recipe(RecipeBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime

class AuditLog(AuditLogBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    timestamp: datetime
