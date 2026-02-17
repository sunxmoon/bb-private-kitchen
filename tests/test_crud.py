import pytest
from app import crud, schemas

def test_create_dish(db):
    user = crud.create_user(db, schemas.UserCreate(name="chef", password="666"))
    dish_in = schemas.DishCreate(name="Mapo Tofu", description="Spicy", created_by=user.id)
    dish = crud.create_dish(db, dish_in)
    assert dish.name == "Mapo Tofu"
