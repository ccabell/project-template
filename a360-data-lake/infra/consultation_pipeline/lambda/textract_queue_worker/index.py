"""SQS worker for textract-output parallel processing.

Receives messages for newly created textract-output objects in silver. This
can be extended to perform downstream transformations or validations.
"""

import json
import os
from typing import Any

# Optional PowerTools import for testing compatibility
try:
    from aws_lambda_powertools import Logger, Tracer

    tracer = Tracer(service="consultation-textract-worker")
    logger = Logger(service="consultation-textract-worker")
except ImportError:
    # Mock objects for testing environments
    class MockLogger:
        def info(self, msg, **kwargs):
            pass

        def error(self, msg, **kwargs):
            pass

        def warning(self, msg, **kwargs):
            pass

        def exception(self, msg, **kwargs):
            pass

        def inject_lambda_context(
            self,
            func=None,
            *,
            log_event=False,
            correlation_id_path=None,
            clear_state=False,
        ):
            if func is None:

                def decorator(f):
                    def wrapper(*args, **kwargs):
                        return f(*args, **kwargs)

                    return wrapper

                return decorator

            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            return wrapper

    class MockTracer:
        def capture_lambda_handler(self, func=None, *args, **kwargs):
            if func is None:

                def decorator(f):
                    def wrapper(*a, **kw):
                        return f(*a, **kw)

                    return wrapper

                return decorator

            def wrapper(*a, **kw):
                return func(*a, **kw)

            return wrapper

    tracer = MockTracer()
    logger = MockLogger()

try:
    SILVER_BUCKET = os.environ["SILVER_BUCKET"]
except KeyError as e:
    raise RuntimeError("Missing required env var: SILVER_BUCKET") from e


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=False)
def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    processed = 0
    failures: list[dict[str, str]] = []
    for record in event.get("Records", []):
        try:
            body_raw = record.get("body", "{}")
            body = json.loads(body_raw) if isinstance(body_raw, str) else body_raw
            # SQS → (optional SNS) → S3 event
            msg = body.get("Message")
            s3_event = json.loads(msg) if isinstance(msg, str) else (msg or body)
            for r in s3_event.get("Records", []):
                key = r.get("s3", {}).get("object", {}).get("key")
                if key and key.startswith("textract-output/"):
                    processed += 1
        except (json.JSONDecodeError, TypeError, KeyError):
            logger.exception("Failed to process SQS record")
            mid = record.get("messageId")
            if mid:
                failures.append({"itemIdentifier": mid})
    if failures:
        return {"batchItemFailures": failures}
    return {}
