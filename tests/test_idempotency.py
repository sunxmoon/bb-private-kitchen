from app import crud, schemas


def test_create_dish_idempotency(db):
    user = crud.create_user(db, schemas.UserCreate(name="chef_dup", password="666"))
    dish_in = schemas.DishCreate(name="Duplicate Dish", description="Test", created_by=user.id)

    # First call
    dish1 = crud.create_dish(db, dish_in)
    # Second call (immediate)
    dish2 = crud.create_dish(db, dish_in)

    assert dish1.id == dish2.id
    dishes = crud.get_dishes(db)
    # Filter by name to be sure
    duplicate_dishes = [d for d in dishes if d.name == "Duplicate Dish"]
    assert len(duplicate_dishes) == 1

def test_add_order_item_idempotency(db):
    user = crud.create_user(db, schemas.UserCreate(name="customer_dup", password="666"))
    dish = crud.create_dish(db, schemas.DishCreate(name="Order Dish", created_by=user.id))
    order = crud.create_order(db, schemas.OrderCreate(created_by=user.id))

    item_in = schemas.OrderItemCreate(
        order_id=order.id,
        dish_id=dish.id,
        user_id=user.id,
        remarks="No spicy"
    )

    # First call
    item1 = crud.add_order_item(db, item_in)
    # Second call (immediate)
    item2 = crud.add_order_item(db, item_in)

    assert item1.id == item2.id

    # Check actual DB count
    current_order = crud.get_current_order(db)
    assert len(current_order.items) == 1

def test_add_order_item_different_remarks_not_idempotent(db):
    user = crud.create_user(db, schemas.UserCreate(name="customer_diff", password="666"))
    dish = crud.create_dish(db, schemas.DishCreate(name="Order Dish Diff", created_by=user.id))
    order = crud.create_order(db, schemas.OrderCreate(created_by=user.id))

    item_in1 = schemas.OrderItemCreate(
        order_id=order.id,
        dish_id=dish.id,
        user_id=user.id,
        remarks="Remark A"
    )
    item_in2 = schemas.OrderItemCreate(
        order_id=order.id,
        dish_id=dish.id,
        user_id=user.id,
        remarks="Remark B"
    )

    # These should be different
    item1 = crud.add_order_item(db, item_in1)
    item2 = crud.add_order_item(db, item_in2)

    assert item1.id != item2.id
    current_order = crud.get_current_order(db)
    assert len(current_order.items) == 2
