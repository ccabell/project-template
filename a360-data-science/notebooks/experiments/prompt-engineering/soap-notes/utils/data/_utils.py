import os


def iter_sorted_dir(
    dir_path: str, *, descending: bool = False
) -> list[os.DirEntry]:
    """Returns a list of directory entries sorted by name.

    Args:
        dir_path: Path to the directory to iterate over.
        descending: Whether to sort in descending order. Defaults to False.

    Returns:
        A list of `os.DirEntry` objects sorted by name.
    """
    with os.scandir(dir_path) as it:
        return sorted(it, key=lambda entry: entry.name, reverse=descending)