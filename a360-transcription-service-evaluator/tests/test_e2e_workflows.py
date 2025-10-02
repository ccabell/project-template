"""End-to-end workflow tests for AWS Cognito RBAC system.

This module contains comprehensive workflow tests that validate the complete
AWS-first RBAC implementation from authentication through task completion.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from transcription_evaluator.api import cognito_assignment_routes as assign_routes
from transcription_evaluator.api import cognito_auth_routes as auth_routes
from transcription_evaluator.api.cognito_main import app
from transcription_evaluator.aws.authorizers import CognitoClaims


@pytest.mark.asyncio
class TestCompleteAuthenticationWorkflow:
    """Test complete authentication and user management workflows."""

    @pytest.fixture
    def client(self):
        """FastAPI test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_services(self):
        """Mock all required services for authentication workflow."""
        user_service = Mock()
        user_service.authenticate_user = AsyncMock()
        user_service.create_user = AsyncMock()
        user_service.get_user_profile = AsyncMock()
        user_service.update_user_profile = AsyncMock()
        user_service.add_user_to_group = AsyncMock()
        user_service.list_users = AsyncMock()
        app.dependency_overrides[auth_routes.get_user_service_dependency] = (
            lambda: user_service
        )

        admin_user = CognitoClaims(
            sub="admin-123",
            email="admin@example.com",
            name="Admin User",
            groups=["admin"],
            token_use="access",
            aud="client-123",
            iss="https://cognito-idp.us-east-1.amazonaws.com/us-east-1_pool",
            exp=1893456000,
            iat=1893452000,
            username="admin-123",
            email_verified=True,
        )

        async def _get_current_user_override(credentials=None):
            return admin_user

        app.dependency_overrides[auth_routes.get_current_user] = (
            _get_current_user_override
        )

        try:
            yield {"user_service": user_service, "admin_user": admin_user}
        finally:
            app.dependency_overrides.pop(auth_routes.get_user_service_dependency, None)
            app.dependency_overrides.pop(auth_routes.get_current_user, None)

    async def test_admin_creates_user_workflow(self, client, mock_services):
        """Test complete workflow: Admin creates user -> User logs in -> Profile access."""
        user_service = mock_services["user_service"]

        # Step 1: Admin creates a new user
        new_user_data = {
            "cognito_user_id": "new-evaluator-123",
            "email": "evaluator@example.com",
            "full_name": "New Evaluator",
            "department": "Quality Assurance",
            "role_level": 3,
            "groups": ["evaluator"],
        }

        user_service.create_user.return_value = new_user_data

        create_response = client.post(
            "/auth/users",
            json={
                "email": "evaluator@example.com",
                "name": "New Evaluator",
                "temporary_password": "TempPassword123!",
                "groups": ["evaluator"],
                "department": "Quality Assurance",
                "role_level": 3,
            },
            headers={"Authorization": "Bearer admin-token"},
        )

        assert create_response.status_code == 200
        create_data = create_response.json()
        assert create_data["success"] is True
        assert create_data["user"]["email"] == "evaluator@example.com"

        # Step 2: New user logs in
        user_service.authenticate_user.return_value = {
            "cognito_user_id": "new-evaluator-123",
            "email": "evaluator@example.com",
            "full_name": "New Evaluator",
            "access_token": "evaluator-jwt-token",
            "groups": ["evaluator"],
        }

        login_response = client.post(
            "/auth/login",
            json={"email": "evaluator@example.com", "password": "NewPassword123!"},
        )

        assert login_response.status_code == 200
        login_data = login_response.json()
        assert login_data["success"] is True
        assert "access_token" in login_data["user"]

        # Step 3: User accesses their profile
        user_service.get_user_profile.return_value = {
            **new_user_data,
            "preferences": {"theme": "light"},
            "is_active": True,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }

        # Mock the current user for profile access
        evaluator_user = CognitoClaims(
            sub="new-evaluator-123",
            email="evaluator@example.com",
            name="New Evaluator",
            groups=["evaluator"],
            token_use="access",
            aud="client-123",
            iss="https://cognito-idp.us-east-1.amazonaws.com/us-east-1_pool",
            exp=1893456000,
            iat=1893452000,
            username="new-evaluator-123",
            email_verified=True,
        )

        async def _override_get_current_user(credentials=None):
            return evaluator_user

        app.dependency_overrides[auth_routes.get_current_user] = (
            _override_get_current_user
        )

        profile_response = client.get(
            "/auth/profile", headers={"Authorization": "Bearer evaluator-jwt-token"}
        )

        app.dependency_overrides.pop(auth_routes.get_current_user, None)

        assert profile_response.status_code == 200
        profile_data = profile_response.json()
        assert profile_data["cognito_user_id"] == "new-evaluator-123"
        assert profile_data["email"] == "evaluator@example.com"
        assert "evaluator" in profile_data["groups"]

        # Verify all service calls were made correctly
        user_service.create_user.assert_called_once()
        user_service.authenticate_user.assert_called_once()
        user_service.get_user_profile.assert_called_once_with("new-evaluator-123")

    async def test_role_based_user_creation_permissions(self, client, mock_services):
        """Test that only admins can create users with specific roles."""
        user_service = mock_services["user_service"]

        # Test admin creating another admin (should succeed)
        user_service.create_user.return_value = {
            "cognito_user_id": "new-admin-456",
            "email": "newadmin@example.com",
            "full_name": "New Admin",
        }

        admin_create_response = client.post(
            "/auth/users",
            json={
                "email": "newadmin@example.com",
                "name": "New Admin",
                "temporary_password": "AdminPassword123!",
                "groups": ["admin"],
                "role_level": 1,
            },
            headers={"Authorization": "Bearer admin-token"},
        )

        assert admin_create_response.status_code == 200

        # Test non-admin trying to create admin (should fail via service layer)
        user_service.create_user.side_effect = PermissionError(
            "Insufficient permissions to create admin users"
        )

        with patch(
            "transcription_evaluator.api.cognito_auth_routes.get_current_user"
        ) as mock_current:
            evaluator_user = CognitoClaims(
                sub="evaluator-123",
                email="evaluator@example.com",
                name="Evaluator User",
                groups=["evaluator"],
                email_verified=True,
                token_use="access",
                aud="client-123",
                iss="https://cognito-idp.us-east-1.amazonaws.com/us-east-1_pool",
                exp=1893456000,
                iat=1893452000,
                username="evaluator-123",
            )
            mock_current.return_value = evaluator_user

            evaluator_create_response = client.post(
                "/auth/users",
                json={
                    "email": "unauthorized@example.com",
                    "name": "Unauthorized User",
                    "temporary_password": "Password123!",
                    "groups": ["admin"],
                    "role_level": 1,
                },
                headers={"Authorization": "Bearer evaluator-token"},
            )

        assert evaluator_create_response.status_code == 403
        assert "Insufficient permissions" in evaluator_create_response.json()["detail"]


