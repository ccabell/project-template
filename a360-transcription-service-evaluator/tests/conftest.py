"""Pytest configuration and shared fixtures for AWS Cognito RBAC tests.

This module provides common test fixtures and configuration for testing
the AWS-first RBAC implementation with Cognito integration.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timedelta
from uuid import uuid4

# Mock the AWS components for testing
class MockCognitoClaims:
    def __init__(self, sub, email, name, groups, email_verified, token_use, exp):
        self.sub = sub
        self.email = email
        self.name = name
        self.groups = groups
        self.email_verified = email_verified
        self.token_use = token_use
        self.exp = exp

class MockAuthorizationDecision:
    ALLOW = "ALLOW"
    DENY = "DENY"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_cognito_claims():
    """Sample Cognito JWT claims for testing."""
    return {
        "sub": "test-user-123",
        "email": "test@example.com", 
        "name": "Test User",
        "groups": ["evaluator"],
        "email_verified": True,
        "token_use": "access",
        "exp": 1234567890
    }


@pytest.fixture
def mock_cognito_claims(sample_cognito_claims):
    """Mock CognitoClaims object for testing."""
    return MockCognitoClaims(**sample_cognito_claims)


@pytest.fixture
def sample_user_profiles():
    """Sample user profiles for different roles."""
    base_time = datetime.utcnow()
    
    return {
        "admin": {
            "id": str(uuid4()),
            "cognito_user_id": "admin-123",
            "email": "admin@example.com",
            "full_name": "Admin User",
            "department": "IT",
            "role_level": 1,
            "groups": ["admin"],
            "preferences": {"theme": "dark"},
            "is_active": True,
            "created_at": base_time.isoformat(),
            "updated_at": base_time.isoformat()
        },
        "evaluator": {
            "id": str(uuid4()),
            "cognito_user_id": "evaluator-456",
            "email": "evaluator@example.com",
            "full_name": "Evaluator User",
            "department": "Quality Assurance",
            "role_level": 3,
            "groups": ["evaluator"],
            "preferences": {"theme": "light"},
            "is_active": True,
            "created_at": base_time.isoformat(),
            "updated_at": base_time.isoformat()
        },
        "reviewer": {
            "id": str(uuid4()),
            "cognito_user_id": "reviewer-789",
            "email": "reviewer@example.com",
            "full_name": "Reviewer User",
            "department": "Quality Assurance",
            "role_level": 2,
            "groups": ["reviewer"],
            "preferences": {"theme": "auto"},
            "is_active": True,
            "created_at": base_time.isoformat(),
            "updated_at": base_time.isoformat()
        },
        "voice_actor": {
            "id": str(uuid4()),
            "cognito_user_id": "voice-actor-012",
            "email": "voiceactor@example.com",
            "full_name": "Voice Actor User",
            "department": "Content Creation",
            "role_level": 4,
            "groups": ["voice_actor"],
            "preferences": {"theme": "light"},
            "is_active": True,
            "created_at": base_time.isoformat(),
            "updated_at": base_time.isoformat()
        }
    }


@pytest.fixture
def sample_scripts():
    """Sample script data for testing."""
    base_time = datetime.utcnow()
    
    return [
        {
            "id": str(uuid4()),
            "title": "Dermatology Consultation Script 1",
            "content": "This is a sample script for dermatology consultation...",
            "difficulty_level": 3,
            "seed_terms": ["acne", "rosacea", "dermatitis"],
            "language": "english",
            "word_count": 500,
            "created_at": base_time.isoformat(),
            "updated_at": base_time.isoformat()
        },
        {
            "id": str(uuid4()),
            "title": "Pediatric Consultation Script 2",
            "content": "This is a sample script for pediatric consultation...",
            "difficulty_level": 2,
            "seed_terms": ["pediatric", "child", "vaccination"],
            "language": "english",
            "word_count": 400,
            "created_at": base_time.isoformat(),
            "updated_at": base_time.isoformat()
        }
    ]


@pytest.fixture
def sample_assignments(sample_scripts, sample_user_profiles):
    """Sample assignment data for testing."""
    base_time = datetime.utcnow()
    
    return [
        {
            "id": str(uuid4()),
            "script_id": sample_scripts[0]["id"],
            "script_title": sample_scripts[0]["title"],
            "script_difficulty": sample_scripts[0]["difficulty_level"],
            "assigned_to_cognito_id": sample_user_profiles["evaluator"]["cognito_user_id"],
            "assigned_to_name": sample_user_profiles["evaluator"]["full_name"],
            "assigned_by_cognito_id": sample_user_profiles["admin"]["cognito_user_id"],
            "assigned_by_name": sample_user_profiles["admin"]["full_name"],
            "assignment_type": "evaluate",
            "status": "pending",
            "priority": 3,
            "due_date": (base_time.replace(hour=23, minute=59)).isoformat(),
            "notes": None,
            "created_at": base_time.isoformat(),
            "updated_at": base_time.isoformat(),
            "completed_at": None
        },
        {
            "id": str(uuid4()),
            "script_id": sample_scripts[1]["id"],
            "script_title": sample_scripts[1]["title"],
            "script_difficulty": sample_scripts[1]["difficulty_level"],
            "assigned_to_cognito_id": sample_user_profiles["voice_actor"]["cognito_user_id"],
            "assigned_to_name": sample_user_profiles["voice_actor"]["full_name"],
            "assigned_by_cognito_id": sample_user_profiles["admin"]["cognito_user_id"],
            "assigned_by_name": sample_user_profiles["admin"]["full_name"],
            "assignment_type": "record",
            "status": "completed",
            "priority": 2,
            "due_date": None,
            "notes": "Completed successfully",
            "created_at": (base_time - timedelta(days=2)).isoformat(),
            "updated_at": (base_time - timedelta(days=1)).isoformat(),
            "completed_at": (base_time - timedelta(days=1)).isoformat()
        }
    ]


@pytest.fixture
def mock_authorization_responses():
    """Mock authorization responses for different scenarios."""
    return {
        "admin_allow": Mock(decision=MockAuthorizationDecision.ALLOW),
        "admin_deny": Mock(decision=MockAuthorizationDecision.DENY),
        "evaluator_allow": Mock(decision=MockAuthorizationDecision.ALLOW),
        "evaluator_deny": Mock(decision=MockAuthorizationDecision.DENY),
        "voice_actor_allow": Mock(decision=MockAuthorizationDecision.ALLOW),
        "voice_actor_deny": Mock(decision=MockAuthorizationDecision.DENY)
    }


@pytest.fixture
def mock_database_session():
    """Mock database session for testing."""
    session = Mock()
    session.query = Mock()
    session.add = Mock()
    session.commit = Mock()
    session.rollback = Mock()
    session.close = Mock()
    session.refresh = Mock()
    session.delete = Mock()
    session.execute = Mock()
    return session


@pytest.fixture
def aws_environment_variables():
    """AWS environment variables for testing."""
    return {
        'TRANSCRIPTION_EVALUATOR_COGNITO_USER_POOL_ID': 'us-east-1_TEST123456',
        'TRANSCRIPTION_EVALUATOR_COGNITO_CLIENT_ID': 'test-client-id-123456',
        'TRANSCRIPTION_EVALUATOR_VERIFIED_PERMISSIONS_POLICY_STORE_ID': 'test-policy-store-123',
        'TRANSCRIPTION_EVALUATOR_AWS_REGION': 'us-east-1',
        'TRANSCRIPTION_EVALUATOR_AWS_PROFILE': 'test-profile'
    }


@pytest.fixture
def jwt_tokens():
    """Sample JWT tokens for different users."""
    return {
        "admin": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.admin.token",
        "evaluator": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.evaluator.token",
        "reviewer": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.reviewer.token",
        "voice_actor": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.voice_actor.token",
        "invalid": "invalid.jwt.token",
        "expired": "expired.jwt.token"
    }


@pytest.fixture
def test_assignment_statistics():
    """Sample assignment statistics for testing."""
    return {
        "total_assignments": 15,
        "by_status": {
            "pending": 5,
            "in_progress": 3,
            "completed": 6,
            "skipped": 1
        },
        "by_type": {
            "evaluate": 8,
            "record": 4,
            "review": 3
        },
        "by_priority": {
            1: 2,
            2: 5,
            3: 6,
            4: 2
        },
        "overdue_count": 2,
        "completed_this_week": 4,
        "average_completion_time_hours": 18.5
    }


# Test markers for different test categories
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.e2e = pytest.mark.e2e
pytest.mark.aws = pytest.mark.aws
pytest.mark.slow = pytest.mark.slow


# Test configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "aws: Tests requiring AWS services")
    config.addinivalue_line("markers", "slow: Slow running tests")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add default markers."""
    for item in items:
        # Add unit marker to tests without other markers
        if not any(item.iter_markers()):
            item.add_marker(pytest.mark.unit)
        
        # Add slow marker to tests with AWS integration
        if item.get_closest_marker("aws"):
            item.add_marker(pytest.mark.slow)