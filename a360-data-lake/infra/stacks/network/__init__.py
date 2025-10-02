"""Network infrastructure module for A360 Data Platform.

This module provides VPC, subnet, and networking components required for
the modern data platform architecture including Dagster+ hybrid agents
and LakeFS data versioning services.
"""

from .network_stack import NetworkStack

__all__ = ["NetworkStack"]
