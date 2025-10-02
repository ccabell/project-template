"""Utility functions for podcast pipeline.
This module provides helper functions for RSS feed parsing, S3 key generation,
and data sanitization.
"""

import re
from typing import Any, Optional, Dict
import unicodedata


def sanitize_episode_id(episode_id: str) -> str:
    """Sanitize episode ID for use as partition key.
    Args:
        episode_id: Raw episode ID from RSS feed.
    Returns:
        Sanitized episode ID safe for S3 keys.
    """
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", episode_id)
    sanitized = re.sub(r"_+", "_", sanitized)
    sanitized = sanitized.strip("_")

    if len(sanitized) > 128:
        sanitized = sanitized[:128]

    # Ensure we don't return an empty string
    if not sanitized:
        sanitized = "unknown_episode"

    return sanitized


def sanitize_s3_metadata(metadata: Dict[str, str]) -> Dict[str, str]:
    """
    Sanitize S3 metadata to contain only ASCII characters in keys and values.

    Non-ASCII characters will be normalized to their closest ASCII equivalents.
    Entries with invalid types (non-str) are skipped.

    Args:
        metadata (Dict[str, str]): Original metadata.

    Returns:
        Dict[str, str]: Sanitized metadata ready for S3.
    """
    sanitized = {}

    for key, value in metadata.items():
        if not isinstance(key, str) or not isinstance(value, str):
            continue  # skip non-string entries

        key_ascii = _to_ascii(key)
        value_ascii = _to_ascii(value)

        sanitized[key_ascii] = value_ascii

    return sanitized


def _to_ascii(text: str) -> str:
    """
    Normalize and encode text to ASCII, removing non-ASCII characters.
    E.g., “We’re” → "We're"

    Args:
        text (str): Input string.

    Returns:
        str: ASCII-only string.
    """
    normalized = unicodedata.normalize("NFKD", text)
    return normalized.encode("ascii", "ignore").decode("ascii")


def get_audio_url_from_entry(entry: Any) -> Optional[str]:
    """Extract audio URL from RSS feed entry.
    Args:
        entry: Feed entry from feedparser.
    Returns:
        Audio URL if found, None otherwise.
    """
    if hasattr(entry, "enclosures") and entry.enclosures:
        for enclosure in entry.enclosures:
            if enclosure.get("type", "").startswith("audio/"):
                return enclosure.get("href")

    if hasattr(entry, "links"):
        for link in entry.links:
            if link.get("type", "").startswith("audio/"):
                return link.get("href")

    return None


def get_s3_key(zone: str, domain: str, feed: str, episode: str, filename: str) -> str:
    """Generate S3 key for podcast data.
    Args:
        zone: Data zone (bronze, silver, gold).
        domain: Domain name (podcasts).
        feed: Feed name.
        episode: Episode identifier.
        filename: File name.
    Returns:
        S3 key string.
    """
    return f"{zone}/{domain}/{feed}/{episode}/{filename}"


def make_bias_analysis_prompt(transcript_text: str, summary_data: dict) -> str:
    return f"""
<!-- SYSTEM -->
<system>
You are Claude Sonnet v4, an impartial medical-communications analyst. Your goal is to surface any conflicts of interest between podcast content and its sponsors, grounded in evidence from the transcript.
</system>

<!-- CONTEXT -->
<context>
Domain: Medical Aesthetics
Objective: Detect segments where recommendations may align with a sponsor's commercial interests.
Scale: Return one integer "alignment_score" (0=neutral, 100=fully sponsor-aligned).
</context>

<!-- INPUT -->
<input>
<transcript><![CDATA[
{transcript_text}
]]></transcript>

<!-- Structured summary from upstream step -->
<summary>
<main_topics>{summary_data.get("main_topics_discussed", "")}</main_topics>
<key_insights>{summary_data.get("key_medical_insights", "")}</key_insights>
<expert_opinions>{summary_data.get("expert_opinions", "")}</expert_opinions>
<takeaways>{summary_data.get("practical_takeaways", "")}</takeaways>
<warnings>{summary_data.get("warnings_disclaimers", "")}</warnings>
</summary>
</input>

<!-- TASK -->
<instructions>
1. Scan the transcript for any mention of sponsors, advertisers, brand names, or paid partnerships.
2. Extract the minimal text span (sentence or short paragraph) showing a potential conflict between sponsor interests and podcast recommendations or opinions.
3. For each extracted span, add a concise (≤ 40-word) explanation of why it may represent a conflict.
4. After reviewing all spans, assign a single "alignment_score" using the rubric below.
</instructions>

<rubric>
0-20 Purely neutral; no discernible alignment.
21-40 Mild references; informational only.
41-60 Mixed alignment; some promotional undertones.
61-80 Strong alignment; recommendations favor a sponsor.
81-100 Direct promotion; recommendations function as ads.
</rubric>

<!-- OUTPUT FORMAT -->
<output_format>
{{
  "conflict_segments": [
    {{
      "sponsor": "<string>",
      "excerpt": "<string>",
      "explanation": "<string>",
      "timestamp": "<HH:MM:SS-HH:MM:SS | ISO-8601 | omit if unavailable>",
      "confidence": "<float 0-1>"
    }}
    /* repeat for each segment */
  ],
  "alignment_score": <integer 0-100>
}}
</output_format>

<!-- NOTES -->
<notes>
• If no conflicts are found, return an empty "conflict_segments" array and an alignment_score ≤ 20.
• Output **only** the JSON—no extra commentary.
• Respect medical-aesthetics domain nuance; err on the side of neutrality when evidence is weak.
</notes>
"""
