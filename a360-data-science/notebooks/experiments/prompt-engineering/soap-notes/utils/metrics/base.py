import re
from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence
from functools import partial
from typing import Literal

import numpy as np
from mlflow.models import EvaluationMetric

from ..bedrock import BedrockModel


AGG_NAME_TO_FUNC = {
    "min": np.min,
    "max": np.max,
    "mean": np.mean,
    "median": np.median,
    "variance": np.var,
    "p90": partial(np.percentile, q=90),
}
DEFAULT_AGGREGATIONS = tuple(AGG_NAME_TO_FUNC)
DEFAULT_JUDGE_INF_CONFIG = {"temperature": 0.0}


Aggregation = Literal["min", "max", "mean", "median", "variance", "p90"]


class BaseLLMAsAJudgeMetric(ABC):
    """Interface for defining LLM-as-a-judge evaluation metrics.

    This interface exposes accessors for the metric's configuration and an
    abstract method to convert a metric to MLflow-compatible format.
    """

    def __init__(
        self,
        name: str,
        prompt: str,
        aggregations: Sequence[Aggregation] | None = None,
        *,
        greater_is_better: bool = True,
    ):
        """Initialize `BaseLLMAsAJudgeMetric`

        Args:
            name: The name of the metric.
            prompt: The prompt to be used when evaluating with the LLM.
            aggregations: A sequence of aggregation methods to apply to scores.
                Supported values are:
                `["min", "max", "mean", "median", "variance", "p90"]`
            greater_is_better: Whether higher values are better for this metric.
        """
        self._name = name
        self._prompt = prompt
        if aggregations is None:
            self._aggregations = DEFAULT_AGGREGATIONS
        else:
            self._aggregations = aggregations
        self._greater_is_better = greater_is_better

    @property
    def name(self) -> str:
        """Return the name of the metric."""
        return self._name

    @property
    def prompt(self) -> str:
        """Return the prompt used for LLM-based evaluation."""
        return self._prompt

    @property
    def greater_is_better(self) -> bool:
        """Return whether higher scores are better for this metric."""
        return self._greater_is_better

    @property
    def aggregations(self) -> Sequence[Aggregation]:
        """Return the list of aggregation methods associated with the metric.
        """
        return self._aggregations

    @abstractmethod
    def make_mlflow_metric(
        self, judge_model: BedrockModel
    ) -> EvaluationMetric:
        """Create an MLflow-compatible metric with a specific judge model.

        Args:
            judge_model: An instance of `BedrockModel` to calculate the metric.

        Returns:
            An `EvaluationMetric` instance compatible with MLflow.
        """
        ...


# adapted from: https://github.com/anthropics/anthropic-cookbook/blob/4a7be656bd1a6e2149f9f1c40678dac379a857a7/misc/how_to_enable_json_mode.ipynb
def extract_between_tags(
    tag: str, source: str, *, strip: bool = True
) -> list[str]:
    """Extracts content enclosed between specified XML-like tags in a string.

    Args:
        tag: The tag name to search for.
        source: The input string containing tagged content.
        strip: Whether to strip leading/trailing whitespace from each result.

    Returns:
        A list of strings extracted from within the given tags.
    """
    ext_list = re.findall(f"<{tag}>(.+?)</{tag}>", source, re.DOTALL)
    if strip:
        ext_list = [e.strip() for e in ext_list]
    return ext_list


def aggregate_scores(
    scores: Iterable, aggregations: Iterable[Aggregation]
) -> dict | None:
    """Aggregates numerical scores using specified statistical functions.

    Args:
        scores: An iterable of numerical values.
        aggregations: A list of aggregation method names to apply.
            Supported values are:
            `["min", "max", "mean", "median", "variance", "p90"]`

    Returns:
        A dictionary mapping each aggregation name to its computed value.
        Returns `None` if no valid aggregations are provided.
    """
    res = {}
    for agg in aggregations:
        agg_func = AGG_NAME_TO_FUNC.get(agg)
        if agg_func is None:
            continue
        res[agg] = agg_func(scores)
    if len(res) == 0:
        return None
    return res