from app import crud, schemas
from app.security import sign_cookie_value
from conftest import _login_admin as _login, _csrf


def test_users_page(client, db):
    _login(client, db)
    response = client.get("/admin")
    assert response.status_code == 200


def test_create_user_via_http(client, db):
    _login(client, db)
    token = _csrf(client)
    response = client.post(
        "/create-user",
        data={"name": "newuser", "password": "123456", "csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    user = crud.get_user_by_name(db, "newuser")
    assert user is not None
    assert user.name == "newuser"


def test_create_user_default_password(client, db):
    _login(client, db)
    token = _csrf(client)
    response = client.post(
        "/create-user",
        data={"name": "defaultpwd", "csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    user = crud.get_user_by_name(db, "defaultpwd")
    assert user is not None


def test_update_user_name(client, db):
    _login(client, db)
    target = crud.create_user(db, schemas.UserCreate(name="target", password="666"))
    token = _csrf(client)
    response = client.post(
        f"/update-user/{target.id}",
        data={"name": "updated", "csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    updated = crud.get_user(db, target.id)
    assert updated.name == "updated"


def test_update_nonexistent_user_returns_404(client, db):
    _login(client, db)
    token = _csrf(client)
    response = client.post(
        "/update-user/99999",
        data={"name": "ghost", "csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 404


def test_delete_user(client, db):
    _login(client, db)
    target = crud.create_user(db, schemas.UserCreate(name="todelete", password="666"))
    token = _csrf(client)
    response = client.post(
        f"/delete-user/{target.id}",
        data={"csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert crud.get_user(db, target.id) is None


def test_delete_self_is_blocked(client, db):
    user = crud.create_user(db, schemas.UserCreate(name="self", password="666"))
    user.role = "admin"
    db.commit()
    token = "test-csrf-token"
    client.cookies.set("csrf_token", token)
    client.cookies.set("user_id", sign_cookie_value(str(user.id)))
    response = client.post(
        f"/delete-user/{user.id}",
        data={"csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "self_delete" in response.headers["location"]
    assert crud.get_user(db, user.id) is not None


def test_delete_nonexistent_user_returns_404(client, db):
    _login(client, db)
    token = _csrf(client)
    response = client.post("/delete-user/99999", data={"csrf_token": token}, follow_redirects=False)
    assert response.status_code == 404


def test_users_page_requires_login(client, db):
    response = client.get("/admin", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
