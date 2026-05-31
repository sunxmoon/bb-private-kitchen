from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    theme_color = Column(String(20), default="#f97316")
    role = Column(String(20), default="user", nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    dishes = relationship("Dish", back_populates="creator")
    orders = relationship("Order", back_populates="creator")
    order_items = relationship("OrderItem", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")
    recipes = relationship("Recipe", back_populates="generator")


class Dish(Base):
    __tablename__ = "dishes"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    image_url = Column(String(512))
    category = Column(String(50), default="", server_default="")
    created_by = Column(Integer, ForeignKey("users.id"), index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    creator = relationship("User", back_populates="dishes")
    items = relationship("OrderItem", back_populates="dish")
    recipe = relationship("Recipe", back_populates="dish", uselist=False, cascade="all, delete-orphan")


class Recipe(Base):
    __tablename__ = "recipes"
    id = Column(Integer, primary_key=True, index=True)
    dish_id = Column(Integer, ForeignKey("dishes.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    content = Column(JSON, nullable=False)
    generated_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    dish = relationship("Dish", back_populates="recipe")
    generator = relationship("User", back_populates="recipes")


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    status = Column(String(50), default="open", index=True)
    created_by = Column(Integer, ForeignKey("users.id"), index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    creator = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    dish_id = Column(Integer, ForeignKey("dishes.id"), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    taste = Column(Text)
    preferred_time = Column(Text)
    location = Column(Text)
    ingredients = Column(Text)
    remarks = Column(Text)
    rating = Column(Integer)
    status = Column(String(50), default="pending", index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    order = relationship("Order", back_populates="items")
    dish = relationship("Dish", back_populates="items")
    user = relationship("User", back_populates="order_items")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(255), nullable=False)
    table_name = Column(String(50))
    record_id = Column(Integer)
    old_values = Column(JSON)
    new_values = Column(JSON)
    timestamp = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="audit_logs")
