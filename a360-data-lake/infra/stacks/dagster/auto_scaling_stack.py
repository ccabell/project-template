"""
Auto-scaling and high availability infrastructure for Dagster+ ECS agents.

This stack provisions scalable ECS services for Dagster agents, including:
- Application Auto Scaling for an existing Fargate Service
- CPU and Memory scaling policies (step scaling)
"""

from aws_cdk import (
    Stack,
    Duration,
    aws_ecs as ecs,
    aws_applicationautoscaling as appscaling,
)
from constructs import Construct
from .outputs import OutputManager


class AutoScalingStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        cluster: ecs.Cluster,
        agent_service: ecs.FargateService,
        min_capacity=1,
        max_capacity=2,
        cpu_target=80,
        memory_target=80,
        **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)
        self.output_manager = OutputManager(self, self.stack_name)

        # ECS Service for Dagster agent
        self.agent_service = agent_service

        self.cluster = cluster
        # Auto Scaling Target
        scaling_target = appscaling.ScalableTarget(
            self,
            "DagsterAgentScalingTarget",
            service_namespace=appscaling.ServiceNamespace.ECS,
            resource_id=f"service/{self.cluster.cluster_name}/{self.agent_service.service_name}",
            scalable_dimension="ecs:service:DesiredCount",
            min_capacity=min_capacity,
            max_capacity=max_capacity,
        )

        # CPU Utilization Scaling Policy
        scaling_target.scale_on_metric(
            "CpuScaling",
            metric=self.agent_service.metric_cpu_utilization(),
            scaling_steps=[
                appscaling.ScalingInterval(lower=0, upper=cpu_target - 10, change=-1),
                appscaling.ScalingInterval(lower=cpu_target + 10, change=+1),
            ],
            adjustment_type=appscaling.AdjustmentType.CHANGE_IN_CAPACITY,
            cooldown=Duration.seconds(60),
        )

        # Memory Utilization Scaling Policy
        scaling_target.scale_on_metric(
            "MemoryScaling",
            metric=self.agent_service.metric_memory_utilization(),
            scaling_steps=[
                appscaling.ScalingInterval(
                    lower=0,
                    upper=memory_target - 10,
                    change=-1,
                ),
                appscaling.ScalingInterval(lower=memory_target + 10, change=+1),
            ],
            adjustment_type=appscaling.AdjustmentType.CHANGE_IN_CAPACITY,
            cooldown=Duration.seconds(60),
        )

        # Output Scaling Target ARN
        self.output_manager.add_output_with_ssm(
            "DagsterAgentScalingTargetID",
            scaling_target.scalable_target_id,
            "ID of Dagster ECS agent scaling target",
            f"{self.stack_name}-DagsterAgentScalingTargetID",
        )
