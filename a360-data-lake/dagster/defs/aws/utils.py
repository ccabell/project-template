import json
import re
from typing import Any


def parse_bedrock_json_response(response: str) -> Any:
    """Extract and parse JSON from Claude's Markdown-style response."""
    # Try to extract a fenced code block with JSON
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
    json_str = match.group(1) if match else response

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON: {e}\nRaw content:\n{json_str}") from e
