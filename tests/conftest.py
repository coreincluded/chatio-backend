"""Shared fixtures for Chatio backend tests."""
import os, sys, tempfile, pytest
from dataclasses import dataclass

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Base, engine, SessionLocal, init_db
from main import app
from routers.auth import hash_password, create_access_token
from models import User, Organization, Subscription, SubscriptionTier
from fastapi.testclient import TestClient


@dataclass
class TestUser:
    user_id: int
    org_id: int
    email: str
    username: str


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _make_user(email, username, full_name) -> TestUser:
    db = SessionLocal()
    user = User(email=email, username=username, full_name=full_name,
                hashed_password=hash_password("test1234"))
    db.add(user)
    db.commit()
    db.refresh(user)
    uid = user.id

    org = Organization(owner_id=uid, name=f"{username}'s Org")
    db.add(org)
    db.commit()
    db.refresh(org)
    oid = org.id

    sub = Subscription(organization_id=oid, tier=SubscriptionTier.FREE)
    db.add(sub)
    db.commit()
    db.close()
    return TestUser(user_id=uid, org_id=oid, email=email, username=username)


@pytest.fixture
def user_a():
    return _make_user("alice@test.com", "alice", "Alice")


@pytest.fixture
def user_b():
    return _make_user("bob@test.com", "bob", "Bob")


@pytest.fixture
def token_a(user_a):
    return create_access_token({"sub": str(user_a.user_id)})


@pytest.fixture
def token_b(user_b):
    return create_access_token({"sub": str(user_b.user_id)})


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
