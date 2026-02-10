from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app import models, security

def seed():
    db = SessionLocal()
    # Check if users already exist
    if db.query(models.User).count() == 0:
        users = [
            models.User(name="哥哥", password=security.get_password_hash("666")),
            models.User(name="姐姐", password=security.get_password_hash("666")),
            models.User(name="宝宝", password=security.get_password_hash("666"))
        ]
        db.add_all(users)
        db.commit()
        print("Database seeded with users.")
    else:
        # Update existing users to have hashed password if it's still plain "666" or missing
        users = db.query(models.User).all()
        for user in users:
            if not user.password or user.password == "666":
                user.password = security.get_password_hash("666")
        db.commit()
        print("Users already exist, ensured passwords are hashed.")
    db.close()

if __name__ == "__main__":
    models.Base.metadata.create_all(bind=engine)
    seed()
