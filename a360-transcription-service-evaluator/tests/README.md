# AWS Cognito RBAC Test Suite

This test suite provides comprehensive testing for the AWS-first Role-Based Access Control (RBAC) system implemented for the A360 Transcription Service Evaluator.

## Test Structure

### Test Categories

- **Unit Tests** (`test_cognito_user_service.py`, `test_cognito_assignment_service.py`)
  - Test individual service classes with mocked dependencies
  - Focus on business logic and error handling
  - Fast execution, no external dependencies

- **Integration Tests** (`test_api_integration.py`)
  - Test FastAPI endpoints with mocked services
  - Validate request/response formats and HTTP status codes
  - Test middleware and security features

- **Configuration Tests** (`test_configuration.py`)
  - Test settings management and environment variable loading
  - Database connection configuration
  - AWS service configuration validation

- **End-to-End Workflow Tests** (`test_e2e_workflows.py`)
  - Complete user workflows from authentication to task completion
  - Role-based permission testing across all user types
  - Error handling and recovery scenarios

## Test Markers

Use pytest markers to run specific test categories:

```bash
# Run only unit tests (fastest)
pytest -m unit

# Run integration tests
pytest -m integration

# Run end-to-end tests
pytest -m e2e

# Run tests requiring AWS services
pytest -m aws

# Skip slow tests
pytest -m "not slow"
```

## Running Tests

### Prerequisites

```bash
# Install test dependencies
uv add --dev pytest pytest-asyncio pytest-cov httpx pytest-watcher pytest-xdist

# Install project dependencies
uv install
```

### Basic Test Execution

```bash
# Run all tests with coverage
pytest

# Run specific test file
pytest tests/test_cognito_user_service.py

# Run specific test function
pytest tests/test_cognito_user_service.py::TestCognitoUserService::test_authenticate_user_success

# Run tests with verbose output
pytest -v

# Run tests and stop on first failure
pytest -x
```

### Coverage Reports

```bash
# Generate HTML coverage report
pytest --cov-report=html

# View coverage in terminal
pytest --cov-report=term-missing

# Set minimum coverage threshold
pytest --cov-fail-under=90
```

### Test Development Mode

```bash
# Watch for file changes and re-run tests
pytest --watch

# Run tests in parallel (if pytest-xdist installed)
pytest -n auto
```

## Test Configuration

### Environment Variables

Set these environment variables for comprehensive testing:

```bash
export TRANSCRIPTION_EVALUATOR_COGNITO_USER_POOL_ID="us-east-1_TEST123456"
export TRANSCRIPTION_EVALUATOR_COGNITO_CLIENT_ID="test-client-id-123456"
export TRANSCRIPTION_EVALUATOR_VERIFIED_PERMISSIONS_POLICY_STORE_ID="test-policy-store-123"
export TRANSCRIPTION_EVALUATOR_AWS_REGION="us-east-1"
export TRANSCRIPTION_EVALUATOR_DATABASE_URL="postgresql://test:test@localhost/test_transcription_evaluator"
```

### AWS Services Testing

For tests that require actual AWS services (marked with `@pytest.mark.aws`):

1. Configure AWS credentials:
   ```bash
   aws configure --profile GenAI-Platform-Dev
   ```

2. Deploy test infrastructure:
   ```bash
   cd cdk
   cdk deploy CognitoRbacStack --profile GenAI-Platform-Dev
   ```

3. Run AWS integration tests:
   ```bash
   pytest -m aws
   ```

## Test Fixtures

The test suite includes comprehensive fixtures in `conftest.py`:

- **User Fixtures**: Sample user profiles for all roles (admin, evaluator, reviewer, voice_actor)
- **Assignment Fixtures**: Sample script assignments with various statuses
- **Authentication Fixtures**: Mock JWT tokens and Cognito claims
- **Database Fixtures**: Mock database sessions and query results
- **AWS Fixtures**: Mock authorization responses and service clients

## Key Test Scenarios

### Authentication Workflows
- User login with correct/incorrect credentials
- JWT token validation and extraction
- User profile creation and management
- Role-based user creation permissions

### Assignment Management
- Assignment creation with authorization checks
- Bulk assignment operations
- Assignment status updates and completion
- Assignment reassignment between users
- Assignment statistics and reporting

### Role-Based Access Control
- **Admin**: Full system access, user management, assignment creation
- **Evaluator**: Assignment viewing/updating, profile management
- **Reviewer**: Review-specific permissions, limited assignment access
- **Voice Actor**: Minimal permissions, own assignments only

### Error Handling
- Authentication failures and recovery
- Permission denied scenarios
- Service errors and graceful degradation
- Invalid input validation
- Database connection failures

## Performance Testing

The test suite includes performance validation for:

- Bulk operations (100+ scripts, 50+ users)
- Large dataset handling
- Concurrent user scenarios
- Database query optimization

Run performance tests:
```bash
pytest -m slow -v
```

## Continuous Integration

For CI/CD pipelines, use:

```bash
# Skip AWS integration tests in CI
pytest -m "not aws"

# Run with minimal output
pytest --tb=line --quiet

# Generate XML coverage for CI tools
pytest --cov-report=xml
```

## Test Data Management

The test suite uses:
- **Mock data**: For unit and integration tests (no external dependencies)
- **Fixture data**: Realistic sample data for comprehensive testing
- **Environment isolation**: Each test runs in isolation with clean state

## Debugging Tests

### Common Issues

1. **Import Errors**: Ensure `PYTHONPATH` includes the backend directory
2. **Async Test Failures**: Use `@pytest.mark.asyncio` for async test functions
3. **Mock Issues**: Verify mock objects match the actual service interfaces
4. **Database Tests**: Ensure test database is accessible and properly configured

### Debug Commands

```bash
# Run with debug output
pytest -s -vv

# Drop into debugger on failure
pytest --pdb

# Run specific test with full traceback
pytest --tb=long tests/test_cognito_user_service.py::test_authenticate_user_success
```

## Contributing Tests

When adding new tests:

1. **Follow naming conventions**: `test_*.py` files, `test_*` functions
2. **Use appropriate markers**: Mark tests with `@pytest.mark.unit`, `@pytest.mark.integration`, etc.
3. **Mock external dependencies**: Use mocks for AWS services, database operations
4. **Test error conditions**: Include negative test cases and edge conditions
5. **Document complex scenarios**: Add docstrings explaining test purpose and setup

## Test Metrics

Current test coverage targets:
- **Overall coverage**: >80%
- **Service classes**: >90%
- **API endpoints**: >85%
- **Configuration**: >75%

Run coverage analysis:
```bash
pytest --cov-report=term-missing --cov-fail-under=80
```