"""Dagster+ ECS infrastructure module for A360 Data Platform.

This module provides ECS cluster and service infrastructure for running
Dagster+ hybrid agents that process healthcare data from the existing
MDA data lake infrastructure.
"""

from .agent_config import AgentConfiguration
from .ecs_stack import EcsStack
from .monitoring_stack import MonitoringStack
from .auto_scaling_stack import AutoScalingStack
from .security_stack import SecurityStack
from .service_discovery import ServiceDiscoveryStack

__all__ = [
    "AgentConfiguration",
    "EcsStack",
    "MonitoringStack",
    "AutoScalingStack",
    "AgentConfiguration",
    "SecurityStack",
    "ServiceDiscoveryStack",
]
