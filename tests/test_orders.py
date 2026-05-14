from app import crud, schemas


def _login(client, db):
    crud.create_user(db, schemas.UserCreate(name="testuser", password="666"))
    user = crud.get_user_by_name(db, "testuser")
    user.role = "admin"
    db.commit()
    token = "test-csrf-token"
    client.cookies.set("csrf_token", token)
    client.post("/login", data={"name": "testuser", "password": "666", "csrf_token": token})


def _csrf(client):
    token = "test-csrf-token"
    client.cookies.set("csrf_token", token)
    return token


def test_order_page_creates_order_if_none(client, db):
    _login(client, db)
    response = client.get("/order")
    assert response.status_code == 200
    order = crud.get_current_order(db)
    assert order is not None
    assert order.status == "open"


def test_add_item_to_order(client, db):
    _login(client, db)
    user = crud.get_user_by_name(db, "testuser")
    dish = crud.create_dish(db, schemas.DishCreate(name="Test Dish", created_by=user.id))
    token = _csrf(client)
    response = client.post(
        "/add-item",
        data={"dish_id": dish.id, "taste": "Spicy", "remarks": "Extra spicy", "csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    order = crud.get_current_order(db)
    assert len(order.items) == 1
    assert order.items[0].dish_id == dish.id


def test_add_item_without_login_redirects(client, db):
    token = _csrf(client)
    response = client.post(
        "/add-item",
        data={"dish_id": 1, "csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_my_orders_page(client, db):
    _login(client, db)
    response = client.get("/my-orders")
    assert response.status_code == 200


def test_complete_item(client, db):
    _login(client, db)
    user = crud.get_user_by_name(db, "testuser")
    dish = crud.create_dish(db, schemas.DishCreate(name="Test Dish", created_by=user.id))
    order = crud.get_or_create_current_order(db, user.id)
    item = crud.add_order_item(db, schemas.OrderItemCreate(
        order_id=order.id, dish_id=dish.id, user_id=user.id,
    ))
    token = _csrf(client)
    response = client.post(f"/complete-item/{item.id}", data={"csrf_token": token}, follow_redirects=False)
    assert response.status_code == 303
    updated = crud.get_dish(db, dish.id)
    assert updated is not None


def test_delay_item(client, db):
    _login(client, db)
    user = crud.get_user_by_name(db, "testuser")
    dish = crud.create_dish(db, schemas.DishCreate(name="Test Dish", created_by=user.id))
    order = crud.get_or_create_current_order(db, user.id)
    item = crud.add_order_item(db, schemas.OrderItemCreate(
        order_id=order.id, dish_id=dish.id, user_id=user.id,
    ))
    token = _csrf(client)
    response = client.post(f"/delay-item/{item.id}", data={"csrf_token": token}, follow_redirects=False)
    assert response.status_code == 303


def test_delete_item(client, db):
    _login(client, db)
    user = crud.get_user_by_name(db, "testuser")
    dish = crud.create_dish(db, schemas.DishCreate(name="Test Dish", created_by=user.id))
    order = crud.get_or_create_current_order(db, user.id)
    item = crud.add_order_item(db, schemas.OrderItemCreate(
        order_id=order.id, dish_id=dish.id, user_id=user.id,
    ))
    token = _csrf(client)
    response = client.post(f"/delete-item/{item.id}", data={"csrf_token": token}, follow_redirects=False)
    assert response.status_code == 303
    order = crud.get_current_order(db)
    assert len(order.items) == 0


def test_delete_order(client, db):
    _login(client, db)
    user = crud.get_user_by_name(db, "testuser")
    order = crud.get_or_create_current_order(db, user.id)
    token = _csrf(client)
    response = client.post(f"/delete-order/{order.id}", data={"csrf_token": token}, follow_redirects=False)
    assert response.status_code == 303
    assert crud.get_current_order(db) is None


def test_update_item(client, db):
    _login(client, db)
    user = crud.get_user_by_name(db, "testuser")
    dish = crud.create_dish(db, schemas.DishCreate(name="Test Dish", created_by=user.id))
    order = crud.get_or_create_current_order(db, user.id)
    item = crud.add_order_item(db, schemas.OrderItemCreate(
        order_id=order.id, dish_id=dish.id, user_id=user.id,
    ))
    token = _csrf(client)
    response = client.post(
        f"/update-item/{item.id}",
        data={"taste": "Mild", "remarks": "Less spicy", "csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_update_nonexistent_item_returns_404(client, db):
    _login(client, db)
    token = _csrf(client)
    response = client.post(
        "/update-item/99999",
        data={"csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 404


def test_complete_nonexistent_item_returns_404(client, db):
    _login(client, db)
    token = _csrf(client)
    response = client.post("/complete-item/99999", data={"csrf_token": token}, follow_redirects=False)
    assert response.status_code == 404


def test_delete_nonexistent_item_returns_404(client, db):
    _login(client, db)
    token = _csrf(client)
    response = client.post("/delete-item/99999", data={"csrf_token": token}, follow_redirects=False)
    assert response.status_code == 404


def test_delete_nonexistent_order_returns_404(client, db):
    _login(client, db)
    token = _csrf(client)
    response = client.post("/delete-order/99999", data={"csrf_token": token}, follow_redirects=False)
    assert response.status_code == 404
