"""Tests for the main FastAPI application."""

import pytest
from fastapi.testclient import TestClient
from transcription_evaluator.api.main import app


class TestMainAPI:
    """Tests for the main FastAPI application endpoints."""

    @pytest.fixture
    def client(self):
        """FastAPI test client."""
        return TestClient(app)

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    def test_analyze_endpoints_exist(self, client):
        """Test that analysis endpoints are registered."""
        # Check if analyze endpoints return proper error messages rather than 404
        response = client.post("/analyze/single", json={})
        # Should return 422 validation error, not 404
        assert response.status_code in [400, 422]  # Validation error, not Not Found

    def test_cors_configuration(self):
        """Test CORS middleware is configured."""
        # Verify CORS middleware is in the app middleware stack 
        # TestClient doesn't process CORS headers, so we just check configuration
        middleware_classes = []
        if hasattr(app, 'user_middleware'):
            for middleware in app.user_middleware:
                if hasattr(middleware, 'cls'):
                    middleware_classes.append(middleware.cls)
                else:
                    middleware_classes.append(type(middleware))
        
        # Check if any CORS middleware is configured
        cors_configured = any('cors' in str(cls).lower() for cls in middleware_classes)
        assert cors_configured, f"CORS middleware not found in: {middleware_classes}"

    def test_not_found_endpoint(self, client):
        """Test 404 for non-existent endpoint."""
        response = client.get("/nonexistent")
        assert response.status_code == 404

    def test_app_configuration(self):
        """Test app configuration."""
        assert app.title == "A360 Transcription Evaluator"
        assert app.version == "0.1.0"
        assert len(app.routes) > 0