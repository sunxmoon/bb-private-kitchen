import asyncio

from app import crud, schemas
from app.broadcaster import order_broadcaster


def _csrf(client):
    token = "test-csrf-token"
    client.cookies.set("csrf_token", token)
    return token


def _login_admin(client, db):
    crud.create_user(db, schemas.UserCreate(name="testadmin", password="testpass666"))
    user = crud.get_user_by_name(db, "testadmin")
    user.role = "admin"
    db.commit()
    token = _csrf(client)
    client.post("/login", data={"name": "testadmin", "password": "testpass666", "csrf_token": token})
    return user


def test_shopping_list_categories(client, db):
    admin_user = _login_admin(client, db)

    # Create some dishes and order items to test categorizations
    from app.models import Dish, Order, OrderItem, Recipe

    # 1. Dish with meat
    dish_meat = Dish(name="Test Meat", created_by=admin_user.id, is_active=True)
    db.add(dish_meat)
    db.flush()
    recipe_meat = Recipe(
        dish_id=dish_meat.id, content={"ingredients": [{"name": "猪肉", "amount": "1斤"}]}, generated_by=admin_user.id
    )
    db.add(recipe_meat)

    # 2. Dish with veg
    dish_veg = Dish(name="Test Veg", created_by=admin_user.id, is_active=True)
    db.add(dish_veg)
    db.flush()
    recipe_veg = Recipe(
        dish_id=dish_veg.id, content={"ingredients": [{"name": "白菜", "amount": "2颗"}]}, generated_by=admin_user.id
    )
    db.add(recipe_veg)

    # Create order
    order = Order(status="open", created_by=admin_user.id)
    db.add(order)
    db.flush()

    item1 = OrderItem(order_id=order.id, dish_id=dish_meat.id, user_id=admin_user.id, status="pending")
    item2 = OrderItem(order_id=order.id, dish_id=dish_veg.id, user_id=admin_user.id, status="pending")
    db.add_all([item1, item2])
    db.commit()

    # Test shopping list endpoint
    response = client.get("/shopping-list")
    assert response.status_code == 200
    html = response.text

    # Check that categories are present
    assert "肉禽类" in html
    assert "蔬菜菌菇" in html
    assert "猪肉" in html
    assert "白菜" in html


def test_token_revocation(client, db):
    crud.create_user(db, schemas.UserCreate(name="testuser", password="testpass666"))
    test_user = crud.get_user_by_name(db, "testuser")
    token = _csrf(client)

    # Initial login
    response = client.post(
        "/login", data={"name": "testuser", "password": "testpass666", "csrf_token": token}, follow_redirects=False
    )
    assert response.status_code == 303
    cookie = response.cookies.get("user_id")
    assert cookie is not None

    # Access page
    resp = client.get("/")
    assert resp.status_code == 200

    # Change password
    crud.update_user(db, test_user.id, {"password": "newpassword123"}, test_user.id)

    # Token should be invalid now
    resp = client.get("/my-orders", follow_redirects=False)
    assert resp.status_code == 303
    assert "/login" in resp.headers["Location"]


def test_sse_broadcaster():
    # Test the broadcaster queue mechanism synchronously using asyncio.run
    async def subscriber_test():
        task = asyncio.create_task(order_broadcaster.subscribe().__anext__())
        await asyncio.sleep(0.01)  # Let subscriber start

        order_broadcaster.loop = asyncio.get_running_loop()
        order_broadcaster.broadcast("update")

        msg = await task
        assert msg == "data: update\n\n"

    asyncio.run(subscriber_test())


def test_upload_webp_dish_image(client, db):
    import io

    from app.dependencies import delete_old_image

    _login_admin(client, db)
    # Minimal 1x1 WebP byte sequence
    fake_webp_bytes = b"RIFF\x1a\x00\x00\x00WEBPVP8 \x0e\x00\x00\x00\x30\x01\x00\x9d\x01\x2a\x01\x00\x01\x00\x02\x00\x34\x25"
    token = _csrf(client)
    files = {"file": ("dish.webp", io.BytesIO(fake_webp_bytes), "image/webp")}
    data = {
        "name": "WebP测试菜品",
        "description": "测试客户端WebP上传",
        "csrf_token": token,
    }
    resp = client.post("/create-dish", data=data, files=files, follow_redirects=False)
    assert resp.status_code == 303

    from app.models import Dish

    dish = db.query(Dish).filter(Dish.name == "WebP测试菜品").first()
    assert dish is not None
    assert dish.image_url is not None
    assert dish.image_url.endswith(".webp")

    delete_old_image(dish.image_url)


def test_batch_add_items(client, db):
    user = _login_admin(client, db)
    token = _csrf(client)

    from app.models import Dish, OrderItem

    dish1 = Dish(name="批量菜品1", created_by=user.id, is_active=True)
    dish2 = Dish(name="批量菜品2", created_by=user.id, is_active=True)
    db.add_all([dish1, dish2])
    db.commit()

    payload = {
        "items": [
            {"dish_id": dish1.id, "quantity": 2, "taste": "微辣", "remarks": "多葱"},
            {"dish_id": dish2.id, "quantity": 1, "taste": "不辣"},
        ],
        "global_location": "餐厅",
        "global_time": "18:00",
    }

    resp = client.post("/api/orders/batch", json=payload, headers={"X-CSRF-Token": token})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["added_count"] == 3

    # Verify records in database
    items = db.query(OrderItem).filter(OrderItem.order_id == data["order_id"]).all()
    assert len(items) == 3
    tastes = [it.taste for it in items]
    assert tastes.count("微辣") == 2
    assert tastes.count("不辣") == 1
    assert all(it.location == "餐厅" for it in items)
    assert all(it.preferred_time == "18:00" for it in items)
