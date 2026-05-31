from conftest import _login

from app import crud, schemas


def test_history_page_empty(client, db):
    _login(client, db)
    response = client.get("/history")
    assert response.status_code == 200


def test_history_page_with_data(client, db):
    _login(client, db)
    user = crud.get_user_by_name(db, "testuser")
    dish = crud.create_dish(db, schemas.DishCreate(name="Hist Dish", created_by=user.id))
    order = crud.create_order(db, schemas.OrderCreate(created_by=user.id))
    crud.add_order_item(db, schemas.OrderItemCreate(
        order_id=order.id, dish_id=dish.id, user_id=user.id,
    ))
    response = client.get("/history")
    assert response.status_code == 200


def test_get_or_create_current_order_creates_if_missing(db):
    user = crud.create_user(db, schemas.UserCreate(name="noorder", password="testpass666"))
    order = crud.get_or_create_current_order(db, user.id)
    assert order is not None
    assert order.status == "open"
    assert order.created_by == user.id


def test_get_or_create_current_order_returns_existing(db):
    user = crud.create_user(db, schemas.UserCreate(name="hasorder", password="testpass666"))
    order1 = crud.get_or_create_current_order(db, user.id)
    order2 = crud.get_or_create_current_order(db, user.id)
    assert order1.id == order2.id


def test_get_order_history_count(db):
    user = crud.create_user(db, schemas.UserCreate(name="counter", password="testpass666"))
    assert crud.get_order_history_count(db) == 0
    crud.create_order(db, schemas.OrderCreate(created_by=user.id))
    assert crud.get_order_history_count(db) == 1


def test_get_audit_logs(db):
    user = crud.create_user(db, schemas.UserCreate(name="logger", password="testpass666"))
    crud.create_dish(db, schemas.DishCreate(name="Log Dish", created_by=user.id))
    logs = crud.get_audit_logs(db)
    assert len(logs) > 0
