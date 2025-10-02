import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch


def _load_handler(rel_parts: list[str]):
    root = Path(__file__).resolve().parents[2]
    path = root.joinpath(*rel_parts)
    spec = importlib.util.spec_from_file_location("tmp_enrich", str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["tmp_enrich"] = mod
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
def test_enrichment_from_eventbridge_minimal(mock_boto):
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
                                    {"speaker": "A", "text": "Hello patient"},
                                ],
                            },
                        ).encode(),
                    },
                )(),
            },
            "put_object": lambda *a, **k: None,
        },
    )()
    br = type(
        "BR",
        (),
        {
            "invoke_model": lambda *a, **k: {
                "body": type(
                    "B2",
                    (),
                    {
                        "read": lambda: json.dumps(
                            {
                                "content": [
                                    {
                                        "text": json.dumps(
                                            {
                                                "consultation_quality_score": 7,
                                                "consultation_type": "initial",
                                            },
                                        ),
                                    },
                                ],
                            },
                        ).encode(),
                    },
                )(),
            },
        },
    )()
    ddb = type("D", (), {"update_item": lambda *a, **k: None})()
    sns = type("SNS", (), {"publish": lambda *a, **k: None})()
    mock_boto.side_effect = [s3, br, ddb, sns]

    os.environ["SILVER_BUCKET"] = "silver"
    os.environ["GOLD_BUCKET"] = "gold"
    os.environ["CONSULTATION_METADATA_TABLE"] = "table"
    os.environ["PIPELINE_COMPLETION_TOPIC_ARN"] = "arn:aws:sns:xx:1:t"

    handler = _load_handler(
        ["consultation_pipeline", "lambda", "consultation_enrichment", "index.py"],
    )

    event = {
        "source": "consultation.pipeline",
        "detail": {
            "consultationId": "c1",
            "tenantId": "t1",
            "goldKey": "embeddings/t1/c1/conversation_embeddings.json",
        },
    }
    resp = handler(event, DummyContext())
    assert resp["statusCode"] == 200
