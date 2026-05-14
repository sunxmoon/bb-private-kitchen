from app import crud, schemas


def _csrf(client):
    client.cookies.set("csrf_token", "test-csrf-token")
    return "test-csrf-token"


def test_login_success(client, db):
    user_in = schemas.UserCreate(name="testuser", password="password123")
    crud.create_user(db, user_in)
    token = _csrf(client)
    response = client.post(
        "/login",
        data={"name": "testuser", "password": "password123", "csrf_token": token},
        follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "user_id" in response.cookies


def test_login_failure(client, db):
    user_in = schemas.UserCreate(name="testuser", password="password123")
    crud.create_user(db, user_in)
    token = _csrf(client)
    response = client.post(
        "/login",
        data={"name": "testuser", "password": "wrongpassword", "csrf_token": token},
        follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/login?error=wrong_password"
    assert "user_id" not in response.cookies


def test_logout(client):
    client.cookies.set("user_id", "1")
    response = client.get("/logout", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    set_cookie = response.headers.get("set-cookie")
    assert set_cookie is not None
    assert 'user_id=;' in set_cookie or 'user_id=""' in set_cookie or 'Max-Age=0' in set_cookie
