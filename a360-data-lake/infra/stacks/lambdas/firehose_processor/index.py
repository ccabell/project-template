"""firehose_processor/index.py
---------------------------

* Trigger :  Kinesis Data Firehose (record-transform)
* Task    :  Wrap raw PCM bytes in a JSON envelope, add consultation_id
             as a dynamic partition key, return ND-JSON to Firehose.

Instrumentation
~~~~~~~~~~~~~~~
• Logger  – structured logs with cold-start keys
• Tracer  – X-Ray subsegments
• Metrics – RecordsProcessed / RecordsFailed
"""

from __future__ import annotations

import base64
import json
from typing import Any

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

tracer = Tracer(service="firehose_transformer")
logger = Logger(service="firehose_transformer")
metrics = Metrics(namespace="TranscriptionService", service="firehose_transformer")


@logger.inject_lambda_context(log_event=False)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: dict[str, Any], _: LambdaContext) -> dict[str, Any]:
    """Iterate Firehose records, wrap each payload in JSON, and emit the result
    in the format Firehose expects (`recordId`, `result`, `data`, `metadata`).
    """
    out = {"records": []}

    for rec in event["records"]:
        try:
            data_str = base64.b64decode(rec["data"]).decode()
            payload = json.loads(data_str)

            envelope = {
                "consultation_id": payload["consultation_id"],
                "audio_raw": payload["audio_raw"],
                "timestamp": payload["timestamp"],
                "meta": payload.get("meta", {}),
            }

            out["records"].append(
                {
                    "recordId": rec["recordId"],
                    "result": "Ok",
                    "data": base64.b64encode(json.dumps(envelope).encode()).decode(),
                    "metadata": {
                        "partitionKeys": {
                            "consultation_id": envelope["consultation_id"],
                        },
                    },
                },
            )

            metrics.add_metric(name="RecordsProcessed", unit="Count", value=1)

        except Exception as exc:
            logger.exception("Record transformation failed", extra={"error": str(exc)})
            metrics.add_metric(name="RecordsFailed", unit="Count", value=1)

            out["records"].append(
                {
                    "recordId": rec["recordId"],
                    "result": "ProcessingFailed",
                    "data": rec["data"],
                    "metadata": {
                        "error": str(exc),
                        "partitionKeys": {"consultation_id": "unknown"},
                    },
                },
            )

    return out
