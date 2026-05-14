from app import crud, schemas


def _csrf(client):
    client.cookies.set("csrf_token", "test-csrf-token")
    return "test-csrf-token"


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


def test_get_order_history_count(db):
    user = crud.create_user(db, schemas.UserCreate(name="testuser", password="666"))
    assert crud.get_order_history_count(db) == 0
    crud.create_order(db, schemas.OrderCreate(created_by=user.id))
    assert crud.get_order_history_count(db) == 1
