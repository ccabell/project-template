import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch


def _load_handler(rel_parts: list[str]):
    root = Path(__file__).resolve().parents[2]
    path = root.joinpath(*rel_parts)
    spec = importlib.util.spec_from_file_location("tmp_textract", str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["tmp_textract"] = mod
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
def test_textract_completion_minimal(mock_boto):
    # Mock clients in call order: s3, textract, events, macie2, dynamodb
    textract = type(
        "T",
        (),
        {
            "get_document_analysis": lambda *a, **k: {
                "Blocks": [],
                "DocumentMetadata": {"Pages": 1},
            },
        },
    )()
    s3 = type("S3", (), {"put_object": lambda *a, **k: None})()
    ev = type("EV", (), {"put_events": lambda *a, **k: None})()
    macie = type(
        "M",
        (),
        {"create_classification_job": lambda *a, **k: {"jobId": "macie-1"}},
    )()
    ddb = type("D", (), {"put_item": lambda *a, **k: None})()
    mock_boto.side_effect = [s3, textract, ev, macie, ddb]

    import os

    os.environ["SILVER_BUCKET"] = "silver"
    os.environ["JOB_STATUS_TABLE"] = "table"

    handler = _load_handler(
        [
            "consultation_pipeline",
            "lambda",
            "textract_completion_processor",
            "index.py",
        ],
    )

    sns_event = {
        "Records": [
            {
                "Sns": {
                    "Message": json.dumps({"JobId": "job-1", "Status": "SUCCEEDED"}),
                },
            },
        ],
    }

    resp = handler(sns_event, DummyContext())
    assert resp["statusCode"] == 200
