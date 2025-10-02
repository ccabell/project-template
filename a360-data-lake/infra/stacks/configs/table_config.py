"""Configuration module for Lake Formation table settings."""

from dataclasses import dataclass
from typing import Final

RAW_TABLES: Final[list[str]] = []  # To be populated as needed
STAGE_TABLES: Final[list[str]] = []  # To be populated as needed
ANALYTICS_TABLES: Final[list[str]] = []  # To be populated as needed


@dataclass(frozen=True)
class DatabaseTables:
    """Configuration model for tables within a Lake Formation database.

    Defines the tables available in each database zone for permission management
    and access control.

    Attributes:
        names: List of table names within the database.
    """

    names: list[str]


@dataclass(frozen=True)
class TableConfig:
    """Configuration model for Lake Formation tables across databases.

    Defines the complete table configuration across all database zones in the
    data lake, supporting granular access control and permissions management.

    Attributes:
        raw_tables: Tables in the raw database zone.
        stage_tables: Tables in the staging database zone.
        analytics_tables: Tables in the analytics database zone.
    """

    raw_tables: DatabaseTables
    stage_tables: DatabaseTables
    analytics_tables: DatabaseTables


def get_table_config() -> TableConfig:
    """Returns configured Lake Formation table settings.

    Creates a TableConfig instance with the standard table configurations
    for the data lake environment.

    Returns:
        Configured TableConfig instance initialized with standard table names.
    """
    return TableConfig(
        raw_tables=DatabaseTables(names=RAW_TABLES),
        stage_tables=DatabaseTables(names=STAGE_TABLES),
        analytics_tables=DatabaseTables(names=ANALYTICS_TABLES),
    )
