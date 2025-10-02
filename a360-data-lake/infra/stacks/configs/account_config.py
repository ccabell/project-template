from typing import Final

from aws_cdk import Aws
from pydantic import BaseModel, Field


class AccountConfig(BaseModel):
    """Configuration model for AWS account settings.

    Defines the structure and validation for AWS account configurations used
    in cross-account data sharing setups.

    Attributes:
        account_id: AWS account ID, resolved dynamically during deployment.
        region: AWS region identifier, resolved dynamically during deployment.
        enabled: Flag indicating if this account configuration is active.
    """

    model_config = {"arbitrary_types_allowed": True}

    account_id: str
    region: str
    enabled: bool = Field(default=True)


class LakeFormationConfig(BaseModel):
    """Configuration model for Lake Formation settings.

    Defines the complete configuration for Lake Formation cross-account
    sharing, including producer and consumer account details.

    Attributes:
        producer_account: Configuration for the producer AWS account.
        consumer_accounts: List of consumer AWS account configurations.
    """

    producer_account: AccountConfig
    consumer_accounts: list[AccountConfig]


CONSUMER_ACCOUNT_IDS: Final[list[str]] = ["590183989543"]


def get_lakeformation_config() -> LakeFormationConfig:
    """Returns configured Lake Formation account settings.

    Creates a LakeFormationConfig instance using dynamically resolved
    account settings from CDK context.

    Returns:
        Configured LakeFormationConfig instance with producer and consumer
        account configurations.
    """
    return LakeFormationConfig(
        producer_account=AccountConfig(account_id=Aws.ACCOUNT_ID, region=Aws.REGION),
        consumer_accounts=[
            AccountConfig(account_id=acc_id, region=Aws.REGION)
            for acc_id in CONSUMER_ACCOUNT_IDS
        ],
    )
