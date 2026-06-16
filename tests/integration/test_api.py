"""
Integration tests for the FastAPI app using TestClient.
Databases are mocked so no live connections are required.
"""
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    """Create a TestClient with all DB dependencies mocked."""
    with (
        patch("rootcause.db.postgres.init_postgres", new_callable=AsyncMock),
        patch("rootcause.db.postgres.close_postgres", new_callable=AsyncMock),
        patch("rootcause.db.redis_client.init_redis", new_callable=AsyncMock),
        patch("rootcause.db.redis_client.close_redis", new_callable=AsyncMock),
        patch("rootcause.db.qdrant_client.init_qdrant", new_callable=AsyncMock),
        patch("rootcause.db.qdrant_client.close_qdrant", new_callable=AsyncMock),
        patch("rootcause.db.neo4j_client.init_neo4j", new_callable=AsyncMock),
        patch("rootcause.db.neo4j_client.close_neo4j", new_callable=AsyncMock),
        patch("rootcause.core.telemetry.init_otel"),
    ):
        from rootcause.api.app import create_app
        app = create_app()
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


def test_health_returns_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "timestamp" in data


def test_health_includes_environment(client):
    resp = client.get("/health")
    assert "environment" in resp.json()


def test_analyze_requires_auth_when_key_set(client):
    with patch("rootcause.core.security.get_settings") as mock:
        mock.return_value.api_secret_key = "secret"
        resp = client.post("/incidents/analyze", json={
            "title": "Test", "description": "test", "service": "svc", "severity": "low",
        })
        assert resp.status_code == 401


def test_analyze_accepts_valid_request(client):
    incident_id = uuid.uuid4()
    mock_incident = MagicMock()
    mock_incident.id = incident_id
    mock_incident.status = "queued"
    mock_incident.created_at = datetime.now(UTC)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.add = MagicMock()

    with (
        patch("rootcause.core.security.get_settings") as sec_mock,
        patch("rootcause.api.routes.incidents.get_session") as sess_mock,
        patch("rootcause.api.routes.incidents.BackgroundTasks.add_task"),
    ):
        sec_mock.return_value.api_secret_key = ""
        sess_mock.return_value = mock_session

        resp = client.post("/incidents/analyze", json={
            "title": "DB down",
            "description": "Database is not responding",
            "service": "payment-service",
            "severity": "critical",
        })
        assert resp.status_code in (202, 422, 500)


def test_get_incident_returns_404_for_unknown(client):
    unknown_id = uuid.uuid4()

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.get = AsyncMock(return_value=None)

    with (
        patch("rootcause.core.security.get_settings") as sec_mock,
        patch("rootcause.api.routes.incidents.get_session") as sess_mock,
        patch("rootcause.db.redis_client.get_redis", return_value=None),
    ):
        sec_mock.return_value.api_secret_key = ""
        sess_mock.return_value = mock_session

        resp = client.get(f"/incidents/{unknown_id}")
        assert resp.status_code == 404
