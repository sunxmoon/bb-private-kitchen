from app import crud, schemas


def test_post_without_csrf_is_rejected(client, db):
    crud.create_user(db, schemas.UserCreate(name="testuser", password="testpass666"))
    response = client.post(
        "/login",
        data={"name": "testuser", "password": "testpass666"},
        follow_redirects=False
    )
    assert response.status_code == 403


def test_post_with_wrong_csrf_is_rejected(client, db):
    crud.create_user(db, schemas.UserCreate(name="testuser", password="testpass666"))
    client.cookies.set("csrf_token", "real-token")
    response = client.post(
        "/login",
        data={"name": "testuser", "password": "testpass666", "csrf_token": "wrong-token"},
        follow_redirects=False
    )
    assert response.status_code == 403


def test_post_with_correct_csrf_succeeds(client, db):
    crud.create_user(db, schemas.UserCreate(name="testuser", password="testpass666"))
    client.cookies.set("csrf_token", "valid-token")
    response = client.post(
        "/login",
        data={"name": "testuser", "password": "testpass666", "csrf_token": "valid-token"},
        follow_redirects=False
    )
    assert response.status_code == 303


def test_get_requests_not_blocked(client, db):
    response = client.get("/login")
    assert response.status_code == 200
