"""
Lifecycle configuration for shutting down idle SageMaker Studio applications.

Provides a construct for creating and managing a lifecycle configuration that
automatically shuts down idle Studio applications to reduce costs.
"""

from constructs import Construct

from .lifecycle_config_base import LifecycleConfigBase


class IdleShutdownLifecycleConfig(LifecycleConfigBase):
    """
    Lifecycle configuration for automatically shutting down idle Studio applications.

    This construct creates a lifecycle configuration that monitors activity in
    JupyterLab environments and automatically shuts them down after a specified
    period of inactivity. The configuration is attached to the specified
    SageMaker Studio domain.
    """

    def __init__(
        self, scope: Construct, construct_id: str, domain_id: str, **kwargs
    ) -> None:
        """
        Initialize the idle shutdown lifecycle configuration.

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
            config_name="idle-shutdown-config",
            lambda_file_path="idle_shutdown_lifecycle",
            **kwargs,
        )
