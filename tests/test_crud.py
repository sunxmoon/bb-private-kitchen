from app import crud, schemas


def test_create_dish(db):
    user = crud.create_user(db, schemas.UserCreate(name="chef", password="testpass666"))
    dish_in = schemas.DishCreate(name="Mapo Tofu", description="Spicy", created_by=user.id)
    dish = crud.create_dish(db, dish_in)
    assert dish.name == "Mapo Tofu"
    assert dish.created_by == user.id


def test_get_dishes(db):
    user = crud.create_user(db, schemas.UserCreate(name="chef", password="testpass666"))
    crud.create_dish(db, schemas.DishCreate(name="Dish 1", created_by=user.id))
    crud.create_dish(db, schemas.DishCreate(name="Dish 2", created_by=user.id))
    dishes = crud.get_dishes(db)
    assert len(dishes) == 2


def test_update_dish(db):
    user = crud.create_user(db, schemas.UserCreate(name="chef", password="testpass666"))
    dish = crud.create_dish(db, schemas.DishCreate(name="Old Name", created_by=user.id))
    updated_dish = crud.update_dish(db, dish.id, {"name": "New Name"}, user.id)
    assert updated_dish.name == "New Name"


def test_delete_dish(db):
    user = crud.create_user(db, schemas.UserCreate(name="chef", password="testpass666"))
    dish = crud.create_dish(db, schemas.DishCreate(name="To Delete", created_by=user.id))
    crud.delete_dish(db, dish.id, user.id)
    dishes = crud.get_dishes(db)
    assert len(dishes) == 0


def test_get_dish_by_id(db):
    user = crud.create_user(db, schemas.UserCreate(name="chef", password="testpass666"))
    dish = crud.create_dish(db, schemas.DishCreate(name="Find Me", created_by=user.id))
    found = crud.get_dish(db, dish.id)
    assert found is not None
    assert found.name == "Find Me"


def test_get_nonexistent_dish(db):
    assert crud.get_dish(db, 99999) is None


def test_update_nonexistent_dish(db):
    result = crud.update_dish(db, 99999, {"name": "Ghost"}, user_id=1)
    assert result is None


def test_delete_nonexistent_dish(db):
    result = crud.delete_dish(db, 99999, user_id=1)
    assert result is None


def test_create_user_and_authenticate(db):
    crud.create_user(db, schemas.UserCreate(name="authuser", password="mypassword"))
    assert crud.authenticate_user(db, "authuser", "mypassword") is not None
    assert crud.authenticate_user(db, "authuser", "wrong") is None
    assert crud.authenticate_user(db, "nonexistent", "any") is None


def test_get_user_by_name(db):
    crud.create_user(db, schemas.UserCreate(name="finder", password="testpass666"))
    user = crud.get_user_by_name(db, "finder")
    assert user is not None
    assert user.name == "finder"
    assert crud.get_user_by_name(db, "ghost") is None


def test_get_users_list(db):
    crud.create_user(db, schemas.UserCreate(name="A", password="testpass666"))
    crud.create_user(db, schemas.UserCreate(name="B", password="testpass666"))
    users = crud.get_users(db)
    assert len(users) >= 2


def test_update_user_password(db):
    user = crud.create_user(db, schemas.UserCreate(name="passuser", password="oldpassword"))
    crud.update_user(db, user.id, {"password": "newpass"}, actor_id=user.id)
    assert crud.authenticate_user(db, "passuser", "newpass") is not None


def test_update_nonexistent_user(db):
    result = crud.update_user(db, 99999, {"name": "ghost"}, actor_id=1)
    assert result is None


def test_delete_user(db):
    user = crud.create_user(db, schemas.UserCreate(name="deleteme", password="testpass666"))
    crud.delete_user(db, user.id, actor_id=1)
    assert crud.get_user(db, user.id) is None


def test_delete_nonexistent_user(db):
    result = crud.delete_user(db, 99999, actor_id=1)
    assert result is None


def test_order_lifecycle(db):
    user = crud.create_user(db, schemas.UserCreate(name="orderuser", password="testpass666"))
    dish = crud.create_dish(db, schemas.DishCreate(name="Order Dish", created_by=user.id))
    order = crud.get_or_create_current_order(db, user.id)
    assert order is not None
    assert order.status == "open"
    item = crud.add_order_item(db, schemas.OrderItemCreate(
        order_id=order.id, dish_id=dish.id, user_id=user.id, taste="Yummy",
    ))
    assert item.id is not None
    assert crud.get_current_order(db).id == order.id
    crud.delete_order_item(db, item.id, user.id)
    crud.delete_order(db, order.id, user.id)
    assert crud.get_current_order(db) is None
