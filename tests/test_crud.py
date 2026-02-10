import pytest
from app import crud, schemas

def test_create_dish(db):
    user = crud.create_user(db, schemas.UserCreate(name="chef", password="666"))
    dish_in = schemas.DishCreate(name="Mapo Tofu", description="Spicy", created_by=user.id)
    dish = crud.create_dish(db, dish_in)
    assert dish.name == "Mapo Tofu"
    assert dish.created_by == user.id

def test_get_dishes(db):
    user = crud.create_user(db, schemas.UserCreate(name="chef", password="666"))
    crud.create_dish(db, schemas.DishCreate(name="Dish 1", created_by=user.id))
    crud.create_dish(db, schemas.DishCreate(name="Dish 2", created_by=user.id))
    dishes = crud.get_dishes(db)
    assert len(dishes) == 2

def test_update_dish(db):
    user = crud.create_user(db, schemas.UserCreate(name="chef", password="666"))
    dish = crud.create_dish(db, schemas.DishCreate(name="Old Name", created_by=user.id))
    updated_dish = crud.update_dish(db, dish.id, {"name": "New Name"}, user.id)
    assert updated_dish.name == "New Name"

def test_delete_dish(db):
    user = crud.create_user(db, schemas.UserCreate(name="chef", password="666"))
    dish = crud.create_dish(db, schemas.DishCreate(name="To Delete", created_by=user.id))
    crud.delete_dish(db, dish.id, user.id)
    dishes = crud.get_dishes(db)
    assert len(dishes) == 0 # Soft delete filter works