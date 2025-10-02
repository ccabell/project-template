"""
Lifecycle configuration for installing packages in SageMaker Studio environments.

Provides a construct for creating and managing a lifecycle configuration that
automatically installs specified Python packages in Studio JupyterLab environments.
"""

from constructs import Construct

from .lifecycle_config_base import LifecycleConfigBase


class PackageInstallerLifecycleConfig(LifecycleConfigBase):
    """
    Lifecycle configuration for installing Python packages in Studio environments.

    This construct creates a lifecycle configuration that automatically installs
    specified Python packages when a JupyterLab environment is launched. The
    configuration is attached to the specified SageMaker Studio domain.
    """

    def __init__(
        self, scope: Construct, construct_id: str, domain_id: str, **kwargs
    ) -> None:
        """
        Initialize the package installer lifecycle configuration.

        Args:
            scope: CDK construct scope
            construct_id: Unique identifier for this construct
            domain_id: SageMaker Studio domain ID
            **kwargs: Additional arguments to pass to the parent construct
        """
        super().__init__(
            scope,
            construct_id,
            domain_id=domain_id,
            config_name="package-installer-config",
            lambda_file_path="package_installer_lifecycle",
            **kwargs,
        )
