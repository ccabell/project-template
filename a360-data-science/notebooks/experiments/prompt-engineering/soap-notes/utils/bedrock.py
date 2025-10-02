import warnings
from collections import defaultdict
from collections.abc import Sequence
from enum import StrEnum
from typing import Any, Callable
from string import Formatter

import pandas as pd

from .aws import bedrock_client


class ReasoningModel(StrEnum):
    """Enumeration of supported reasoning model identifiers."""
    CLAUDE_3_7_SONNET = "anthropic.claude-3-7-sonnet-20250219-v1:0"
    DEEPSEEK_R1 = "deepseek.r1-v1:0"


class BedrockModel:
    """Wrapper for invoking LLMs on Bedrock.

    Supports reasoning models and exposes a helper function to create
    evaluation function compatible with MLflow's interface.

    Attributes:
        bedrock_rt_client: `boto3` client for the `bedrock-runtime` service
    """

    def __init__(
        self,
        model_id: str,
        bedrock_rt_client,
        name: str | None = None,
        inf_config: dict | None = None,
        additional_req_fields: dict | None = None,
    ):
        """Initialize the `BedrockModel`.

        Args:
            model_id: Identifier of the model or inference profile.
            bedrock_rt_client: `boto3` client for the `bedrock-runtime` service
            name: Optional custom name for the model.
            inf_config: Optional inference configuration to apply to requests
                (see Bedrock documentation for Converse API for details).
            additional_req_fields: Optional additional request fields.
                (see Bedrock documentation for Converse API for details).

        Raises:
            ValueError: If the model ID or inference profile cannot be found.
        """
        model_exceptions = (
            bedrock_client.exceptions.ValidationException,
            bedrock_client.exceptions.ResourceNotFoundException,
        )
        try:
            fm_response = bedrock_client.get_foundation_model(
                modelIdentifier=model_id
            )
        except model_exceptions:
            try:
                ip_response = bedrock_client.get_inference_profile(
                    inferenceProfileIdentifier=model_id
                )
            except model_exceptions as e:
                msg = f"Model or inference profile with ID '{model_id}' does not exist"
                raise ValueError(msg) from e
            else:
                fm_response = bedrock_client.get_foundation_model(
                    modelIdentifier=ip_response["models"][0]["modelArn"]
                )
        self._id = model_id
        self._info = fm_response["modelDetails"]
        if name is None:
            self._name = self._info["modelName"].lower().replace(" ", "-")
        else:
            self._name = name
        self.bedrock_rt_client = bedrock_rt_client
        self._inf_config = inf_config
        self._additional_req_fields = additional_req_fields
        self._is_reasoner = self._determine_if_reasoner()

    def _determine_if_reasoner(self) -> bool:
        model_id = self.info["modelId"]
        if model_id == ReasoningModel.DEEPSEEK_R1:
            return True
        if (
            model_id == ReasoningModel.CLAUDE_3_7_SONNET
            and self._additional_req_fields is not None
            and "thinking" in self._additional_req_fields
        ):
            return True
        return False

    @property
    def id(self) -> str:
        """Return the model ID as specified by the caller."""
        return self._id

    @property
    def info(self) -> dict[str, Any]:
        """Return the model details.

        See the `modelDetails` field of the GetFoundationModel API response
        for available keys
        """
        return self._info

    @property
    def name(self) -> str:
        """Return the model name suitable for display purposes."""
        return self._name

    @property
    def inf_config(self) -> dict | None:
        """Return the inference configuration, if any."""
        return self._inf_config

    @property
    def additional_req_fields(self) -> dict | None:
        """Return the additional request fields, if any."""
        return self._additional_req_fields

    @property
    def is_reasoner(self) -> bool:
        """Return whether the model supports reasoning."""
        return self._is_reasoner

    def __call__(self, messages: Sequence[str], **kwargs):
        """Invoke the model with a sequence of messages.

        Args:
            messages: A sequence of alternating user/assistant messages.
            **kwargs: Additional arguments to pass to the Converse API call.

        Returns:
            Response from the Converse API call.

        Raises:
            ValueError: If no messages are provided.
        """
        if len(messages) == 0:
            msg = "You need to provide at least one message"
            raise ValueError(msg)
        msgs = [construct_bedrock_msg(m, i) for i, m in enumerate(messages)]
        if self.inf_config is not None and "inferenceConfig" not in kwargs:
            kwargs["inferenceConfig"] = self.inf_config
        if (
            self.additional_req_fields is not None
            and "additionalModelRequestFields" not in kwargs
        ):
            kwargs["additionalModelRequestFields"] = self.additional_req_fields
        return self.bedrock_rt_client.converse(
            modelId=self.id, messages=msgs, **kwargs
        )

    def make_eval_fn(
        self,
        prompt: str,
        response_prefill: str | None = None,
        output_col_name: str = "output",
        out_reasoning_col_name: str = "reasoning_output",
        custom_cols: dict[str, Callable[[dict[str, Any]], Any]] | None = None,
        **kwargs,
    ) -> Callable[[pd.DataFrame], pd.DataFrame]:
        """Create an evaluation function compatible with the MLflow interface.

        Args:
            prompt: A prompt with optional placeholders enclosed in single
                curly braces.
            response_prefill: Optional assistant message prefill.
            output_col_name: Custom name of the column for the generated output.
            out_reasoning_col_name: Custom name of the column for the reasoning
                output.
            custom_cols: Optional dict mapping column names to functions applied
                on responses from the Converse API.
            **kwargs: Additional arguments to pass to the Converse API.

        Returns:
            A function that takes a pandas DataFrame with evaluation data and
            returns the DataFrame with the generated outputs alongside the
            token usage stats, request latency, and any custom columns.

        Raises:
            ValueError: If output/custom columns conflict with reserved names.
                Reserved names are: `["input_tokens", "output_tokens", "latency_ms"]`
        """
        reserved_cols = ["input_tokens", "output_tokens", "latency_ms"]
        reserved_col_exc_msg = "Output column name '{}' is reserved. Please use a different name"
        if output_col_name in reserved_cols:
            raise ValueError(reserved_col_exc_msg.format(output_col_name))
        reserved_cols.append(output_col_name)
        if out_reasoning_col_name in reserved_cols:
            raise ValueError(
                reserved_col_exc_msg.format(out_reasoning_col_name)
            )
        reserved_cols.append(out_reasoning_col_name)
        if (
            custom_cols is not None
            and (col_overrides := custom_cols.keys() & reserved_cols)
        ):
            msg = f"Custom column(s) '{col_overrides}' override the reserved names. Please use a different name"
            raise ValueError(msg)
        prompt_args = {
            arg for _, arg, *_ in Formatter().parse(prompt) if arg is not None
        }
        if len(prompt_args) == 0:
            msg = "No prompt arguments detected - the same prompt will be run for each input row"
            warnings.warn(msg, RuntimeWarning)

        def eval_fn(eval_df: pd.DataFrame) -> pd.DataFrame:
            if missing_args := prompt_args.difference(eval_df.columns):
                msg = f"Input DataFrame is missing the following columns required to format the prompt: '{missing_args}'"
                raise ValueError(msg)
            result = defaultdict(list)
            for row in eval_df.itertuples(index=False):
                messages = []
                if len(prompt_args) > 0:
                    format_args = {
                        arg: getattr(row, arg) for arg in prompt_args
                    }
                    messages.append(prompt.format(**format_args))
                else:
                    messages.append(prompt)
                if response_prefill is not None:
                    messages.append(response_prefill)
                response = self(messages, **kwargs)
                text_content_block = None
                reasoning_content_block = None
                for content_block in response["output"]["message"]["content"]:
                    if "text" in content_block:
                        text_content_block = content_block
                    elif "reasoningContent" in content_block:
                        reasoning_content_block = content_block
                if text_content_block is None:
                    msg = "Bedrock response does not include 'text' content block"
                    raise RuntimeError(msg)
                if response_prefill is not None:
                    text_content_block["text"] = (
                        response_prefill + text_content_block["text"]
                    )
                result[output_col_name].append(text_content_block["text"])
                if reasoning_content_block is not None:
                    result[out_reasoning_col_name].append(
                        reasoning_content_block["reasoningContent"]
                        .get("reasoningText", {})
                        .get("text")
                    )
                else:
                    result[out_reasoning_col_name].append(None)
                result["input_tokens"].append(response["usage"]["inputTokens"])
                result["output_tokens"].append(
                    response["usage"]["outputTokens"]
                )
                result["latency_ms"].append(response["metrics"]["latencyMs"])
                if custom_cols is not None:
                    for custom_col, col_func in custom_cols.items():
                        result[custom_col].append(col_func(response))
            return pd.DataFrame(data=result)
        return eval_fn


def construct_bedrock_msg(msg: str, idx: int) -> dict:
    """Construct a Bedrock Message object with a text ContentBlock.

    Args:
        msg: The message content.
        idx: Message index, used to alternate role between user and assistant.

    Returns:
        A dictionary representing the Bedrock Message object.
    """
    role = "user" if idx % 2 == 0 else "assistant"
    return {"role": role, "content": [{"text": msg}]}


def extract_text_content_block(converse_response: dict) -> dict:
    """Extract the text ContentBlock from a Bedrock Converse response.

    Args:
        converse_response: The full Converse response.

    Returns:
        A text ContentBlock.

    Raises:
        RuntimeError: If no text ContentBlock is found.
    """
    for content_block in converse_response["output"]["message"]["content"]:
        if "text" in content_block:
            return content_block
    msg = "Bedrock response does not include 'text' content block"
    raise RuntimeError(msg)