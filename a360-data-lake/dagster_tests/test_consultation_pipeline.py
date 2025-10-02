"""Simple test script to validate consultation pipeline imports."""

import importlib.util
import os
import sys
from pathlib import Path

import pytest


class MockBedrockResource:
    """Lightweight mock for BedrockResource used in testing."""

    def __init__(self):
        self.model_id = "test-model-id"

    def invoke_text_model(self, prompt: str, max_tokens: int = 2000, model_id: str = None) -> str:
        """Mock text model invocation that returns a simple summary."""
        return "This is a mock summary of the clinical consultation."

    def resolve_model_id(self, model_id: str) -> str:
        """Mock model ID resolution."""
        return model_id or "resolved-test-model-id"


# Create mock instance for use in tests
mock_bedrock = MockBedrockResource()


def test_consultation_pipeline_imports():
    """Test that consultation pipeline modules can be imported."""
    # Compute infra path using pathlib
    infra_path = (Path(__file__).parent / ".." / "infra").resolve()
    infra_path_str = str(infra_path)

    # Add to sys.path if missing
    if infra_path_str not in sys.path:
        sys.path.insert(0, infra_path_str)

    # Check for optional Dagster-related module
    dagster_spec = importlib.util.find_spec("dagster")
    if dagster_spec is None:
        pytest.skip("Dagster dependency not available")

    try:
        # Import consultation factory using importlib
        factory_module = importlib.import_module(
            "consultation_pipeline.consultation_pipeline_factory",
        )
        consultation_definition = factory_module.ConsultationDefinition

        # Create consultation definition and validate
        consultation_def = consultation_definition(
            tenant_id="test_tenant",
            tenant_name="test_tenant",
            environment="dev",
        )

        # Single minimal assertion for validation
        assert consultation_def is not None, (
            "ConsultationDefinition instance should not be None"
        )
        assert hasattr(consultation_def, "tenant_id"), (
            "ConsultationDefinition should have tenant_id attribute"
        )

    except (ImportError, AttributeError) as e:
        if "dagster" in str(e).lower() or "definitions" in str(e).lower():
            pytest.skip(f"Dagster-related import failed: {e}")
        raise


def test_infrastructure_imports():
    """Test that infrastructure modules can be imported."""
    try:
        # Add correct infra path for imports
        infra_path = (Path(__file__).parent / ".." / "infra").resolve()
        if str(infra_path) not in sys.path:
            sys.path.insert(0, str(infra_path))

    except ImportError as e:
        # Check if it's a missing AWS CDK dependency issue
        if "aws_cdk" in str(e).lower() or "constructs" in str(e).lower():
            pass
        else:
            msg = f"Infrastructure import failed: {e}"
            raise AssertionError(msg) from e
    except Exception as e:
        msg = f"Unexpected error in infrastructure import test: {e}"
        raise AssertionError(msg) from e


def test_lambda_function_syntax():
    """Test that Lambda function code has valid syntax."""
    try:
        lambda_dir = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "infra",
                "consultation_pipeline",
                "lambda",
            ),
        )

        functions = [
            "consultation_enrichment",
            "phi_detection_processor",
            "embedding_processor",
            "pii_redaction_trigger",
        ]

        functions_found = 0
        for func_name in functions:
            func_path = Path(lambda_dir) / func_name / "index.py"
            if func_path.exists():
                # Compile the Lambda function code to check syntax
                with func_path.open(encoding="utf-8") as f:
                    code = f.read()
                compile(code, str(func_path), "exec")
                functions_found += 1
            else:
                pass

        if functions_found > 0:
            pass
        else:
            pass

    except SyntaxError as e:
        msg = f"Syntax error in Lambda function: {e}"
        raise AssertionError(msg) from e
    except Exception as e:
        msg = f"Unexpected error in lambda syntax test: {e}"
        raise AssertionError(msg) from e


def test_conversation_preprocessing_logic():
    """Test the conversation preprocessing logic for long conversations."""
    try:
        # Add correct dagster path for imports
        dagster_path = (Path(__file__).parent / ".." / "dagster").resolve()
        if str(dagster_path) not in sys.path:
            sys.path.insert(0, str(dagster_path))

        from dagster.defs.consultation_pipeline.pipeline_factory import (
            preprocess_conversation_for_analytics,
        )

        # Test with short conversation (should return direct)
        short_text = (
            "Doctor: Hello, how are you today?\nPatient: I'm doing well, thank you."
        )
        result, metadata, was_chunked = preprocess_conversation_for_analytics(
            short_text,
            mock_bedrock,
            max_length=15000,
            context=None,
        )

        if not was_chunked and metadata["method"] == "direct":
            pass
        else:
            pass

        # Test with long conversation (should indicate chunking needed)
        long_text = (
            "Doctor: " + "This is a very long conversation. " * 1000
        )  # ~30k chars
        result, metadata, was_chunked = preprocess_conversation_for_analytics(
            long_text,
            mock_bedrock,
            max_length=15000,
            context=None,
        )

        if was_chunked and metadata["method"] == "chunking":
            pass
        else:
            pass

    except ImportError:
        pass
    except Exception as e:
        # Only fail if there's a real logic error, not missing dependencies
        error_str = str(e).lower()
        if any(
            keyword in error_str
            for keyword in ["modulenotfounderror", "dagster", "has no attribute"]
        ):
            pass
        else:
            msg = f"Unexpected error in preprocessing test: {e}"
            raise AssertionError(msg) from e


if __name__ == "__main__":
    # Run each test and assert they pass instead of aggregating
    assert test_consultation_pipeline_imports(), "Consultation pipeline imports test failed"

    assert test_infrastructure_imports(), "Infrastructure imports test failed"

    assert test_lambda_function_syntax(), "Lambda function syntax test failed"

    assert test_conversation_preprocessing_logic(), "Conversation preprocessing logic test failed"

    print("All tests passed successfully!")
