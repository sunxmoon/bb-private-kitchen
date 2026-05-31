import pytest

from app import crud, schemas


def test_root_redirects_to_login_when_unauthenticated(client, db):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_order_redirects_to_login_when_unauthenticated(client, db):
    response = client.get("/order", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_my_orders_redirects_to_login_when_unauthenticated(client, db):
    response = client.get("/my-orders", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_history_redirects_to_login_when_unauthenticated(client, db):
    response = client.get("/history", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_get_preference_redirects_to_login_when_unauthenticated(client, db):
    response = client.get("/get-preference/1", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_crud_create_user_duplicate_name_raises(db):
    from sqlalchemy.exc import IntegrityError
    crud.create_user(db, schemas.UserCreate(name="unique", password="testpass666"))
    with pytest.raises(IntegrityError):
        crud.create_user(db, schemas.UserCreate(name="unique", password="testpass666"))


def test_crud_update_nonexistent_user(db):
    result = crud.update_user(db, 99999, {"name": "ghost"}, actor_id=1)
    assert result is None


def test_crud_delete_nonexistent_user(db):
    result = crud.delete_user(db, 99999, actor_id=1)
    assert result is None


def test_crud_get_nonexistent_dish(db):
    dish = crud.get_dish(db, 99999)
    assert dish is None


def test_crud_update_nonexistent_dish(db):
    result = crud.update_dish(db, 99999, {"name": "ghost"}, user_id=1)
    assert result is None


def test_crud_delete_nonexistent_dish(db):
    result = crud.delete_dish(db, 99999, user_id=1)
    assert result is None


def test_crud_get_last_preference_no_history(db):
    user = crud.create_user(db, schemas.UserCreate(name="test", password="testpass666"))
    dish = crud.create_dish(db, schemas.DishCreate(name="Dish", created_by=user.id))
    pref = crud.get_last_item_preference(db, user.id, dish.id)
    assert pref is None


def test_crud_order_item_nonexistent(db):
    result = crud.update_order_item(db, 99999, {"status": "completed"}, user_id=1)
    assert result is None
    result = crud.delete_order_item(db, 99999, user_id=1)
    assert result is None


def test_crud_delete_nonexistent_order(db):
    result = crud.delete_order(db, 99999, user_id=1)
    assert result is None


def test_json_serializable_with_sensitive(db):
    from app.crud import json_serializable
    data = {"name": "test", "password": "secret123", "email": "test@test.com"}
    result = json_serializable(data)
    assert "password" not in result
    assert result["name"] == "test"
    assert result["email"] == "test@test.com"
