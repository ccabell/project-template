"""Configuration module for Lake Formation database settings."""

from dataclasses import dataclass
from typing import Final

DATABASE_RAW: Final[str] = "raw"
DATABASE_STAGE: Final[str] = "stage"
DATABASE_ANALYTICS: Final[str] = "analytics"


@dataclass(frozen=True)
class DatabaseConfig:
    """Configuration model for Lake Formation databases.

    Defines the configuration for data lake databases, including naming conventions
    and access patterns for different data zones.

    Attributes:
        raw_db_name: Name of the raw data zone database.
        stage_db_name: Name of the staging zone database.
        analytics_db_name: Name of the analytics zone database.
    """

    raw_db_name: str
    stage_db_name: str
    analytics_db_name: str


def get_database_config() -> DatabaseConfig:
    """Returns configured Lake Formation database settings.

    Creates a DatabaseConfig instance with the standard naming conventions
    for the data lake environment.

    Returns:
        Configured DatabaseConfig instance initialized with standard database names.
    """
    return DatabaseConfig(
        raw_db_name=DATABASE_RAW,
        stage_db_name=DATABASE_STAGE,
        analytics_db_name=DATABASE_ANALYTICS,
    )
