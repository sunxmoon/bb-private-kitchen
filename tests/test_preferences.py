import pytest
from app import crud, schemas

def test_get_preference(client, db):
    # Create user and dish
    user = crud.create_user(db, schemas.UserCreate(name="testuser", password="666"))
    dish = crud.create_dish(db, schemas.DishCreate(name="Test Dish", created_by=user.id))
    
    # Create an order item (last preference)
    order = crud.create_order(db, schemas.OrderCreate(created_by=user.id))
    item_in = schemas.OrderItemCreate(
        order_id=order.id,
        dish_id=dish.id,
        user_id=user.id,
        taste="Spicy",
        remarks="More onions"
    )
    crud.add_order_item(db, item_in)
    
    # Login
    client.post("/login", data={"name": "testuser", "password": "666"})
    
    # Get preference
    response = client.get(f"/get-preference/{dish.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["taste"] == "Spicy"
    assert data["remarks"] == "More onions"

def test_get_preference_no_record(client, db):
    user = crud.create_user(db, schemas.UserCreate(name="testuser", password="666"))
    dish = crud.create_dish(db, schemas.DishCreate(name="New Dish", created_by=user.id))
    
    client.post("/login", data={"name": "testuser", "password": "666"})
    
    response = client.get(f"/get-preference/{dish.id}")
    assert response.status_code == 200
    assert response.json() == {}
