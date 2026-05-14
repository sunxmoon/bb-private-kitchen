from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app import models, security


def _migrate_background_to_theme():
    insp = inspect(engine)
    if "users" in insp.get_table_names():
        columns = {c["name"] for c in insp.get_columns("users")}
        if "background_image_url" in columns and "theme_color" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN theme_color VARCHAR(20) DEFAULT '#f97316'"))
                conn.execute(text("ALTER TABLE users DROP COLUMN background_image_url"))
            print("Migrated users: background_image_url -> theme_color")


def _migrate_add_role_column():
    insp = inspect(engine)
    if "users" not in insp.get_table_names():
        return
    columns = {c["name"] for c in insp.get_columns("users")}
    if "role" not in columns:
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'user' NOT NULL"
            ))
            conn.execute(text(
                "UPDATE users SET role = 'admin' WHERE id = (SELECT MIN(id) FROM users)"
            ))
        print("Migration: added role column")


def _migrate_add_indexes():
    insp = inspect(engine)
    if "orders" in insp.get_table_names():
        idx_names = {i["name"] for i in insp.get_indexes("orders")}
        if "ix_orders_status" not in idx_names:
            with engine.begin() as conn:
                conn.execute(text("CREATE INDEX ix_orders_status ON orders (status)"))
            print("Migration: created index ix_orders_status")
    if "order_items" in insp.get_table_names():
        idx_names = {i["name"] for i in insp.get_indexes("order_items")}
        if "ix_order_items_status" not in idx_names:
            with engine.begin() as conn:
                conn.execute(text("CREATE INDEX ix_order_items_status ON order_items (status)"))
            print("Migration: created index ix_order_items_status")


def seed():
    db = SessionLocal()
    # Check if users already exist
    if db.query(models.User).count() == 0:
        users = [
            models.User(name="哥哥", password=security.get_password_hash("666"), role="admin"),
            models.User(name="姐姐", password=security.get_password_hash("666")),
            models.User(name="宝宝", password=security.get_password_hash("666"))
        ]
        db.add_all(users)
        db.commit()
        print("Database seeded with users.")
    else:
        users = db.query(models.User).all()
        updated = 0
        for user in users:
            if not user.password or user.password == "666":
                user.password = security.get_password_hash("666")
                updated += 1
        if updated:
            db.commit()
            print(f"Updated {updated} user(s) with hashed passwords.")
        else:
            print(f"Users already exist ({len(users)} found).")
    db.close()

if __name__ == "__main__":
    models.Base.metadata.create_all(bind=engine)
    _migrate_background_to_theme()
    _migrate_add_role_column()
    _migrate_add_indexes()
    seed()
