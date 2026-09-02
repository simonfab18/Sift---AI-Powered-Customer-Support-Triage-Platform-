from fastapi.testclient import TestClient

from app.core.config import settings


def test_sensitive_actions_return_429_with_retry_after(client: TestClient, create_org, monkeypatch) -> None:
    organization = create_org()
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_sensitive_limit", 1)
    monkeypatch.setattr(settings, "rate_limit_sensitive_window_seconds", 60)

    first = client.post(
        f"/v1/orgs/{organization['id']}/members/invite",
        json={"email": "first@example.com", "role": "agent"},
    )
    second = client.post(
        f"/v1/orgs/{organization['id']}/members/invite",
        json={"email": "second@example.com", "role": "agent"},
    )

    assert first.status_code == 201
    assert second.status_code == 429
    assert second.json()["detail"] == "Rate limit exceeded. Try again later."
    assert int(second.headers["retry-after"]) > 0


def test_request_body_limit_returns_413(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "max_request_body_bytes", 4)

    response = client.post(
        "/v1/organizations",
        json={"name": "Body Too Large"},
        headers={"content-length": "100"},
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "Request body too large"


def test_security_headers_are_set(client: TestClient) -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
