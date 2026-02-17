import pytest
from app import crud, schemas

def test_login_success(client, db):
    user_in = schemas.UserCreate(name="testuser", password="password123")
    crud.create_user(db, user_in)
    response = client.post("/login", data={"name": "testuser", "password": "password123"}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"
