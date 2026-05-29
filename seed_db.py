"""Seed database with initial users. Run after Alembic migrations."""
from app.database import SessionLocal
from app import models, security


def seed():
    db = SessionLocal()
    try:
        if db.query(models.User).count() == 0:
            users = [
                models.User(name="哥哥", password=security.get_password_hash("666"), role="admin"),
                models.User(name="姐姐", password=security.get_password_hash("666")),
                models.User(name="宝宝", password=security.get_password_hash("666")),
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
    finally:
        db.close()


if __name__ == "__main__":
    seed()