@pytest.mark.asyncio
class TestCompleteAssignmentWorkflow:
    """Test complete script assignment and evaluation workflows."""

    @pytest.fixture
    def client(self):
        """FastAPI test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_services(self):
        """Mock all required services for assignment workflow."""
        assignment_service = Mock()
        assignment_service.create_assignment = AsyncMock()
        assignment_service.get_user_assignments = AsyncMock()
        assignment_service.update_assignment_status = AsyncMock()
        assignment_service.bulk_assign_scripts = AsyncMock()
        assignment_service.get_assignment_statistics = AsyncMock()
        assignment_service.reassign_assignment = AsyncMock()
        app.dependency_overrides[assign_routes.get_assignment_service_dependency] = (
            lambda: assignment_service
        )

        # Provide a default admin user override; tests can replace later
        default_admin = CognitoClaims(
            sub="admin-123",
            email="admin@example.com",
            name="Admin User",
            groups=["admin"],
            token_use="access",
            aud="client-123",
            iss="https://cognito-idp.us-east-1.amazonaws.com/us-east-1_pool",
            exp=1893456000,
            iat=1893452000,
            username="admin-123",
            email_verified=True,
        )

        async def _get_current_user_override(credentials=None):
            return default_admin

        app.dependency_overrides[assign_routes.get_current_user] = (
            _get_current_user_override
        )

        try:
            yield {
                "assignment_service": assignment_service,
                "get_current_user": assign_routes.get_current_user,
            }
        finally:
            app.dependency_overrides.pop(
                assign_routes.get_assignment_service_dependency, None
            )
            app.dependency_overrides.pop(assign_routes.get_current_user, None)

    async def test_complete_assignment_lifecycle(self, client, mock_services):
        """Test complete assignment lifecycle from creation to completion."""
        assignment_service = mock_services["assignment_service"]
        get_current_user = mock_services["get_current_user"]

        # Setup users
        admin_user = CognitoClaims(
            sub="admin-123",
            email="admin@example.com",
            name="Admin User",
            groups=["admin"],
            token_use="access",
            aud="client-123",
            iss="https://cognito-idp.us-east-1.amazonaws.com/us-east-1_pool",
            exp=1893456000,
            iat=1893452000,
            username="admin-123",
            email_verified=True,
        )

        evaluator_user = CognitoClaims(
            sub="evaluator-456",
            email="evaluator@example.com",
            name="Evaluator User",
            groups=["evaluator"],
            token_use="access",
            aud="client-123",
            iss="https://cognito-idp.us-east-1.amazonaws.com/us-east-1_pool",
            exp=1893456000,
            iat=1893452000,
            username="evaluator-456",
            email_verified=True,
        )

        script_id = str(uuid4())
        assignment_id = str(uuid4())

        # Step 1: Admin creates assignment
        get_current_user.return_value = admin_user

        assignment_service.create_assignment.return_value = {
            "assignment_id": assignment_id,
            "script_id": script_id,
            "script_title": "Test Evaluation Script",
            "assigned_to_cognito_id": "evaluator-456",
            "assigned_to_name": "Evaluator User",
            "assigned_by_cognito_id": "admin-123",
            "assigned_by_name": "Admin User",
            "assignment_type": "evaluate",
            "status": "pending",
            "priority": 3,
            "due_date": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
            "notes": None,
            "created_at": datetime.now(UTC).isoformat(),
        }

        create_response = client.post(
            "/assignments/",
            json={
                "script_id": script_id,
                "assigned_to_cognito_id": "evaluator-456",
                "assignment_type": "evaluate",
                "priority": 3,
                "due_date": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
            },
            headers={"Authorization": "Bearer admin-token"},
        )

        assert create_response.status_code == 200
        create_data = create_response.json()
        assert create_data["success"] is True
        assert create_data["assignment"]["assignment_type"] == "evaluate"

        # Step 2: Evaluator retrieves their assignments
        get_current_user.return_value = evaluator_user

        assignment_service.get_user_assignments.return_value = [
            {
                "assignment_id": assignment_id,
                "script_id": script_id,
                "script_title": "Test Evaluation Script",
                "script_difficulty": 3,
                "assigned_to_cognito_id": "evaluator-456",
                "assigned_to_name": "Evaluator User",
                "assigned_by_cognito_id": "admin-123",
                "assigned_by_name": "Admin User",
                "assignment_type": "evaluate",
                "status": "pending",
                "priority": 3,
                "due_date": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
                "notes": None,
                "created_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
                "completed_at": None,
            }
        ]

        assignments_response = client.get(
            "/assignments/my", headers={"Authorization": "Bearer evaluator-token"}
        )

        assert assignments_response.status_code == 200
        assignments_data = assignments_response.json()
        assert len(assignments_data) == 1
        assert assignments_data[0]["status"] == "pending"

        # Step 3: Evaluator starts working on assignment
        assignment_service.update_assignment_status.return_value = True

        start_response = client.put(
            f"/assignments/{assignment_id}/status",
            json={"status": "in_progress", "notes": "Started evaluation process"},
            headers={"Authorization": "Bearer evaluator-token"},
        )

        assert start_response.status_code == 200
        start_data = start_response.json()
        assert start_data["success"] is True
        assert "in_progress" in start_data["message"]

        # Step 4: Evaluator completes assignment
        complete_response = client.put(
            f"/assignments/{assignment_id}/status",
            json={"status": "completed", "notes": "Evaluation completed successfully"},
            headers={"Authorization": "Bearer evaluator-token"},
        )

        assert complete_response.status_code == 200
        complete_data = complete_response.json()
        assert complete_data["success"] is True
        assert "completed" in complete_data["message"]

        # Step 5: Check assignment statistics
        assignment_service.get_assignment_statistics.return_value = {
            "total_assignments": 1,
            "by_status": {"completed": 1},
            "by_type": {"evaluate": 1},
            "by_priority": {3: 1},
            "overdue_count": 0,
            "completed_this_week": 1,
            "average_completion_time_hours": 2.5,
        }

        stats_response = client.get(
            "/assignments/stats/my", headers={"Authorization": "Bearer evaluator-token"}
        )

        assert stats_response.status_code == 200
        stats_data = stats_response.json()
        assert stats_data["total_assignments"] == 1
        assert stats_data["completed_this_week"] == 1

        # Verify all service calls
        assignment_service.create_assignment.assert_called_once()
        assignment_service.get_user_assignments.assert_called_once()
        assert assignment_service.update_assignment_status.call_count == 2
        assignment_service.get_assignment_statistics.assert_called_once()

    async def test_bulk_assignment_workflow(self, client, mock_services):
        """Test bulk assignment creation and management workflow."""
        assignment_service = mock_services["assignment_service"]
        get_current_user = mock_services["get_current_user"]

        # Setup admin user
        admin_user = CognitoClaims(
            sub="admin-123",
            email="admin@example.com",
            name="Admin User",
            groups=["admin"],
            token_use="access",
            aud="client-123",
            iss="https://cognito-idp.us-east-1.amazonaws.com/us-east-1_pool",
            exp=1893456000,
            iat=1893452000,
            username="admin-123",
            email_verified=True,
        )
        get_current_user.return_value = admin_user

        # Prepare bulk assignment data
        script_ids = [str(uuid4()), str(uuid4()), str(uuid4())]
        user_assignments = {
            "evaluator-1": ["evaluate"],
            "evaluator-2": ["evaluate"],
            "voice-actor-1": ["record"],
        }

        assignment_service.bulk_assign_scripts.return_value = {
            "created_count": 5,
            "failed_count": 1,
            "created_assignments": [
                {
                    "script_id": script_ids[0],
                    "assigned_to": "evaluator-1",
                    "assignment_type": "evaluate",
                },
                {
                    "script_id": script_ids[1],
                    "assigned_to": "evaluator-1",
                    "assignment_type": "evaluate",
                },
                {
                    "script_id": script_ids[2],
                    "assigned_to": "evaluator-1",
                    "assignment_type": "evaluate",
                },
                {
                    "script_id": script_ids[0],
                    "assigned_to": "evaluator-2",
                    "assignment_type": "evaluate",
                },
                {
                    "script_id": script_ids[1],
                    "assigned_to": "voice-actor-1",
                    "assignment_type": "record",
                },
            ],
            "failed_assignments": [
                {
                    "script_id": script_ids[2],
                    "assigned_to": "voice-actor-1",
                    "assignment_type": "record",
                    "error": "User not found",
                }
            ],
        }

        bulk_response = client.post(
            "/assignments/bulk",
            json={
                "script_ids": script_ids,
                "user_assignments": user_assignments,
                "priority": 2,
                "due_date": (datetime.now(UTC) + timedelta(days=5)).isoformat(),
            },
            headers={"Authorization": "Bearer admin-token"},
        )

        assert bulk_response.status_code == 200
        bulk_data = bulk_response.json()
        assert bulk_data["success"] is True
        assert bulk_data["results"]["created_count"] == 5
        assert bulk_data["results"]["failed_count"] == 1
        assert len(bulk_data["results"]["created_assignments"]) == 5
        assert len(bulk_data["results"]["failed_assignments"]) == 1

        assignment_service.bulk_assign_scripts.assert_called_once()

    async def test_assignment_reassignment_workflow(self, client, mock_services):
        """Test assignment reassignment between users."""
        assignment_service = mock_services["assignment_service"]
        get_current_user = mock_services["get_current_user"]

        # Setup admin user
        admin_user = CognitoClaims(
            sub="admin-123",
            email="admin@example.com",
            name="Admin User",
            groups=["admin"],
            email_verified=True,
            token_use="access",
            aud="client-123",
            iss="https://cognito-idp.us-east-1.amazonaws.com/us-east-1_pool",
            exp=1893456000,
            iat=1893452000,
            username="admin-123",
        )
        get_current_user.return_value = admin_user

        assignment_id = str(uuid4())
        assignment_service.reassign_assignment.return_value = True

        reassign_response = client.put(
            f"/assignments/{assignment_id}/reassign",
            json={
                "new_assignee_cognito_id": "evaluator-new-123",
                "reason": "Original evaluator is overloaded",
            },
            headers={"Authorization": "Bearer admin-token"},
        )

        assert reassign_response.status_code == 200
        reassign_data = reassign_response.json()
        assert reassign_data["success"] is True
        assert "reassigned successfully" in reassign_data["message"]

        assert assignment_service.reassign_assignment.call_count == 1


@pytest.mark.asyncio
class TestRoleBasedWorkflows:
    """Test workflows for different user roles and their permissions."""

    @pytest.fixture
    def client(self):
        """FastAPI test client."""
        return TestClient(app)

    @pytest.fixture
    def user_roles(self):
        """Different user role configurations for testing."""
        return {
            "admin": CognitoClaims(
                sub="admin-123",
                email="admin@example.com",
                name="Admin User",
                groups=["admin"],
                email_verified=True,
                token_use="access",
                aud="client-123",
                iss="https://cognito-idp.us-east-1.amazonaws.com/us-east-1_pool",
                exp=1893456000,
                iat=1893452000,
                username="admin-123",
            ),
            "evaluator": CognitoClaims(
                sub="evaluator-456",
                email="evaluator@example.com",
                name="Evaluator User",
                groups=["evaluator"],
                email_verified=True,
                token_use="access",
                aud="client-123",
                iss="https://cognito-idp.us-east-1.amazonaws.com/us-east-1_pool",
                exp=1893456000,
                iat=1893452000,
                username="evaluator-456",
            ),
            "reviewer": CognitoClaims(
                sub="reviewer-789",
                email="reviewer@example.com",
                name="Reviewer User",
                groups=["reviewer"],
                email_verified=True,
                token_use="access",
                aud="client-123",
                iss="https://cognito-idp.us-east-1.amazonaws.com/us-east-1_pool",
                exp=1893456000,
                iat=1893452000,
                username="reviewer-789",
            ),
            "voice_actor": CognitoClaims(
                sub="voice-actor-012",
                email="voiceactor@example.com",
                name="Voice Actor User",
                groups=["voice_actor"],
                email_verified=True,
                token_use="access",
                aud="client-123",
                iss="https://cognito-idp.us-east-1.amazonaws.com/us-east-1_pool",
                exp=1893456000,
                iat=1893452000,
                username="voice-actor-012",
            ),
        }

    async def test_admin_permissions_workflow(self, client, user_roles):
        """Test admin can perform all administrative tasks."""
        admin_user = user_roles["admin"]

        # Set up environment variables for Cognito
        with patch.dict('os.environ', {
            'COGNITO_USER_POOL_ID': 'test-pool-id',
            'COGNITO_CLIENT_ID': 'test-client-id',
            'VERIFIED_PERMISSIONS_POLICY_STORE_ID': 'test-policy-store',
            'AWS_REGION': 'us-east-1'
        }):
            # Mock services
            user_service = Mock()
            user_service.create_user = AsyncMock(
                return_value={"cognito_user_id": "new-user"}
            )
            user_service.list_users = AsyncMock(return_value=[])
            user_service.add_user_to_group = AsyncMock(return_value=True)

            assignment_service = Mock()
            assignment_service.create_assignment = AsyncMock(
                return_value={"assignment_id": "new-assignment"}
            )
            assignment_service.bulk_assign_scripts = AsyncMock(
                return_value={
                    "created_count": 5,
                    "failed_count": 0,
                    "created_assignments": [],
                    "failed_assignments": [],
                }
            )
            assignment_service.reassign_assignment = AsyncMock(return_value=True)

            # Create async wrapper functions for dependency overrides
            async def _override_get_current_user(credentials=None):
                return admin_user

            async def _override_get_user_service():
                return user_service

            async def _override_get_assignment_service():
                return assignment_service

            # Set up dependency overrides
            app.dependency_overrides[auth_routes.get_current_user] = _override_get_current_user
            app.dependency_overrides[auth_routes.get_user_service_dependency] = _override_get_user_service
            app.dependency_overrides[assign_routes.get_current_user] = _override_get_current_user
            app.dependency_overrides[assign_routes.get_assignment_service_dependency] = _override_get_assignment_service

            try:
                # Test admin can create users
                create_user_response = client.post(
                    "/auth/users",
                    json={
                        "email": "test@example.com",
                        "name": "Test User",
                        "temporary_password": "Password123!",
                        "groups": ["evaluator"],
                    },
                    headers={"Authorization": "Bearer admin-token"},
                )
                assert create_user_response.status_code == 200

                # Test admin can list users
                list_users_response = client.get(
                    "/auth/users", headers={"Authorization": "Bearer admin-token"}
                )
                assert list_users_response.status_code == 200

                # Test admin can create assignments
                create_assignment_response = client.post(
                    "/assignments/",
                    json={
                        "script_id": str(uuid4()),
                        "assigned_to_cognito_id": "evaluator-456",
                        "assignment_type": "evaluate",
                    },
                    headers={"Authorization": "Bearer admin-token"},
                )
                assert create_assignment_response.status_code == 200

                # Test admin can bulk assign
                bulk_assign_response = client.post(
                    "/assignments/bulk",
                    json={
                        "script_ids": [str(uuid4())],
                        "user_assignments": {"evaluator-456": ["evaluate"]},
                    },
                    headers={"Authorization": "Bearer admin-token"},
                )
                assert bulk_assign_response.status_code == 200
            finally:
                # Clean up dependency overrides
                app.dependency_overrides.pop(auth_routes.get_current_user, None)
                app.dependency_overrides.pop(auth_routes.get_user_service_dependency, None)
                app.dependency_overrides.pop(assign_routes.get_current_user, None)
                app.dependency_overrides.pop(assign_routes.get_assignment_service_dependency, None)

    async def test_evaluator_permissions_workflow(self, client, user_roles):
        """Test evaluator can only access evaluation-related functions."""
        evaluator_user = user_roles["evaluator"]

        # Set up environment variables for Cognito
        with patch.dict('os.environ', {
            'COGNITO_USER_POOL_ID': 'test-pool-id',
            'COGNITO_CLIENT_ID': 'test-client-id',
            'VERIFIED_PERMISSIONS_POLICY_STORE_ID': 'test-policy-store',
            'AWS_REGION': 'us-east-1'
        }):
            # Mock services with permission restrictions
            user_service = Mock()
            user_service.create_user = AsyncMock(
                side_effect=PermissionError("Insufficient permissions")
            )
            user_service.get_user_profile = AsyncMock(
                return_value={
                    "cognito_user_id": "evaluator-456",
                    "email": "evaluator@example.com",
                    "full_name": "Evaluator User",
                    "department": "Quality Assurance",
                    "role_level": 3,
                    "groups": ["evaluator"],
                    "preferences": {"theme": "light"},
                    "is_active": True,
                    "created_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            )

            assignment_service = Mock()
            assignment_service.get_user_assignments = AsyncMock(return_value=[])
            assignment_service.update_assignment_status = AsyncMock(
                return_value=True
            )
            assignment_service.create_assignment = AsyncMock(
                side_effect=PermissionError("Insufficient permissions")
            )

            # Create async wrapper functions for dependency overrides
            async def _override_get_current_user(credentials=None):
                return evaluator_user

            async def _override_get_user_service():
                return user_service

            async def _override_get_assignment_service():
                return assignment_service

            # Set up dependency overrides
            app.dependency_overrides[auth_routes.get_current_user] = _override_get_current_user
            app.dependency_overrides[auth_routes.get_user_service_dependency] = _override_get_user_service
            app.dependency_overrides[assign_routes.get_current_user] = _override_get_current_user
            app.dependency_overrides[assign_routes.get_assignment_service_dependency] = _override_get_assignment_service

            try:
                # Test evaluator can access their own profile
                profile_response = client.get(
                    "/auth/profile", headers={"Authorization": "Bearer evaluator-token"}
                )
                assert profile_response.status_code == 200

                # Test evaluator can view their assignments
                assignments_response = client.get(
                    "/assignments/my",
                    headers={"Authorization": "Bearer evaluator-token"},
                )
                assert assignments_response.status_code == 200

                # Test evaluator can update assignment status
                update_response = client.put(
                    f"/assignments/{uuid4()}/status",
                    json={"status": "completed"},
                    headers={"Authorization": "Bearer evaluator-token"},
                )
                assert update_response.status_code == 200

                # Test evaluator cannot create users
                create_user_response = client.post(
                    "/auth/users",
                    json={
                        "email": "test@example.com",
                        "name": "Test User",
                        "temporary_password": "Password123!",
                    },
                    headers={"Authorization": "Bearer evaluator-token"},
                )
                assert create_user_response.status_code == 403

                # Test evaluator cannot create assignments
                create_assignment_response = client.post(
                    "/assignments/",
                    json={
                        "script_id": str(uuid4()),
                        "assigned_to_cognito_id": "someone-else",
                        "assignment_type": "evaluate",
                    },
                    headers={"Authorization": "Bearer evaluator-token"},
                )
                assert create_assignment_response.status_code == 403
            finally:
                # Clean up dependency overrides
                app.dependency_overrides.pop(auth_routes.get_current_user, None)
                app.dependency_overrides.pop(auth_routes.get_user_service_dependency, None)
                app.dependency_overrides.pop(assign_routes.get_current_user, None)
                app.dependency_overrides.pop(assign_routes.get_assignment_service_dependency, None)

    async def test_voice_actor_permissions_workflow(self, client, user_roles):
        """Test voice actor has most limited permissions."""
        voice_actor_user = user_roles["voice_actor"]

        # Set up environment variables for Cognito
        with patch.dict('os.environ', {
            'COGNITO_USER_POOL_ID': 'test-pool-id',
            'COGNITO_CLIENT_ID': 'test-client-id',
            'VERIFIED_PERMISSIONS_POLICY_STORE_ID': 'test-policy-store',
            'AWS_REGION': 'us-east-1'
        }):
            # Mock services with most restrictions
            user_service = Mock()
            user_service.create_user = AsyncMock(
                side_effect=PermissionError("Insufficient permissions")
            )
            user_service.get_user_profile = AsyncMock(
                return_value={
                    "cognito_user_id": "voice-actor-012",
                    "email": "voiceactor@example.com",
                    "full_name": "Voice Actor User",
                    "department": "Production",
                    "role_level": 4,
                    "groups": ["voice_actor"],
                    "preferences": {"theme": "light"},
                    "is_active": True,
                    "created_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            )
            user_service.list_users = AsyncMock(
                side_effect=PermissionError("Insufficient permissions")
            )

            assignment_service = Mock()
            assignment_service.get_user_assignments = AsyncMock(return_value=[])
            assignment_service.update_assignment_status = AsyncMock(
                return_value=True
            )
            assignment_service.create_assignment = AsyncMock(
                side_effect=PermissionError("Insufficient permissions")
            )
            assignment_service.get_assignment_statistics = AsyncMock(
                return_value={
                    "total_assignments": 2,
                    "by_status": {"completed": 2},
                    "by_type": {"record": 2},
                    "by_priority": {3: 2},
                    "overdue_count": 0,
                    "completed_this_week": 2,
                    "average_completion_time_hours": 3.0,
                }
            )

            # Create async wrapper functions for dependency overrides
            async def _override_get_current_user(credentials=None):
                return voice_actor_user

            async def _override_get_user_service():
                return user_service

            async def _override_get_assignment_service():
                return assignment_service

            # Set up dependency overrides
            app.dependency_overrides[auth_routes.get_current_user] = _override_get_current_user
            app.dependency_overrides[auth_routes.get_user_service_dependency] = _override_get_user_service
            app.dependency_overrides[assign_routes.get_current_user] = _override_get_current_user
            app.dependency_overrides[assign_routes.get_assignment_service_dependency] = _override_get_assignment_service

            try:
                # Test voice actor can access their own profile
                profile_response = client.get(
                    "/auth/profile",
                    headers={"Authorization": "Bearer voice-actor-token"},
                )
                assert profile_response.status_code == 200

                # Test voice actor can view their own assignments
                assignments_response = client.get(
                    "/assignments/my",
                    headers={"Authorization": "Bearer voice-actor-token"},
                )
                assert assignments_response.status_code == 200

                # Test voice actor can view their own statistics
                stats_response = client.get(
                    "/assignments/stats/my",
                    headers={"Authorization": "Bearer voice-actor-token"},
                )
                assert stats_response.status_code == 200

                # Test voice actor cannot create users
                create_user_response = client.post(
                    "/auth/users",
                    json={
                        "email": "test@example.com",
                        "name": "Test User",
                        "temporary_password": "Password123!",
                    },
                    headers={"Authorization": "Bearer voice-actor-token"},
                )
                assert create_user_response.status_code == 403

                # Test voice actor cannot list other users
                list_users_response = client.get(
                    "/auth/users", headers={"Authorization": "Bearer voice-actor-token"}
                )
                assert list_users_response.status_code == 403
            finally:
                # Clean up dependency overrides
                app.dependency_overrides.pop(auth_routes.get_current_user, None)
                app.dependency_overrides.pop(auth_routes.get_user_service_dependency, None)
                app.dependency_overrides.pop(assign_routes.get_current_user, None)
                app.dependency_overrides.pop(assign_routes.get_assignment_service_dependency, None)


@pytest.mark.asyncio
class TestErrorHandlingWorkflows:
    """Test error handling and edge cases in workflows."""

    @pytest.fixture
    def client(self):
        """FastAPI test client."""
        return TestClient(app)

    async def test_authentication_failure_recovery(self, client):
        """Test handling of authentication failures and recovery."""
        # Use FastAPI dependency overrides to avoid real Cognito client
        user_service = Mock()
        user_service.authenticate_user = AsyncMock()
        app.dependency_overrides[auth_routes.get_user_service_dependency] = (
            lambda: user_service
        )

        try:
            # Test failed login
            user_service.authenticate_user.return_value = None

            failed_login_response = client.post(
                "/auth/login",
                json={"email": "user@example.com", "password": "wrongpassword"},
            )

            assert failed_login_response.status_code == 401
            assert "Invalid email or password" in failed_login_response.json()["detail"]

            # Test successful login after failure
            user_service.authenticate_user.return_value = {
                "cognito_user_id": "user-123",
                "email": "user@example.com",
                "access_token": "valid-token",
            }

            successful_login_response = client.post(
                "/auth/login",
                json={"email": "user@example.com", "password": "correctpassword"},
            )

            assert successful_login_response.status_code == 200
            assert successful_login_response.json()["success"] is True
        finally:
            app.dependency_overrides.pop(auth_routes.get_user_service_dependency, None)

    async def test_assignment_service_error_handling(self, client):
        """Test assignment service error handling and recovery."""
        # Use dependency overrides instead of patch.multiple
        assignment_service = Mock()
        app.dependency_overrides[assign_routes.get_assignment_service_dependency] = (
            lambda: assignment_service
        )

        admin_user = CognitoClaims(
            sub="admin-123",
            email="admin@example.com",
            name="Admin User",
            groups=["admin"],
            token_use="access",
            aud="client-123",
            iss="https://cognito-idp.us-east-1.amazonaws.com/us-east-1_pool",
            exp=1893456000,
            iat=1893452000,
            username="admin-123",
            email_verified=True,
        )

        async def _override_get_current_user(credentials=None):
            return admin_user

        app.dependency_overrides[assign_routes.get_current_user] = (
            _override_get_current_user
        )

        # Test service errors are properly handled
        assignment_service.create_assignment = AsyncMock(
            side_effect=ValueError("Script not found")
        )

        error_response = client.post(
            "/assignments/",
            json={
                "script_id": str(uuid4()),
                "assigned_to_cognito_id": "user-123",
                "assignment_type": "evaluate",
            },
            headers={"Authorization": "Bearer admin-token"},
        )

        assert error_response.status_code == 400
        assert "Script not found" in error_response.json()["detail"]

        # Test service recovery
        assignment_service.create_assignment = AsyncMock(
            return_value={"assignment_id": "success-123"}
        )

        success_response = client.post(
            "/assignments/",
            json={
                "script_id": str(uuid4()),
                "assigned_to_cognito_id": "user-123",
                "assignment_type": "evaluate",
            },
            headers={"Authorization": "Bearer admin-token"},
        )

        assert success_response.status_code == 200
        assert success_response.json()["success"] is True

        app.dependency_overrides.pop(
            assign_routes.get_assignment_service_dependency, None
        )
        app.dependency_overrides.pop(assign_routes.get_current_user, None)

    async def test_token_validation_edge_cases(self, client):
        """Test edge cases in token validation."""
        # Test missing authorization header
        no_auth_response = client.get("/auth/profile")
        assert no_auth_response.status_code == 403

        # Test malformed authorization header
        bad_auth_response = client.get(
            "/auth/profile", headers={"Authorization": "InvalidToken"}
        )
        assert bad_auth_response.status_code == 403

        # Test expired token (would be handled by token validation)
        with patch(
            "transcription_evaluator.api.cognito_auth_routes.get_current_user"
        ) as mock_current:
            mock_current.side_effect = Exception("Token expired")

            expired_response = client.get(
                "/auth/profile", headers={"Authorization": "Bearer expired-token"}
            )
            assert expired_response.status_code == 401


@pytest.mark.asyncio
class TestPerformanceWorkflows:
    """Test performance aspects of workflows."""

    @pytest.fixture
    def client(self):
        """FastAPI test client."""
        return TestClient(app)

    async def test_bulk_operations_performance(self, client):
        """Test that bulk operations handle large datasets efficiently."""
        # Override dependencies
        assignment_service = Mock()
        app.dependency_overrides[assign_routes.get_assignment_service_dependency] = (
            lambda: assignment_service
        )

        admin_user = CognitoClaims(
            sub="admin-123",
            email="admin@example.com",
            name="Admin User",
            groups=["admin"],
            token_use="access",
            aud="client-123",
            iss="https://cognito-idp.us-east-1.amazonaws.com/us-east-1_pool",
            exp=1893456000,
            iat=1893452000,
            username="admin-123",
            email_verified=True,
        )

        async def _override_get_current_user(credentials=None):
            return admin_user

        app.dependency_overrides[assign_routes.get_current_user] = (
            _override_get_current_user
        )

        try:
            # Test large bulk assignment
            large_script_ids = [str(uuid4()) for _ in range(100)]
            large_user_assignments = {f"user-{i}": ["evaluate"] for i in range(50)}

            assignment_service.bulk_assign_scripts = AsyncMock(return_value={
                "created_count": 5000,
                "failed_count": 0,
                "created_assignments": [],
                "failed_assignments": [],
            })

            bulk_response = client.post(
                "/assignments/bulk",
                json={
                    "script_ids": large_script_ids,
                    "user_assignments": large_user_assignments,
                    "priority": 3,
                },
                headers={"Authorization": "Bearer admin-token"},
            )

            assert bulk_response.status_code == 200
            assert bulk_response.json()["results"]["created_count"] == 5000

            # Verify service was called with correct parameters
            assignment_service.bulk_assign_scripts.assert_called_once()
            call_args = assignment_service.bulk_assign_scripts.call_args
            assert len(call_args[1]["script_ids"]) == 100
            assert len(call_args[1]["user_assignments"]) == 50
        finally:
            app.dependency_overrides.pop(
                assign_routes.get_assignment_service_dependency, None
            )
            app.dependency_overrides.pop(assign_routes.get_current_user, None)
