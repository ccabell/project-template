"""
SageMaker Studio lifecycle configuration implementations.

This module provides concrete implementations of lifecycle configurations for
SageMaker Studio domains, allowing for customization of user environments.
"""

from constructs import Construct

from .custom_resources.lifecycle_config_base import LifecycleConfigBase


class PackageInstallerConfig(LifecycleConfigBase):
    """
    Lifecycle configuration for installing packages in Studio environments.

    This configuration installs essential Python packages in JupyterLab
    environments when they start, ensuring consistency across all users.
    """

    def __init__(self, scope: Construct, construct_id: str, domain_id: str) -> None:
        """
        Initialize the package installer lifecycle configuration.

        Args:
            scope: CDK construct scope
            construct_id: Unique identifier for this construct
            domain_id: SageMaker Studio domain ID
        """
        super().__init__(
            scope,
            construct_id,
            domain_id=domain_id,
            config_name="package-installer",
            lambda_file_path="package_installer_lifecycle",
        )


class IdleAppShutdownConfig(LifecycleConfigBase):
    """
    Lifecycle configuration for automatically shutting down idle Studio apps.

    This configuration implements an idle detection mechanism that shuts down
    Studio applications after a period of inactivity, reducing costs.
    """

    def __init__(self, scope: Construct, construct_id: str, domain_id: str) -> None:
        """
        Initialize the idle app shutdown lifecycle configuration.

        Args:
            scope: CDK construct scope
            construct_id: Unique identifier for this construct
            domain_id: SageMaker Studio domain ID
        """
        super().__init__(
            scope,
            construct_id,
            domain_id=domain_id,
            config_name="idle-app-shutdown",
            lambda_file_path="idle_shutdown_lifecycle",
        )
