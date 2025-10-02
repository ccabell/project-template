"""Global pytest configuration and fixtures for CDK testing."""

import os
import sys
from pathlib import Path

import pytest
import requests
from aws_cdk import App, Environment

# Add the infra directory to Python path for imports
infra_path = Path(__file__).parent.parent
if str(infra_path) not in sys.path:
    sys.path.insert(0, str(infra_path))


@pytest.fixture(scope="session", autouse=True)
def configure_test_environment():
    """Configure environment variables for consistent testing."""
    test_env = {
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_REGION": "us-east-1",
        "CDK_DEFAULT_REGION": "us-east-1",
        "CDK_DEFAULT_ACCOUNT": "123456789012",
        "CDK_DISABLE_VERSION_CHECK": "true",
        # Prevent actual AWS API calls during testing
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_SECURITY_TOKEN": "testing",
        "AWS_SESSION_TOKEN": "testing",
    }

    for key, value in test_env.items():
        if key not in os.environ:
            os.environ[key] = value


@pytest.fixture
def cdk_app():
    """Create a fresh CDK App instance for each test."""
    return App()


@pytest.fixture(scope="session")
def aws_environment():
    """Provide AWS environment configuration for testing."""
    return Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT", "123456789012"),
        region=os.environ.get("CDK_DEFAULT_REGION", "us-east-1"),
    )


# LakeFS testing configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "lakefs: mark test as requiring LakeFS server",
    )


@pytest.fixture(scope="session")
def lakefs_available():
    """Check if LakeFS is available for testing."""
    try:
        response = requests.get("http://localhost:8000/api/v1/healthcheck", timeout=5)
        return response.status_code in [200, 204]
    except Exception:
        return False


def pytest_collection_modifyitems(config, items):
    """Skip LakeFS tests if server is not available."""
    lakefs_skip = pytest.mark.skip(reason="LakeFS server not available at localhost:8000")

    # Check if LakeFS is available
    try:
        response = requests.get("http://localhost:8000/api/v1/healthcheck", timeout=2)
        lakefs_available = response.status_code in [200, 204]
    except Exception:
        lakefs_available = False

    if not lakefs_available:
        for item in items:
            if "lakefs" in item.nodeid.lower() or item.get_closest_marker("lakefs"):
                item.add_marker(lakefs_skip)
