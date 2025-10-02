from aws_cdk import Stack
from aws_cdk import aws_glue as glue
from constructs import Construct


class QuickSightCommonStack(Stack):
    """Stack with common resources that all QuickSight stacks can utilize"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        """Initializes the stack

        Args:
            scope: CDK construct providing the scope for resource creation
            construct_id: Unique identifier for the stack
            **kwargs: Additional arguments passed to parent Stack constructor
        """
        super().__init__(scope, construct_id, **kwargs)

        self.analytics_database = glue.CfnDatabase(
            self,
            "AnalyticsDatabase",
            catalog_id=self.account,
            database_input=glue.CfnDatabase.DatabaseInputProperty(
                description="Central database for A360 analytics", name="a360_analytics"
            ),
        )
