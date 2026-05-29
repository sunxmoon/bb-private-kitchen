import os

os.environ["TESTING"] = "1"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import crud, schemas
from app.database import Base, get_db
from app.main import app

# Use in-memory SQLite for tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db():
    # Create the database tables
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        # Drop the tables after the test
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _login(client, db):
    crud.create_user(db, schemas.UserCreate(name="testuser", password="666"))
    token = _csrf(client)
    client.post("/login", data={"name": "testuser", "password": "666", "csrf_token": token})


def _login_admin(client, db):
    crud.create_user(db, schemas.UserCreate(name="testuser", password="666"))
    user = crud.get_user_by_name(db, "testuser")
    user.role = "admin"
    db.commit()
    token = _csrf(client)
    client.post("/login", data={"name": "testuser", "password": "666", "csrf_token": token})


def _csrf(client):
    token = "test-csrf-token"
    client.cookies.set("csrf_token", token)
    return token
