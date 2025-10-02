from collections.abc import Sequence

import pandas as pd
from mlflow.metrics import MetricValue, make_metric
from mlflow.models import EvaluationMetric

from .base import DEFAULT_AGGREGATIONS, Aggregation, aggregate_scores


def input_tokens_count(
    aggregations: Sequence[Aggregation] | None = None
) -> EvaluationMetric:
    """Returns a metric for counting input tokens.

    Args:
        aggregations: A sequence of aggregation methods to apply to the per-row
            scores. If not provided, defaults to `DEFAULT_AGGREGATIONS`.

    Returns:
        An `EvaluationMetric` object that computes input tokens count.
    """
    if aggregations is None:
        aggregations = DEFAULT_AGGREGATIONS

    def eval_fn(predictions: pd.Series, input_tokens: pd.Series) -> MetricValue:
        return MetricValue(
            input_tokens.to_list(),
            aggregate_results=aggregate_scores(input_tokens, aggregations),
        )
    return make_metric(
        eval_fn=eval_fn, greater_is_better=False, name="input_tokens_count"
    )


def output_tokens_count(
    aggregations: Sequence[Aggregation] | None = None
) -> EvaluationMetric:
    """Returns a metric for counting output tokens.

    Args:
        aggregations: A sequence of aggregation methods to apply to the per-row
            scores. If not provided, defaults to `DEFAULT_AGGREGATIONS`.

    Returns:
        An `EvaluationMetric` object that computes output tokens count.
    """
    if aggregations is None:
        aggregations = DEFAULT_AGGREGATIONS

    def eval_fn(predictions: pd.Series, output_tokens: pd.Series) -> MetricValue:
        return MetricValue(
            output_tokens.to_list(),
            aggregate_results=aggregate_scores(output_tokens, aggregations),
        )
    return make_metric(
        eval_fn=eval_fn, greater_is_better=False, name="output_tokens_count"
    )


def latency(
    aggregations: Sequence[Aggregation] | None = None
) -> EvaluationMetric:
    """Returns a metric for measuring response latency in milliseconds.

    Args:
        aggregations: A sequence of aggregation methods to apply to the per-row
            scores. If not provided, defaults to `DEFAULT_AGGREGATIONS`.

    Returns:
        An `EvaluationMetric` object that computes latency.
    """
    if aggregations is None:
        aggregations = DEFAULT_AGGREGATIONS

    def eval_fn(predictions: pd.Series, latency_ms: pd.Series) -> MetricValue:
        return MetricValue(
            latency_ms.to_list(),
            aggregate_results=aggregate_scores(latency_ms, aggregations),
        )
    return make_metric(
        eval_fn=eval_fn, greater_is_better=False, name="latencyMs"
    )