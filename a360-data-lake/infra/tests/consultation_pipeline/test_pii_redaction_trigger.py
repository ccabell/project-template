import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch


def _load_handler(rel_parts: list[str]):
    root = Path(__file__).resolve().parents[2]
    path = root.joinpath(*rel_parts)
    spec = importlib.util.spec_from_file_location("tmp_pii", str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["tmp_pii"] = mod
    assert spec
    assert spec.loader
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod.handler


class DummyContext:
    function_name = "test"
    memory_limit_in_mb = 128
    invoked_function_arn = "arn:aws:lambda:us-east-1:277707121008:function:test"
    aws_request_id = "req-123"


@patch("boto3.client")
def test_pii_redaction_s3_event_minimal(mock_boto):
    s3 = object()
    macie = object()
    textract = type(
        "T",
        (),
        {"start_document_analysis": lambda *a, **k: {"JobId": "jid"}},
    )()
    ddb = type("D", (), {"put_item": lambda *a, **k: None})()
    sns = object()
    mock_boto.side_effect = [s3, macie, textract, ddb, sns]

    os.environ["LANDING_BUCKET"] = "landing"
    os.environ["SILVER_BUCKET"] = "silver"
    os.environ["JOB_STATUS_TABLE"] = "table"
    os.environ["PII_DETECTION_TOPIC_ARN"] = "arn:aws:sns:xx:1:t"
    os.environ["TEXTRACT_SNS_ROLE_ARN"] = "arn:aws:iam::277707121008:role/TextractSNSRole"

    handler = _load_handler(
        ["consultation_pipeline", "lambda", "pii_redaction_trigger", "index.py"],
    )

    event = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "landing"},
                    "object": {"key": "documents/t/123/intake.pdf"},
                },
            },
        ],
    }

    resp = handler(event, DummyContext())
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["processed_count"] == 1
