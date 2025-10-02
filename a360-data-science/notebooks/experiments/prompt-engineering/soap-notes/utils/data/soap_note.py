import os
import json
from collections import defaultdict
from typing import Callable

import pandas as pd

from ._utils import iter_sorted_dir


def process_transcript_plain(transcript_path: str) -> str:
    """Pre-processes the JSON transcript simply concatenating all the text.

    Args:
        transcript_path: Path to the transcript JSON file.

    Returns:
        A string containing the concatenated transcript.
    """
    with open(transcript_path) as f:
        data = json.load(f)
    return " ".join(
        [alt["transcript"] for alt in data["channel"]["alternatives"]]
    )


def process_transcripts(
    data_path: str, processing_fn: Callable[[str], str]
) -> pd.DataFrame:
    """Pre-processes all transcripts in a directory and returns them as a DataFrame.

    The expected directory structure under the `data_path` must contain
    subfolders with with `transcript.json` files inside of them.

    Args:
        data_path: Path to the directory containing transcript subfolders.
        processing_fn: A function that takes a path to a transcript file and
            returns a processed string.

    Returns:
        A pandas DataFrame with a single column "transcript" containing the
            processed transcripts.
    """
    result = defaultdict(list)
    for entry in iter_sorted_dir(data_path):
        if not entry.is_dir():
            continue
        transcript_path = os.path.join(entry.path, "transcript.json")
        if not os.path.isfile(transcript_path):
            continue
        result["transcript"].append(processing_fn(transcript_path))
    return pd.DataFrame(data=result)