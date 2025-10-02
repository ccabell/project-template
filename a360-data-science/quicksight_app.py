"""Main CDK application for QuickSight infrastructure deployment

This module orchestrates the deployment of multiple stacks for setting up and building
QuickSight dashboards
"""

import os

from aws_cdk import App, Environment

from infrastructure.quicksight.quicksight_common_stack import QuickSightCommonStack
from infrastructure.quicksight.transcription_analysis_stack import (
    TranscriptionAnalysisStack,
)


def create_cdk_app(env_name: str) -> App:
    """Creates CDK app with all required stacks

    Args:
        env_name: Deployment environment name

    Returns:
        Configured CDK App instance with all stacks and dependencies
    """
    app = App()
    env = Environment(
        account=os.environ["CDK_DEFAULT_ACCOUNT"],
        region=os.environ["CDK_DEFAULT_REGION"],
    )
    prefix = f"a360-{env_name}-".lower()

    common_stack = QuickSightCommonStack(app, "QuickSightCommonStack", env=env)

    transcript_analysis_stack = TranscriptionAnalysisStack(
        app,
        "TranscriptionAnalysisStack",
        analytics_db=common_stack.analytics_database,
        env_prefix=prefix,
        env=env,
    )
    return app


def main():
    """Application entrypoint for stack deployment"""
    env_name = os.getenv("ENVIRONMENT", "development")
    app = create_cdk_app(env_name)
    app.synth()


if __name__ == "__main__":
    main()
