from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app import models

def seed():
    db = SessionLocal()
    # Check if users already exist
    if db.query(models.User).count() == 0:
        users = [
            models.User(name="哥哥", password="666"),
            models.User(name="姐姐", password="666"),
            models.User(name="宝宝", password="666")
        ]
        db.add_all(users)
        db.commit()
        print("Database seeded with users.")
    else:
        # Update existing users to have default password if they don't
        users = db.query(models.User).all()
        for user in users:
            if not user.password:
                user.password = "666"
        db.commit()
        print("Users already exist, updated passwords if missing.")
    db.close()

if __name__ == "__main__":
    models.Base.metadata.create_all(bind=engine)
    seed()
