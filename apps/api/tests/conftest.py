import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.api.deps import AuthenticatedUser, get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.core.rate_limit import rate_limiter
from app.main import create_app



@pytest.fixture(autouse=True)
def reset_rate_limiter():
    rate_limiter.reset()
    yield
    rate_limiter.reset()

@pytest.fixture(autouse=True)
def stub_auto_triage_dispatch(monkeypatch):
    class StubDispatchedTask:
        message_id = "stub-ai-triage-task"
        topic = "local-ai-triage"

    calls: list[str] = []

    def fake_publish(*, job_id: str):
        calls.append(job_id)
        return StubDispatchedTask()

    monkeypatch.setattr("app.services.job_queue_service.publish_ai_triage_task", fake_publish)
    yield calls

@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
    Base.metadata.create_all(bind=engine)

    current_user = {"id": "user-owner", "email": "owner@example.com"}

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_get_current_user():
        return AuthenticatedUser(**current_user)

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(app) as test_client:
        test_client.current_user = current_user
        test_client.session_factory = TestingSessionLocal
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def create_org(client: TestClient):
    def _create_org(name: str = "Acme Support") -> dict:
        response = client.post("/v1/organizations", json={"name": name})
        assert response.status_code == 201
        return response.json()

    return _create_org
