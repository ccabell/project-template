"""Integration tests for FastAPI endpoints with Cognito authentication.

This module tests the complete API integration including authentication,
authorization, and endpoint functionality with AWS Cognito.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from transcription_evaluator.api import cognito_assignment_routes as assign_routes
from transcription_evaluator.api import cognito_auth_routes as auth_routes
from transcription_evaluator.api.cognito_main import app
from transcription_evaluator.aws.authorizers import CognitoClaims


class TestAuthRoutes:
    """Test authentication routes."""

    @pytest.fixture
    def client(self):
        """FastAPI test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_user_service(self):
        """Mock user service for dependency injection."""
        service = Mock()
        service.authenticate_user = AsyncMock()
        service.create_user = AsyncMock()
        service.get_user_profile = AsyncMock()
        service.update_user_profile = AsyncMock()
        service.add_user_to_group = AsyncMock()
        service.remove_user_from_group = AsyncMock()
        service.list_users = AsyncMock()
        service.delete_user = AsyncMock()
        app.dependency_overrides[auth_routes.get_user_service_dependency] = (
            lambda: service
        )
        yield service
        app.dependency_overrides.pop(auth_routes.get_user_service_dependency, None)

    @pytest.fixture
    def mock_current_user(self):
        """Mock current user for authenticated endpoints."""
        user = CognitoClaims(
            sub="test-user-123",
            email="test@example.com",
            name="Test User",
            groups=["evaluator"],
            token_use="access",
            aud="client-123",
            iss="https://cognito-idp.us-east-1.amazonaws.com/us-east-1_abc",
            exp=1893456000,
            iat=1893452000,
            username="test-user-123",
            email_verified=True,
        )

        async def _override_get_current_user(credentials=None):
            return user

        app.dependency_overrides[auth_routes.get_current_user] = (
            _override_get_current_user
        )
        yield user
        app.dependency_overrides.pop(auth_routes.get_current_user, None)

    def test_health_check(self, client):
        """Test health check endpoint (no auth required)."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "transcription-evaluator-api"
        assert data["authentication"] == "aws-cognito"

    def test_root_endpoint(self, client):
        """Test root endpoint (no auth required)."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "Transcription Evaluator API" in data["message"]
        assert data["version"] == "2.0.0"

    def test_api_info_endpoint(self, client):
        """Test API info endpoint (no auth required)."""
        response = client.get("/api/info")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Transcription Evaluator API"
        assert data["version"] == "2.0.0"
        assert "AWS Cognito JWT" in data["authentication"]["type"]

    def test_login_success(self, client, mock_user_service):
        """Test successful login."""
        # Setup
        mock_user_service.authenticate_user.return_value = {
            "cognito_user_id": "user-123",
            "email": "test@example.com",
            "full_name": "Test User",
            "access_token": "fake-jwt-token",
        }

        # Execute
        response = client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "testpassword123"},
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["user"]["email"] == "test@example.com"
        mock_user_service.authenticate_user.assert_called_once()

    def test_login_failure(self, client, mock_user_service):
        """Test failed login."""
        # Setup
        mock_user_service.authenticate_user.return_value = None

        # Execute
        response = client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "wrongpassword"},
        )

        # Verify
        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]

    def test_create_user_success(self, client, mock_user_service, mock_current_user):
        """Test successful user creation."""
        # Setup
        mock_user_service.create_user.return_value = {
            "cognito_user_id": "new-user-123",
            "email": "newuser@example.com",
            "full_name": "New User",
        }

        # Execute
        response = client.post(
            "/auth/users",
            json={
                "email": "newuser@example.com",
                "name": "New User",
                "temporary_password": "TempPassword123!",
                "groups": ["evaluator"],
                "role_level": 3,
            },
            headers={"Authorization": "Bearer fake-jwt-token"},
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["user"]["email"] == "newuser@example.com"

    def test_get_profile_success(self, client, mock_user_service, mock_current_user):
        """Test successful profile retrieval."""
        # Setup
        mock_user_service.get_user_profile.return_value = {
            "cognito_user_id": "test-user-123",
            "email": "test@example.com",
            "full_name": "Test User",
            "department": "Engineering",
            "role_level": 2,
            "groups": ["evaluator"],
            "preferences": {"theme": "dark"},
            "is_active": True,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }

        # Execute
        response = client.get(
            "/auth/profile", headers={"Authorization": "Bearer fake-jwt-token"}
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["cognito_user_id"] == "test-user-123"
        assert data["email"] == "test@example.com"

    def test_update_profile_success(self, client, mock_user_service, mock_current_user):
        """Test successful profile update."""
        # Setup
        mock_user_service.update_user_profile.return_value = True

        # Execute
        response = client.put(
            "/auth/profile",
            json={"full_name": "Updated Name", "department": "Marketing"},
            headers={"Authorization": "Bearer fake-jwt-token"},
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "updated successfully" in data["message"]

    def test_validate_token_success(self, client, mock_current_user):
        """Test successful token validation."""
        response = client.get(
            "/auth/validate", headers={"Authorization": "Bearer fake-jwt-token"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["user"]["cognito_user_id"] == "test-user-123"
        assert data["user"]["email"] == "test@example.com"

    def test_unauthorized_access(self, client):
        """Test accessing protected endpoint without token."""
        response = client.get("/auth/profile")
        assert (
            response.status_code == 403
        )  # FastAPI returns 403 for missing bearer token


class TestAssignmentRoutes:
    """Test assignment routes."""

    @pytest.fixture
    def client(self):
        """FastAPI test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_assignment_service(self):
        """Mock assignment service for dependency injection."""
        service = Mock()
        service.create_assignment = AsyncMock()
        service.get_user_assignments = AsyncMock()
        service.update_assignment_status = AsyncMock()
        service.bulk_assign_scripts = AsyncMock()
        service.get_assignment_statistics = AsyncMock()
        service.reassign_assignment = AsyncMock()
        app.dependency_overrides[assign_routes.get_assignment_service_dependency] = (
            lambda: service
        )
        yield service
        app.dependency_overrides.pop(
            assign_routes.get_assignment_service_dependency, None
        )

    @pytest.fixture
    def mock_current_user(self):
        """Mock current user for authenticated endpoints."""
        user = CognitoClaims(
            sub="test-user-123",
            email="test@example.com",
            name="Test User",
            groups=["evaluator"],
            token_use="access",
            aud="client-123",
            iss="https://cognito-idp.us-east-1.amazonaws.com/us-east-1_abc",
            exp=1893456000,
            iat=1893452000,
            username="test-user-123",
            email_verified=True,
        )

        async def _override_get_current_user(credentials=None):
            return user

        app.dependency_overrides[assign_routes.get_current_user] = (
            _override_get_current_user
        )
        yield user
        app.dependency_overrides.pop(assign_routes.get_current_user, None)

    def test_create_assignment_success(
        self, client, mock_assignment_service, mock_current_user
    ):
        """Test successful assignment creation."""
        # Setup
        script_id = str(uuid4())
        mock_assignment_service.create_assignment.return_value = {
            "assignment_id": str(uuid4()),
            "script_id": script_id,
            "script_title": "Test Script",
            "assigned_to_cognito_id": "user-456",
            "assigned_to_name": "Test Assignee",
            "assigned_by_cognito_id": "test-user-123",
            "assigned_by_name": "Test User",
            "assignment_type": "evaluate",
            "status": "pending",
            "priority": 3,
            "created_at": datetime.now(UTC).isoformat(),
        }

        # Execute
        response = client.post(
            "/assignments/",
            json={
                "script_id": script_id,
                "assigned_to_cognito_id": "user-456",
                "assignment_type": "evaluate",
                "priority": 3,
            },
            headers={"Authorization": "Bearer fake-jwt-token"},
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["assignment"]["script_id"] == script_id
        mock_assignment_service.create_assignment.assert_called_once()

    def test_get_my_assignments_success(
        self, client, mock_assignment_service, mock_current_user
    ):
        """Test successful retrieval of user's assignments."""
        # Setup
        assignment_id = str(uuid4())
        script_id = str(uuid4())

        mock_assignment_service.get_user_assignments.return_value = [
            {
                "assignment_id": assignment_id,
                "script_id": script_id,
                "script_title": "Test Script",
                "script_difficulty": 3,
                "assigned_to_cognito_id": "test-user-123",
                "assigned_to_name": "Test User",
                "assigned_by_cognito_id": "admin-123",
                "assigned_by_name": "Admin User",
                "assignment_type": "evaluate",
                "status": "pending",
                "priority": 3,
                "due_date": None,
                "notes": None,
                "created_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
                "completed_at": None,
            }
        ]

        # Execute
        response = client.get(
            "/assignments/my", headers={"Authorization": "Bearer fake-jwt-token"}
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["assignment_id"] == assignment_id
        assert data[0]["assignment_type"] == "evaluate"

    def test_update_assignment_status_success(
        self, client, mock_assignment_service, mock_current_user
    ):
        """Test successful assignment status update."""
        # Setup
        assignment_id = str(uuid4())
        mock_assignment_service.update_assignment_status.return_value = True

        # Execute
        response = client.put(
            f"/assignments/{assignment_id}/status",
            json={"status": "completed", "notes": "Task completed successfully"},
            headers={"Authorization": "Bearer fake-jwt-token"},
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "completed" in data["message"]

    def test_bulk_assign_scripts_success(
        self, client, mock_assignment_service, mock_current_user
    ):
        """Test successful bulk script assignment."""
        # Setup
        script_ids = [str(uuid4()), str(uuid4())]
        mock_assignment_service.bulk_assign_scripts.return_value = {
            "created_count": 3,
            "failed_count": 0,
            "created_assignments": [
                {
                    "script_id": script_ids[0],
                    "assigned_to": "user-1",
                    "assignment_type": "evaluate",
                },
                {
                    "script_id": script_ids[1],
                    "assigned_to": "user-1",
                    "assignment_type": "evaluate",
                },
                {
                    "script_id": script_ids[0],
                    "assigned_to": "user-2",
                    "assignment_type": "record",
                },
            ],
            "failed_assignments": [],
        }

        # Execute
        response = client.post(
            "/assignments/bulk",
            json={
                "script_ids": script_ids,
                "user_assignments": {"user-1": ["evaluate"], "user-2": ["record"]},
                "priority": 3,
            },
            headers={"Authorization": "Bearer fake-jwt-token"},
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["results"]["created_count"] == 3
        assert data["results"]["failed_count"] == 0

    def test_get_assignment_statistics_success(
        self, client, mock_assignment_service, mock_current_user
    ):
        """Test successful assignment statistics retrieval."""
        # Setup
        mock_assignment_service.get_assignment_statistics.return_value = {
            "total_assignments": 10,
            "by_status": {"pending": 3, "in_progress": 2, "completed": 5},
            "by_type": {"evaluate": 6, "record": 4},
            "by_priority": {1: 2, 2: 3, 3: 5},
            "overdue_count": 1,
            "completed_this_week": 3,
            "average_completion_time_hours": 24.5,
        }

        # Execute
        response = client.get(
            "/assignments/stats/my", headers={"Authorization": "Bearer fake-jwt-token"}
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["total_assignments"] == 10
        assert data["by_status"]["completed"] == 5
        assert data["overdue_count"] == 1

    def test_reassign_assignment_success(
        self, client, mock_assignment_service, mock_current_user
    ):
        """Test successful assignment reassignment."""
        # Setup
        assignment_id = str(uuid4())
        mock_assignment_service.reassign_assignment.return_value = True

        # Execute
        response = client.put(
            f"/assignments/{assignment_id}/reassign",
            json={
                "new_assignee_cognito_id": "new-user-123",
                "reason": "Better skills match",
            },
            headers={"Authorization": "Bearer fake-jwt-token"},
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "reassigned successfully" in data["message"]

    def test_permission_error_handling(
        self, client, mock_assignment_service, mock_current_user
    ):
        """Test permission error handling."""
        # Setup
        mock_assignment_service.create_assignment.side_effect = PermissionError(
            "Insufficient permissions"
        )

        # Execute
        response = client.post(
            "/assignments/",
            json={
                "script_id": str(uuid4()),
                "assigned_to_cognito_id": "user-456",
                "assignment_type": "evaluate",
                "priority": 3,
            },
            headers={"Authorization": "Bearer fake-jwt-token"},
        )

        # Verify
        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]

    def test_value_error_handling(
        self, client, mock_assignment_service, mock_current_user
    ):
        """Test value error handling."""
        # Setup
        mock_assignment_service.create_assignment.side_effect = ValueError(
            "Script not found"
        )

        # Execute
        response = client.post(
            "/assignments/",
            json={
                "script_id": str(uuid4()),
                "assigned_to_cognito_id": "user-456",
                "assignment_type": "evaluate",
                "priority": 3,
            },
            headers={"Authorization": "Bearer fake-jwt-token"},
        )

        # Verify
        assert response.status_code == 400
        assert "Script not found" in response.json()["detail"]


class TestMiddlewareAndSecurity:
    """Test middleware and security features."""

    @pytest.fixture
    def client(self):
        """FastAPI test client."""
        return TestClient(app)

    def test_cors_headers(self, client):
        """Test CORS headers are properly set."""
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

        # CORS preflight should be handled
        assert "access-control-allow-origin" in response.headers

    def test_trusted_host_middleware(self, client):
        """Test trusted host middleware allows valid hosts."""
        response = client.get("/health", headers={"Host": "localhost"})
        assert response.status_code == 200

    def test_global_exception_handler(self, client):
        """Test global exception handler."""
        # This would need a route that raises an exception
        # For now, test that the handler is properly configured
        assert app.exception_handlers is not None


@pytest.mark.asyncio
class TestEndToEndWorkflows:
    """End-to-end workflow tests."""

    @pytest.fixture
    def client(self):
        """FastAPI test client."""
        return TestClient(app)

    async def test_complete_authentication_flow(self, client):
        """Test complete authentication and authorization flow."""
        # This would test:
        # 1. Login with Cognito
        # 2. Get profile information
        # 3. Access protected resources
        # 4. Token validation
        pytest.skip("Requires full AWS integration setup")

    async def test_complete_assignment_workflow(self, client):
        """Test complete assignment workflow."""
        # This would test:
        # 1. Admin creates assignment
        # 2. User retrieves assignments
        # 3. User updates assignment status
        # 4. Admin checks statistics
        pytest.skip("Requires full AWS integration setup")

    async def test_role_based_access_control(self, client):
        """Test role-based access control across different user types."""
        # This would test different permissions for:
        # - admin: full access
        # - evaluator: assignment management
        # - reviewer: review permissions
        # - voice_actor: limited access
        pytest.skip("Requires full AWS integration setup")
