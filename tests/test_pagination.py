from app import crud, schemas
from conftest import _csrf


def test_history_pagination_defaults_to_page_1(client, db):
    crud.create_user(db, schemas.UserCreate(name="testuser", password="666"))
    token = _csrf(client)
    client.post("/login", data={"name": "testuser", "password": "666", "csrf_token": token})
    response = client.get("/admin")
    assert response.status_code == 200


def test_history_pagination_with_page_param(client, db):
    crud.create_user(db, schemas.UserCreate(name="testuser", password="666"))
    token = _csrf(client)
    client.post("/login", data={"name": "testuser", "password": "666", "csrf_token": token})
    response = client.get("/admin?page=1")
    assert response.status_code == 200


def test_order_history_count_increments(db):
    user = crud.create_user(db, schemas.UserCreate(name="testuser", password="666"))
    assert crud.get_order_history_count(db) == 0
    crud.create_order(db, schemas.OrderCreate(created_by=user.id))
    assert crud.get_order_history_count(db) == 1
