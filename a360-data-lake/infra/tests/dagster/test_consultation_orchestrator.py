import importlib.util
import sys
from pathlib import Path


def _load_handler(rel_parts: list[str]):
    root = Path(__file__).resolve().parents[2]
    path = root.joinpath(*rel_parts)
    spec = importlib.util.spec_from_file_location("tmp_orch", str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["tmp_orch"] = mod
    assert spec
    assert spec.loader
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod.handler


def test_orchestrator_accepts():
    handler = _load_handler(
        ["dagster", "lambda", "consultation_orchestrator", "index.py"],
    )

    class DummyContext:
        function_name = "test"
        memory_limit_in_mb = 128
        invoked_function_arn = "arn:aws:lambda:us-east-1:277707121008:function:test"
        aws_request_id = "req-123"

    # Test with valid pipeline event
    event = {
        "source": "consultation.pipeline",
        "consultation_id": "test-123",
        "tenant_id": "tenant-456",
    }
    resp = handler(event, DummyContext())
    assert resp["statusCode"] == 202
