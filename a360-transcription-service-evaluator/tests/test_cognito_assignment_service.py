"""Unit tests for CognitoAssignmentService.

This module tests the assignment service with AWS Cognito integration,
including assignment creation, updates, and authorization checks.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from transcription_evaluator.aws.verified_permissions import (
    AuthorizationDecision,
    VerifiedPermissionsClient,
)
from transcription_evaluator.services.cognito_assignment_service import (
    CognitoAssignmentService,
)
from transcription_evaluator.services.cognito_user_service import CognitoUserService


class TestCognitoAssignmentService:
    """Test cases for CognitoAssignmentService."""

    @pytest.fixture
    def mock_avp_client(self):
        """Mock Verified Permissions client."""
        client = Mock(spec=VerifiedPermissionsClient)
        client.is_authorized = AsyncMock()
        return client

    @pytest.fixture
    def mock_user_service(self):
        """Mock user service."""
        service = Mock(spec=CognitoUserService)
        service.cognito_client = Mock()
        service.cognito_client.get_user_groups = AsyncMock()
        return service

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        with patch(
            "transcription_evaluator.services.cognito_assignment_service.get_database_session"
        ) as mock:
            session = Mock()
            mock.return_value.__enter__.return_value = session
            yield session

    @pytest.fixture
    def assignment_service(self, mock_avp_client, mock_user_service):
        """Create assignment service with mocked dependencies."""
        return CognitoAssignmentService(
            avp_client=mock_avp_client, user_service=mock_user_service
        )

    @pytest.mark.asyncio
    async def test_create_assignment_success(
        self, assignment_service, mock_avp_client, mock_db_session
    ):
        """Test successful assignment creation."""
        # Setup
        script_id = uuid4()
        assigned_to_cognito_id = "user-123"
        assigned_by_cognito_id = "admin-123"
        assignment_type = "evaluate"

        mock_avp_client.is_authorized.return_value = Mock(
            decision=AuthorizationDecision.ALLOW
        )

        mock_script = Mock()
        mock_script.id = script_id
        mock_script.title = "Test Script"
        mock_script.difficulty_level = 3

        mock_assignee = Mock()
        mock_assignee.cognito_user_id = assigned_to_cognito_id
        mock_assignee.full_name = "Test Assignee"

        mock_assigner = Mock()
        mock_assigner.cognito_user_id = assigned_by_cognito_id
        mock_assigner.full_name = "Test Admin"

        mock_assignment = Mock()
        mock_assignment.id = uuid4()
        mock_assignment.script_id = script_id
        mock_assignment.assigned_to_cognito_id = assigned_to_cognito_id
        mock_assignment.assigned_by_cognito_id = assigned_by_cognito_id
        mock_assignment.assignment_type = assignment_type
        mock_assignment.status = "pending"
        mock_assignment.priority = 3
        mock_assignment.due_date = datetime.now(UTC)
        mock_assignment.notes = None
        mock_assignment.created_at = datetime.now(UTC)

        # Mock database queries
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            mock_script,
            None,
            None,
        ]

        # Bypass internal authorization checks
        assignment_service._check_authorization = AsyncMock(return_value=True)

        with patch(
            "transcription_evaluator.services.cognito_assignment_service.get_user_by_cognito_id"
        ) as mock_get_user:
            # First call from _check_authorization needs a user profile with email
            mock_user_profile = Mock()
            mock_user_profile.email = "admin@example.com"
            mock_get_user.side_effect = [
                mock_user_profile,
                mock_assignee,
                mock_assigner,
            ]

            with patch(
                "transcription_evaluator.models.cognito_models.ScriptAssignment"
            ) as mock_assignment_class:
                mock_assignment_class.return_value = mock_assignment
                mock_db_session.add = Mock()
                mock_db_session.commit = Mock()
                mock_db_session.refresh = Mock()

                # Execute
                result = await assignment_service.create_assignment(
                    script_id=script_id,
                    assigned_to_cognito_id=assigned_to_cognito_id,
                    assignment_type=assignment_type,
                    assigned_by_cognito_id=assigned_by_cognito_id,
                )

        # Verify
        assert result is not None
        assert result["script_id"] == str(script_id)
        assert result["assigned_to_cognito_id"] == assigned_to_cognito_id
        assert result["assignment_type"] == assignment_type
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_assignment_unauthorized(
        self, assignment_service, mock_avp_client
    ):
        """Test assignment creation with insufficient permissions."""
        # Setup
        mock_avp_client.is_authorized.return_value = Mock(
            decision=AuthorizationDecision.DENY
        )

        # Execute & Verify
        with pytest.raises(PermissionError):
            await assignment_service.create_assignment(
                script_id=uuid4(),
                assigned_to_cognito_id="user-123",
                assignment_type="evaluate",
                assigned_by_cognito_id="user-456",
            )

    @pytest.mark.asyncio
    async def test_create_assignment_script_not_found(
        self, assignment_service, mock_avp_client, mock_db_session
    ):
        """Test assignment creation when script doesn't exist."""
        # Setup
        assignment_service._check_authorization = AsyncMock(return_value=True)
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        # Execute & Verify
        with pytest.raises(ValueError, match="Script not found"):
            await assignment_service.create_assignment(
                script_id=uuid4(),
                assigned_to_cognito_id="user-123",
                assignment_type="evaluate",
                assigned_by_cognito_id="admin-123",
            )

    @pytest.mark.asyncio
    async def test_get_user_assignments_success(
        self, assignment_service, mock_avp_client, mock_db_session
    ):
        """Test successful retrieval of user assignments."""
        # Setup
        cognito_user_id = "user-123"
        mock_avp_client.is_authorized.return_value = Mock(
            decision=AuthorizationDecision.ALLOW
        )

        assignment_id = uuid4()
        script_id = uuid4()

        mock_assignment = Mock()
        mock_assignment.id = assignment_id
        mock_assignment.script_id = script_id
        mock_assignment.assigned_to_cognito_id = cognito_user_id
        mock_assignment.assigned_by_cognito_id = "admin-123"
        mock_assignment.assignment_type = "evaluate"
        mock_assignment.status = "pending"
        mock_assignment.priority = 3
        mock_assignment.due_date = None
        mock_assignment.notes = None
        mock_assignment.created_at = datetime.now(UTC)
        mock_assignment.updated_at = datetime.now(UTC)
        mock_assignment.completed_at = None

        mock_script = Mock()
        mock_script.title = "Test Script"
        mock_script.difficulty_level = 2

        mock_assigner = Mock()
        mock_assigner.full_name = "Test Admin"

        mock_db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            mock_assignment
        ]
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_script
        )

        with patch(
            "transcription_evaluator.services.cognito_assignment_service.get_user_by_cognito_id"
        ) as mock_get_user:
            mock_get_user.return_value = mock_assigner

            # Execute
            result = await assignment_service.get_user_assignments(cognito_user_id)

        # Verify
        assert len(result) == 1
        assert result[0]["assignment_id"] == str(assignment_id)
        assert result[0]["script_id"] == str(script_id)
        assert result[0]["assignment_type"] == "evaluate"
        mock_avp_client.is_authorized.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_assignment_status_success(
        self, assignment_service, mock_avp_client, mock_db_session
    ):
        """Test successful assignment status update."""
        # Setup
        assignment_id = uuid4()
        new_status = "completed"
        cognito_user_id = "user-123"

        mock_assignment = Mock()
        mock_assignment.id = assignment_id
        mock_assignment.assigned_to_cognito_id = cognito_user_id
        mock_assignment.status = "in_progress"
        mock_assignment.notes = None
        mock_assignment.completed_at = None

        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_assignment
        )
        mock_db_session.commit = Mock()

        # Execute
        result = await assignment_service.update_assignment_status(
            assignment_id=assignment_id,
            new_status=new_status,
            cognito_user_id=cognito_user_id,
        )

        # Verify
        assert result is True
        assert mock_assignment.status == new_status
        assert mock_assignment.completed_at is not None
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_assignment_status_unauthorized(
        self, assignment_service, mock_avp_client, mock_db_session
    ):
        """Test assignment status update with insufficient permissions."""
        # Setup
        assignment_id = uuid4()
        different_user_id = "other-user-123"

        mock_assignment = Mock()
        mock_assignment.id = assignment_id
        mock_assignment.assigned_to_cognito_id = "user-123"  # Different from requester

        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_assignment
        )
        mock_avp_client.is_authorized.return_value = Mock(
            decision=AuthorizationDecision.DENY
        )

        # Execute & Verify
        with pytest.raises(PermissionError):
            await assignment_service.update_assignment_status(
                assignment_id=assignment_id,
                new_status="completed",
                cognito_user_id=different_user_id,
            )

    @pytest.mark.asyncio
    async def test_bulk_assign_scripts_success(
        self, assignment_service, mock_avp_client, mock_db_session
    ):
        """Test successful bulk script assignment."""
        # Setup
        script_ids = [uuid4(), uuid4()]
        user_assignments = {
            "user-123": ["evaluate"],
            "user-456": ["record", "evaluate"],
        }
        assigned_by_cognito_id = "admin-123"

        mock_avp_client.is_authorized.return_value = Mock(
            decision=AuthorizationDecision.ALLOW
        )
        mock_db_session.add = Mock()
        mock_db_session.commit = Mock()

        # Execute
        result = await assignment_service.bulk_assign_scripts(
            script_ids=script_ids,
            user_assignments=user_assignments,
            assigned_by_cognito_id=assigned_by_cognito_id,
        )

        # Verify
        assert result["created_count"] == 6
        assert result["failed_count"] == 0
        assert len(result["created_assignments"]) == 6
        mock_avp_client.is_authorized.assert_called_once()
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_assignment_statistics_success(
        self, assignment_service, mock_avp_client, mock_db_session
    ):
        """Test successful assignment statistics retrieval."""
        # Setup
        cognito_user_id = "user-123"
        requesting_user_id = "user-123"  # Same user

        now = datetime.now(UTC)
        week_ago = now - timedelta(days=7)

        mock_assignments = [
            Mock(
                status="pending",
                assignment_type="evaluate",
                priority=3,
                due_date=now + timedelta(days=1),  # Not overdue
                completed_at=None,
                created_at=now - timedelta(days=2),
            ),
            Mock(
                status="completed",
                assignment_type="record",
                priority=2,
                due_date=None,
                completed_at=now - timedelta(days=3),  # Completed this week
                created_at=now - timedelta(days=5),
            ),
            Mock(
                status="in_progress",
                assignment_type="evaluate",
                priority=1,
                due_date=now - timedelta(days=1),  # Overdue
                completed_at=None,
                created_at=now - timedelta(days=10),
            ),
        ]

        mock_db_session.query.return_value.filter.return_value.all.return_value = (
            mock_assignments
        )

        # Execute
        result = await assignment_service.get_assignment_statistics(
            cognito_user_id=cognito_user_id, requesting_user_id=requesting_user_id
        )

        # Verify
        assert result["total_assignments"] == 3
        assert result["by_status"]["pending"] == 1
        assert result["by_status"]["completed"] == 1
        assert result["by_status"]["in_progress"] == 1
        assert result["by_type"]["evaluate"] == 2
        assert result["by_type"]["record"] == 1
        assert result["overdue_count"] == 1
        assert result["completed_this_week"] == 1
        assert result["average_completion_time_hours"] is not None

    @pytest.mark.asyncio
    async def test_reassign_assignment_success(
        self, assignment_service, mock_avp_client, mock_db_session
    ):
        """Test successful assignment reassignment."""
        # Setup
        assignment_id = uuid4()
        new_assignee_cognito_id = "new-user-123"
        reassigned_by_cognito_id = "admin-123"
        reason = "Better fit for this task"

        mock_avp_client.is_authorized.return_value = Mock(
            decision=AuthorizationDecision.ALLOW
        )

        mock_assignment = Mock()
        mock_assignment.id = assignment_id
        mock_assignment.assigned_to_cognito_id = "old-user-123"
        mock_assignment.status = "in_progress"
        mock_assignment.completed_at = datetime.now(UTC)
        mock_assignment.notes = "Original notes"

        mock_new_assignee = Mock()
        mock_new_assignee.cognito_user_id = new_assignee_cognito_id

        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_assignment
        )
        mock_db_session.commit = Mock()

        with patch(
            "transcription_evaluator.services.cognito_assignment_service.get_user_by_cognito_id"
        ) as mock_get_user:
            mock_get_user.return_value = mock_new_assignee

            # Execute
            result = await assignment_service.reassign_assignment(
                assignment_id=assignment_id,
                new_assignee_cognito_id=new_assignee_cognito_id,
                reassigned_by_cognito_id=reassigned_by_cognito_id,
                reason=reason,
            )

        # Verify
        assert result is True
        assert mock_assignment.assigned_to_cognito_id == new_assignee_cognito_id
        assert mock_assignment.status == "pending"
        assert mock_assignment.completed_at is None
        assert reason in mock_assignment.notes
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_authorization_success(
        self, assignment_service, mock_avp_client, mock_user_service, mock_db_session
    ):
        """Test successful authorization check."""
        # Setup
        user_id = "user-123"
        action = "ViewAssignment"
        resource_type = "Assignment"

        mock_user_profile = Mock()
        mock_user_profile.email = "test@example.com"

        mock_user_service.cognito_client.get_user_groups.return_value = ["evaluator"]
        mock_avp_client.is_authorized.return_value = Mock(
            decision=AuthorizationDecision.ALLOW
        )

        with patch(
            "transcription_evaluator.services.cognito_assignment_service.get_user_by_cognito_id"
        ) as mock_get_user:
            mock_get_user.return_value = mock_user_profile

            # Execute
            result = await assignment_service._check_authorization(
                user_id=user_id, action=action, resource_type=resource_type
            )

        # Verify
        assert result is True
        mock_avp_client.is_authorized.assert_called_once_with(
            principal_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=None,
            principal_groups=["evaluator"],
        )

    @pytest.mark.asyncio
    async def test_check_authorization_denied(
        self, assignment_service, mock_avp_client, mock_user_service, mock_db_session
    ):
        """Test authorization check when access is denied."""
        # Setup
        user_id = "user-123"
        action = "AdminAction"
        resource_type = "System"

        mock_user_profile = Mock()
        mock_user_profile.email = "test@example.com"

        mock_user_service.cognito_client.get_user_groups.return_value = ["voice_actor"]
        mock_avp_client.is_authorized.return_value = Mock(
            decision=AuthorizationDecision.DENY
        )

        with patch(
            "transcription_evaluator.services.cognito_assignment_service.get_user_by_cognito_id"
        ) as mock_get_user:
            mock_get_user.return_value = mock_user_profile

            # Execute
            result = await assignment_service._check_authorization(
                user_id=user_id, action=action, resource_type=resource_type
            )

        # Verify
        assert result is False


@pytest.mark.asyncio
class TestCognitoAssignmentServiceIntegration:
    """Integration tests for CognitoAssignmentService with database."""

    @pytest.fixture
    def real_db_session(self):
        """Use real database session for integration tests."""
        # This would need actual database setup in a real test environment
        pytest.skip("Integration tests require database setup")

    async def test_full_assignment_workflow(self, real_db_session):
        """Test complete assignment workflow with real database."""
        # This would test creation -> status updates -> completion
        pass

    async def test_bulk_assignment_with_database(self, real_db_session):
        """Test bulk assignment operations with real database."""
        # This would test bulk operations with database constraints
        pass

    async def test_bulk_assignment_with_database(self, real_db_session):
        """Test bulk assignment operations with real database."""
        # This would test bulk operations with database constraints
        pass
