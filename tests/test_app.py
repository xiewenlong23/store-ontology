"""
Basic tests for Store Ontology API.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "store_id" in data

def test_root_endpoint():
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert data["message"] == "Store Ontology API"

def test_cors_headers():
    """Test that CORS headers are present."""
    response = client.get("/health")
    assert "access-control-allow-origin" in response.headers
