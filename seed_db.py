from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app import models, security

def seed():
    db = SessionLocal()
    if db.query(models.User).count() == 0:
        users = [models.User(name="哥哥", password=security.get_password_hash("666")),
                 models.User(name="姐姐", password=security.get_password_hash("666")),
                 models.User(name="宝宝", password=security.get_password_hash("666"))]
        db.add_all(users)
        db.commit()
    db.close()

if __name__ == "__main__":
    models.Base.metadata.create_all(bind=engine)
    seed()
