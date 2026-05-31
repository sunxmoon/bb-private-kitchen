from app import crud, schemas


def test_order_page_has_dishes_for_picker(client, db):
    # Create a user and log in
    crud.create_user(db, schemas.UserCreate(name="testuser", password="testpass666"))
    token = "test-csrf-token"
    client.cookies.set("csrf_token", token)
    client.post("/login", data={"name": "testuser", "password": "testpass666", "csrf_token": token})

    # Create some dishes
    user = crud.get_user_by_name(db, "testuser")
    crud.create_dish(db, schemas.DishCreate(name="Dish 1", created_by=user.id))
    crud.create_dish(db, schemas.DishCreate(name="Dish 2", created_by=user.id))

    # Check order page
    response = client.get("/order")
    assert response.status_code == 200
    # Check if dish data for JS picker is present
    assert "Dish 1" in response.text
    assert "Dish 2" in response.text
    assert "dishNames" in response.text
    assert "dishIds" in response.text

def test_admin_page_tabs(client, db):
    # Login
    crud.create_user(db, schemas.UserCreate(name="admin", password="testpass666"))
    user = crud.get_user_by_name(db, "admin")
    user.role = "admin"
    db.commit()
    token = "test-csrf-token"
    client.cookies.set("csrf_token", token)
    client.post("/login", data={"name": "admin", "password": "testpass666", "csrf_token": token})

    response = client.get("/admin")
    assert response.status_code == 200
    assert "管理中心" in response.text
    assert "家庭成员" in response.text
    assert "全站点单记录" in response.text
    assert "系统操作日志" in response.text
    assert "tab-users-list" in response.text
    assert "tab-order-history" in response.text
    assert "tab-audit-logs" in response.text
