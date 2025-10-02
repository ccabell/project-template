import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch


def _load_handler(rel_parts: list[str]):
    root = Path(__file__).resolve().parents[2]
    path = root.joinpath(*rel_parts)
    spec = importlib.util.spec_from_file_location("tmp_phi", str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["tmp_phi"] = mod
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
def test_phi_detection_eventbridge_minimal(mock_boto):
    s3 = type(
        "S3",
        (),
        {
            "get_object": lambda *a, **k: {
                "Body": type(
                    "B",
                    (),
                    {
                        "read": lambda: json.dumps(
                            {
                                "conversation": [
                                    {
                                        "speaker": "A",
                                        "text": "John Doe met on 01/01/2020",
                                    },
                                ],
                            },
                        ).encode(),
                    },
                )(),
            },
        },
    )()
    cm = type(
        "CM",
        (),
        {
            "detect_phi": lambda *a, **k: {
                "Entities": [
                    {"BeginOffset": 0, "EndOffset": 8, "Type": "NAME", "Score": 0.99},
                ],
                "ModelVersion": "1",
            },
        },
    )()
    ddb = type(
        "D",
        (),
        {"put_item": lambda *a, **k: None, "update_item": lambda *a, **k: None},
    )()
    sns = type("SNS", (), {"publish": lambda *a, **k: None})()
    ev = type("EV", (), {"put_events": lambda *a, **k: None})()
    mock_boto.side_effect = [s3, cm, ddb, sns, ev]

    os.environ["BRONZE_BUCKET"] = "bronze"
    os.environ["SILVER_BUCKET"] = "silver"
    os.environ["CONSULTATION_METADATA_TABLE"] = "table"
    os.environ["PHI_DETECTION_TOPIC_ARN"] = "arn:aws:sns:xx:1:t"

    handler = _load_handler(
        ["consultation_pipeline", "lambda", "phi_detection_processor", "index.py"],
    )

    event = {
        "source": "consultation.pipeline",
        "detail": {"consultationId": "c1", "tenantId": "t1"},
    }
    resp = handler(event, DummyContext())
    assert resp["statusCode"] == 200
