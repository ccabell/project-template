"""Unit tests for CognitoUserService aligned with new infrastructure.

Tests cover authentication, user management, and profile operations using
mocked Cognito and Verified Permissions clients and a mocked DB session.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from transcription_evaluator.aws.cognito_client import CognitoUserInfo
from transcription_evaluator.aws.verified_permissions import AuthorizationDecision
from transcription_evaluator.services.cognito_user_service import CognitoUserService


class TestCognitoUserService:
    """Test cases for CognitoUserService."""

    @pytest.fixture
    def mock_cognito_client(self):
        client = Mock()
        client.authenticate_user = AsyncMock()
        client.create_user = AsyncMock()
        client.get_user_groups = AsyncMock()
        client.delete_user = AsyncMock()
        client.add_user_to_group = AsyncMock()
        client.remove_user_from_group = AsyncMock()
        client.list_users = AsyncMock()
        return client

    @pytest.fixture
    def mock_avp_client(self):
        client = Mock()
        client.is_authorized = AsyncMock()
        return client

    @pytest.fixture
    def mock_db_session(self):
        with patch(
            "transcription_evaluator.services.cognito_user_service.get_database_session"
        ) as mock:
            session = Mock()
            mock.return_value.__enter__.return_value = session
            yield session

    @pytest.fixture
    def user_service(self, mock_cognito_client, mock_avp_client):
        return CognitoUserService(
            cognito_client=mock_cognito_client, avp_client=mock_avp_client
        )

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, user_service, mock_cognito_client):
        email = "test@example.com"
        password = "testpassword123"
        cognito_user = CognitoUserInfo(
            user_id="cognito-123",
            username=email,
            email=email,
            name="Test User",
            groups=["evaluator"],
            attributes={"email": email, "name": "Test User"},
            is_active=True,
            email_verified=True,
            created_at=datetime.now(UTC),
            last_login=None,
        )
        mock_cognito_client.authenticate_user.return_value = cognito_user
        with patch.object(
            CognitoUserService, "_get_or_create_user_profile", new=AsyncMock()
        ) as mock_get_or_create:
            profile = Mock()
            profile.id = uuid4()
            profile.department = "Engineering"
            profile.role_level = 2
            profile.preferences = {"theme": "dark"}
            mock_get_or_create.return_value = profile
            result = await user_service.authenticate_user(email, password)
        assert result is not None
        assert result["cognito_user_id"] == "cognito-123"
        assert result["email"] == email
        mock_cognito_client.authenticate_user.assert_called_once_with(email, password)

    @pytest.mark.asyncio
    async def test_authenticate_user_failure(self, user_service, mock_cognito_client):
        mock_cognito_client.authenticate_user.return_value = None
        result = await user_service.authenticate_user("test@example.com", "wrong")
        assert result is None

    @pytest.mark.asyncio
    async def test_create_user_success(
        self, user_service, mock_cognito_client, mock_avp_client, mock_db_session
    ):
        email = "newuser@example.com"
        name = "New User"
        temp_password = "TempPassword123!"
        mock_avp_client.is_authorized.return_value = Mock(
            decision=AuthorizationDecision.ALLOW
        )
        created = CognitoUserInfo(
            user_id="new-user-123",
            username=email,
            email=email,
            name=name,
            groups=["evaluator"],
            attributes={"email": email, "name": name},
            is_active=True,
            email_verified=True,
            created_at=datetime.now(UTC),
            last_login=None,
        )
        mock_cognito_client.create_user.return_value = created

        class DummyProfile:
            def __init__(self, **kwargs):
                self.id = uuid4()
                self.cognito_user_id = kwargs.get("cognito_user_id")
                self.email = kwargs.get("email")
                self.full_name = kwargs.get("full_name")
                self.department = kwargs.get("department")
                self.role_level = kwargs.get("role_level", 4)
                self.preferences = kwargs.get("preferences", {})
                self.created_at = datetime.now(UTC)

        mock_db_session.add = Mock()
        mock_db_session.commit = Mock()
        mock_db_session.refresh = Mock()
        with patch(
            "transcription_evaluator.services.cognito_user_service.UserProfile",
            DummyProfile,
        ):
            result = await user_service.create_user(
                email=email,
                name=name,
                temporary_password=temp_password,
                groups=["evaluator"],
                requesting_user_id="admin-123",
            )
        assert result["email"] == email
        assert result["name"] == name
        mock_cognito_client.create_user.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_user_unauthorized(self, user_service, mock_avp_client):
        mock_avp_client.is_authorized.return_value = Mock(
            decision=AuthorizationDecision.DENY
        )
        with pytest.raises(PermissionError):
            await user_service.create_user(
                email="x@example.com",
                name="X",
                temporary_password="Temp123!",
                requesting_user_id="user-123",
            )

    @pytest.mark.asyncio
    async def test_get_user_profile_success(
        self, user_service, mock_cognito_client, mock_db_session
    ):
        cognito_user_id = "user-123"
        profile = Mock()
        profile.cognito_user_id = cognito_user_id
        profile.email = "test@example.com"
        profile.full_name = "Test User"
        profile.department = "Engineering"
        profile.role_level = 2
        profile.preferences = {"theme": "dark"}
        profile.is_active = True
        profile.created_at = datetime.now(UTC)
        profile.updated_at = datetime.now(UTC)
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            profile
        )
        mock_cognito_client.get_user_groups.return_value = ["evaluator"]
        result = await user_service.get_user_profile(cognito_user_id)
        assert result is not None
        assert result["cognito_user_id"] == cognito_user_id
        assert result["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_user_profile_not_found(self, user_service, mock_db_session):
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        result = await user_service.get_user_profile("missing")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_user_profile_success(
        self, user_service, mock_avp_client, mock_db_session
    ):
        mock_avp_client.is_authorized.return_value = Mock(
            decision=AuthorizationDecision.ALLOW
        )
        profile = Mock()
        profile.full_name = "Old"
        profile.department = "Eng"
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            profile
        )
        mock_db_session.commit = Mock()
        ok = await user_service.update_user_profile(
            cognito_user_id="user-123",
            updates={"full_name": "New", "department": "Marketing"},
            requesting_user_id="admin-1",
        )
        assert ok is True
        assert profile.full_name == "New"
        assert profile.department == "Marketing"
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_user_to_group_success(
        self, user_service, mock_cognito_client, mock_avp_client, mock_db_session
    ):
        mock_avp_client.is_authorized.return_value = Mock(
            decision=AuthorizationDecision.ALLOW
        )
        profile = Mock()
        profile.email = "member@example.com"
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            profile
        )
        mock_cognito_client.add_user_to_group.return_value = True
        ok = await user_service.add_user_to_group(
            "user-123", "evaluator", requesting_user_id="admin-1"
        )
        assert ok is True
        mock_cognito_client.add_user_to_group.assert_called_once_with(
            "member@example.com", "evaluator"
        )

    @pytest.mark.asyncio
    async def test_delete_user_success(
        self, user_service, mock_cognito_client, mock_avp_client, mock_db_session
    ):
        mock_avp_client.is_authorized.return_value = Mock(
            decision=AuthorizationDecision.ALLOW
        )
        profile = Mock()
        profile.email = "x@example.com"
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            profile
        )
        mock_db_session.delete = Mock()
        mock_db_session.commit = Mock()
        mock_cognito_client.delete_user.return_value = True
        ok = await user_service.delete_user("user-123", requesting_user_id="admin-1")
        assert ok is True
        mock_cognito_client.delete_user.assert_called_once_with("x@example.com")
        mock_db_session.delete.assert_called_once_with(profile)
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_users_success(
        self, user_service, mock_cognito_client, mock_avp_client, mock_db_session
    ):
        # Bypass internal authorization check triggered by requesting_user_id
        user_service._check_authorization = AsyncMock(return_value=True)
        users = [
            CognitoUserInfo(
                user_id="user-1",
                username="user1@example.com",
                email="user1@example.com",
                name="User One",
                groups=["evaluator"],
                attributes={"email": "user1@example.com", "name": "User One"},
                is_active=True,
                email_verified=True,
                created_at=datetime.now(UTC),
                last_login=None,
            ),
            CognitoUserInfo(
                user_id="user-2",
                username="user2@example.com",
                email="user2@example.com",
                name="User Two",
                groups=["voice_actor"],
                attributes={"email": "user2@example.com", "name": "User Two"},
                is_active=True,
                email_verified=True,
                created_at=datetime.now(UTC),
                last_login=None,
            ),
        ]
        mock_cognito_client.list_users.return_value = {
            "users": users,
            "pagination_token": None,
            "total_returned": 2,
        }
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        result = await user_service.list_users(limit=10, requesting_user_id="admin-1")
        assert len(result) == 2
        assert result[0]["cognito_user_id"] == "user-1"
        mock_cognito_client.list_users.assert_called_once()


@pytest.mark.asyncio
class TestCognitoUserServiceIntegration:
    @pytest.fixture
    def real_db_session(self):
        pytest.skip("Integration tests require database setup")

    async def test_create_and_retrieve_user_profile(self, real_db_session):
        pass

    async def test_user_authentication_flow(self, real_db_session):
        pass
