import os
import pytest

os.environ["MOCK_LLM"] = "1"
os.environ["DATABASE_URL"] = "sqlite:///./test_yuno.db"


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.database import init_db, engine, Base
    from app.main import app

    Base.metadata.drop_all(bind=engine)
    init_db()
    with TestClient(app) as c:
        yield c
