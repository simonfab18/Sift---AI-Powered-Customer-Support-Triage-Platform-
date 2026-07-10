from fastapi.testclient import TestClient

from app.main import create_app


def test_health_check_returns_ok() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_liveness_check_returns_ok() -> None:
    client = TestClient(create_app())

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_reports_dependencies(monkeypatch) -> None:
    monkeypatch.setattr("app.api.routes.health.check_database", lambda: (True, None))
    monkeypatch.setattr("app.api.routes.health.check_task_queue_config", lambda: (True, "pubsub configured"))
    client = TestClient(create_app())

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["dependencies"]["database"]["status"] == "ok"
    assert response.json()["dependencies"]["task_queue"]["status"] == "ok"


def test_status_returns_service_status(monkeypatch) -> None:
    monkeypatch.setattr("app.api.routes.health.check_database", lambda: (True, None))
    monkeypatch.setattr("app.api.routes.health.check_task_queue_config", lambda: (True, "pubsub configured"))
    monkeypatch.setattr("app.api.routes.status.check_database", lambda: (True, None))
    monkeypatch.setattr("app.api.routes.status.check_task_queue_config", lambda: (True, "pubsub configured"))
    client = TestClient(create_app())

    response = client.get("/v1/status")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"]
    assert response.json()["release_version"]
