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


def test_flash_message_display_and_clear(client, db):
    crud.create_user(db, schemas.UserCreate(name="flashuser", password="testpass666"))
    token = "test-csrf-token"
    client.cookies.set("csrf_token", token)
    client.post("/login", data={"name": "flashuser", "password": "testpass666", "csrf_token": token})

    # Trigger action with flash redirect
    from fastapi import APIRouter

    from app.dependencies import redirect_with_flash

    test_router = APIRouter()

    @test_router.get("/test-flash-action")
    def flash_action():
        return redirect_with_flash("/", "操作成功提示")

    client.app.include_router(test_router)

    response = client.get("/test-flash-action", follow_redirects=True)
    assert response.status_code == 200
    assert "操作成功提示" in response.text

    # Subsequent request should no longer have the flash message
    response2 = client.get("/")
    assert "操作成功提示" not in response2.text


def test_desktop_sidebar_and_navigation_links(client, db):
    crud.create_user(db, schemas.UserCreate(name="navuser", password="testpass666"))
    token = "test-csrf-token"
    client.cookies.set("csrf_token", token)
    client.post("/login", data={"name": "navuser", "password": "testpass666", "csrf_token": token})

    response = client.get("/")
    assert response.status_code == 200
    html = response.text

    # Assert desktop sidebar classes
    assert "sidebar-desktop" in html
    assert "md:flex" in html

    # Assert desktop navigation items
    assert "今日菜单" in html
    assert "点餐中心" in html
    assert "实时订单" in html
    assert "采购清单" in html
    assert "点单记录" in html

    # Assert user profile, settings and logout controls
    assert "navuser" in html
    assert "家庭成员" in html
    assert "/settings" in html
    assert "/logout" in html

