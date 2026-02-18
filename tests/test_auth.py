import pytest
from app import crud, schemas, security

def test_login_success(client, db):
    # Create a user
    user_in = schemas.UserCreate(name="testuser", password="password123")
    crud.create_user(db, user_in)
    
    # Try to login
    response = client.post(
        "/login",
        data={"name": "testuser", "password": "password123"},
        follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "user_id" in response.cookies

def test_login_failure(client, db):
    # Create a user
    user_in = schemas.UserCreate(name="testuser", password="password123")
    crud.create_user(db, user_in)
    
    # Try to login with wrong password
    response = client.post(
        "/login",
        data={"name": "testuser", "password": "wrongpassword"},
        follow_redirects=False
    )
    assert response.status_code == 303
    assert "/login?error=1" in response.headers["location"]
    assert "user_id" not in response.cookies

def test_logout(client):
    # Set a cookie
    client.cookies.set("user_id", "1")
    response = client.get("/logout", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    
    # Check if Set-Cookie header is present
    set_cookie = response.headers.get("set-cookie")
    assert set_cookie is not None
    assert 'user_id=;' in set_cookie or 'user_id=""' in set_cookie or 'Max-Age=0' in set_cookie
