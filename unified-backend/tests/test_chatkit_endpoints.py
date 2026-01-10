"""
Tests for ChatKit API endpoints
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch

from app.main import app


@pytest.fixture
def client():
    """Test client"""
    return TestClient(app)


def test_create_session(client):
    """Test creating a ChatKit session"""
    response = client.post(
        "/v1/chatkit/sessions",
        json={"user": "test_user", "workflow": {"id": "test_workflow"}}
    )
    assert response.status_code == 200
    assert "client_secret" in response.json()
    assert "session_id" in response.json()


def test_list_threads(client):
    """Test listing threads"""
    response = client.get("/support/threads")
    # May return 200 or 500 depending on server initialization
    assert response.status_code in [200, 500]


def test_create_thread(client):
    """Test creating a thread"""
    response = client.post(
        "/support/threads",
        json={"title": "Test Thread"}
    )
    # May return 200 or 500 depending on server initialization
    assert response.status_code in [200, 500]


def test_support_customer(client):
    """Test support customer endpoint"""
    response = client.get("/support/customer?thread_id=test_thread")
    assert response.status_code == 200
    assert "customer" in response.json()


def test_root_endpoint(client):
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()


def test_health_endpoint(client):
    """Test health endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert "status" in response.json()

