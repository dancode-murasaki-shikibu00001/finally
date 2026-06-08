"""Integration tests for main FastAPI app — health endpoint and lifespan."""

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint(tmp_path):
    """Test that GET /api/health returns 200 with {"status": "ok"}."""
    db_file = str(tmp_path / "test.db")
    with patch.dict(os.environ, {"DB_PATH": db_file}):
        with TestClient(app) as client:
            response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_lifespan_startup(tmp_path):
    """Test that entering TestClient context manager (lifespan startup) does not raise."""
    db_file = str(tmp_path / "test.db")
    with patch.dict(os.environ, {"DB_PATH": db_file}):
        with TestClient(app) as client:
            # Lifespan ran without raising — verify health endpoint as confirmation
            assert client.get("/api/health").status_code == 200


def test_sse_route_registered(tmp_path):
    """Test that GET /api/stream/prices route is registered (returns 200, not 404)."""
    db_file = str(tmp_path / "test.db")
    with patch.dict(os.environ, {"DB_PATH": db_file}):
        with TestClient(app) as client:
            response = client.get("/api/stream/prices", stream=True)
    assert response.status_code != 404
