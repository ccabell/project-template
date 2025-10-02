from collections.abc import Sequence
from typing import Callable

import mlflow
import pandas as pd
from mlflow.models import EvaluationMetric, EvaluationResult

from .metrics.base import BaseLLMAsAJudgeMetric
from .bedrock import BedrockModel
from ._mlflow import log_model_params


def _evaluate_model(
    judge_model: BedrockModel,
    eval_data: pd.DataFrame,
    judge_metrics: Sequence[BaseLLMAsAJudgeMetric],
    pred_col_name: str,
    model_eval_fn: Callable[[pd.DataFrame], pd.DataFrame] | None = None,
    other_metrics: Sequence[EvaluationMetric] | None = None,
) -> EvaluationResult:
    """Evaluate a model using LLM-as-a-Judge approach.

    Args:
        judge_model: The `BedrockModel` to use as the judge.
        eval_data: DataFrame containing evaluation data. If the `model_eval_fn`
            is omitted, this should alsp include model predictions in the
            `pred_col_name` column.
        judge_metrics: A sequence of custom LLM-as-a-judge metrics to evaluate
            with.
        pred_col_name: Name of the column in `eval_data` containing predictions.
        model_eval_fn: Optional function to generate predictions.
        other_metrics: Optional list of additional MLflow-compatible metrics.

    Returns:
        An EvaluationResult object containing the evaluation metrics and tables.
    """
    if other_metrics is None:
        extra_metrics = []
    else:
        extra_metrics = [*other_metrics]
    extra_metrics.extend(
        metric.make_mlflow_metric(judge_model) for metric in judge_metrics
    )
    eval_result = mlflow.evaluate(
        model_eval_fn,
        eval_data,
        predictions=pred_col_name,
        extra_metrics=extra_metrics,
    )
    log_model_params(judge_model, "judge_")
    metric_prompts = {metric.name: metric.prompt for metric in judge_metrics}
    mlflow.log_dict(metric_prompts, "metric_prompts.json")
    return eval_result


def _evaluate_model_in_nested_run(
    *args, run_name: str | None = None, **kwargs
) -> EvaluationResult:
    """Helper function to run `_evaluate_model` inside a nested MLflow run.

    Args:
        *args: Positional arguments forwarded to `_evaluate_model`.
        run_name: Optional name for the nested MLflow run.
        **kwargs: Keyword arguments forwarded to `_evaluate_model`.

    Returns:
        An EvaluationResult object containing the evaluation metrics and tables.
    """
    with mlflow.start_run(run_name=run_name, nested=True):
        return _evaluate_model(*args, **kwargs)


def compare_judge_models(
    judge_models: Sequence[BedrockModel],
    model_eval_fn: Callable[[pd.DataFrame], pd.DataFrame],
    eval_data: pd.DataFrame,
    judge_metrics: Sequence[BaseLLMAsAJudgeMetric],
    pred_col_name: str,
    other_metrics: Sequence[EvaluationMetric] | None = None,
    parent_run_name: str | None = None,
) -> dict[str, EvaluationResult]:
    """Compares multiple judge models using the same evaluation data and metrics.

    Args:
        judge_models: List of judge `BedrockModel`'s to compare.
        model_eval_fn: Function that generates predictions for the input data.
        eval_data: DataFrame containing input data.
        judge_metrics: A sequence of custom LLM-as-a-judge metrics to evaluate
        pred_col_name: Name of the column in `eval_data` where to store
            predictions.
        other_metrics: Optional list of additional MLflow-compatible metrics.
        parent_run_name: Optional MLflow run name to use for the parent run.

    Returns:
        A dictionary mapping child run names to its `EvaluationResult`'s.

    Raises:
        ValueError: If `judge_models` or `judge_metrics` are empty.
    """
    if len(judge_models) == 0:
        msg = "At least one judge model must be specified"
        raise ValueError(msg)
    if len(judge_metrics) == 0:
        msg = "At least one LLM-as-a-judge metric must be specified"
        raise ValueError(msg)
    first_judge, *other_judges = judge_models
    eval_results = {}
    with mlflow.start_run(run_name=parent_run_name):
        first_run_name = first_judge.name
        first_eval_result = _evaluate_model_in_nested_run(
            first_judge,
            eval_data,
            judge_metrics,
            pred_col_name,
            model_eval_fn,
            other_metrics,
            run_name=first_run_name,
        )
        eval_results[first_run_name] = first_eval_result
        if len(other_judges) > 0:
            # assume inputs are located in the first column of the `eval_data`
            inputs_col_name = eval_data.columns[0]
            first_result_table = first_eval_result.tables["eval_results_table"]
            data_with_preds = pd.DataFrame(
                data={
                    inputs_col_name: eval_data[inputs_col_name],
                    "outputs": first_result_table["outputs"],
                }
            )
            for judge in other_judges:
                run_name = judge.name
                eval_results[run_name] = _evaluate_model_in_nested_run(
                    judge,
                    data_with_preds,
                    judge_metrics,
                    "outputs",
                    run_name=run_name,
                    other_metrics=other_metrics,
                )
    return eval_results


def evaluate_prompt(
    prompt: str,
    models: Sequence[BedrockModel],
    eval_data: pd.DataFrame,
    judge_model: BedrockModel,
    judge_metrics: Sequence[BaseLLMAsAJudgeMetric],
    pred_col_name: str,
    other_metrics: Sequence[EvaluationMetric] | None = None,
    run_name_prefix: str = "",
    **eval_fn_kwargs,
) -> dict[str, EvaluationResult]:
    """Evaluates a prompt across multiple models using a shared judge model.

    Args:
        prompt: The prompt template to use when generating model outputs.
        models: List of models to evaluate.
        eval_data: DataFrame containing input data.
        judge_model: Judge model used to evaluate outputs.
        judge_metrics: A sequence of custom LLM-as-a-judge metrics to evaluate
        pred_col_name: Name of the column in `eval_data` where to store
            predictions.
        other_metrics: Optional list of additional MLflow-compatible metrics.
        run_name_prefix: Prefix to prepend to each MLflow run name.
        **eval_fn_kwargs: Additional keyword arguments to pass to each model's
            `make_eval_fn()` call.

    Returns:
        A dictionary mapping run names to `EvaluationResult` objects.

    Raises:
        ValueError: If `models` or `judge_metrics` are empty.
    """
    if len(models) == 0:
        msg = "At least one model must be specified"
        raise ValueError(msg)
    if len(judge_metrics) == 0:
        msg = "At least one LLM-as-a-judge metric must be specified"
        raise ValueError(msg)
    prompts = {
        "prompt_template": prompt,
        "response_prefill": eval_fn_kwargs.get("response_prefill", None),
    }
    eval_results = {}
    for model in models:
        eval_fn = model.make_eval_fn(prompt, **eval_fn_kwargs)
        run_name = run_name_prefix + model.name
        with mlflow.start_run(run_name=run_name):
            eval_result = _evaluate_model(
                judge_model,
                eval_data,
                judge_metrics,
                pred_col_name,
                eval_fn,
                other_metrics
            )
            log_model_params(model)
            mlflow.log_dict(prompts, "prompts.json")
            eval_results[run_name] = eval_result
    return eval_results