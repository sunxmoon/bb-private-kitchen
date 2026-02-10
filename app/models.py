from sqlalchemy import Column, Integer, String, Text, ForeignKey, Boolean, DateTime, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    password = Column(String(255), nullable=False, default="666")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    dishes = relationship("Dish", back_populates="creator")
    orders = relationship("Order", back_populates="creator")
    order_items = relationship("OrderItem", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")

class Dish(Base):
    __tablename__ = "dishes"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    image_url = Column(String(512))
    created_by = Column(Integer, ForeignKey("users.id"), index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    creator = relationship("User", back_populates="dishes")
    items = relationship("OrderItem", back_populates="dish")

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    status = Column(String(50), default="open")
    created_by = Column(Integer, ForeignKey("users.id"), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

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
    status = Column(String(50), default="pending")  # pending, completed, delayed
    custom_data = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

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
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="audit_logs")
