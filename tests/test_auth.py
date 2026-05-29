from app import crud, schemas
from conftest import _csrf


def test_login_success(client, db):
    user_in = schemas.UserCreate(name="testuser", password="password123")
    crud.create_user(db, user_in)
    token = _csrf(client)
    response = client.post(
        "/login",
        data={"name": "testuser", "password": "password123", "csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_login_failure(client, db):
    crud.create_user(db, schemas.UserCreate(name="testuser", password="password123"))
    token = _csrf(client)
    response = client.post(
        "/login",
        data={"name": "testuser", "password": "wrongpassword", "csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "error" in response.headers["location"]


def test_logout(client, db):
    crud.create_user(db, schemas.UserCreate(name="testuser", password="password123"))
    token = _csrf(client)
    client.post("/login", data={"name": "testuser", "password": "password123", "csrf_token": token})
    response = client.get("/logout", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
