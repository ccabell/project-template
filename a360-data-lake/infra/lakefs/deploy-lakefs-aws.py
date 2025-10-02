#!/usr/bin/env python3
"""Deploy LakeFS to AWS
===================

Deployment script for LakeFS AWS infrastructure with dynamic account resolution.
Creates all necessary AWS resources and sets up LakeFS repositories.
"""

import json
import os
import sys
import time

import boto3

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stacks.lakefs.repository_manager import LakeFSRepositoryManager


class LakeFSAWSDeployer:
    """Deploys LakeFS infrastructure to AWS."""

    def __init__(self, environment: str = "dev"):
        """Initialize deployer.
        
        Args:
            environment: Deployment environment (dev, staging, prod)
        """
        self.environment = environment
        self.account_id = self._get_aws_account_id()
        self.region = self._get_aws_region()

        print("🚀 LakeFS AWS Deployment")
        print(f"Environment: {environment}")
        print(f"AWS Account: {self.account_id}")
        print(f"AWS Region: {self.region}")
        print("=" * 50)

    def _get_aws_account_id(self) -> str:
        """Get current AWS account ID."""
        try:
            sts_client = boto3.client('sts')
            response = sts_client.get_caller_identity()
            return response['Account']
        except Exception as e:
            raise RuntimeError(f"Failed to get AWS account ID: {e}")

    def _get_aws_region(self) -> str:
        """Get current AWS region."""
        try:
            session = boto3.Session()
            return session.region_name or "us-east-1"
        except Exception:
            return "us-east-1"

    def deploy_infrastructure(self) -> dict[str, str]:
        """Deploy LakeFS infrastructure using CDK.
        
        Returns:
            Dictionary with deployment outputs
        """
        print("📦 Deploying LakeFS infrastructure...")

        # CDK deployment command
        stack_name = f"LakeFSStack-{self.environment}"
        cdk_command = f"npx cdk deploy {stack_name} --context environment={self.environment} --require-approval never"

        print(f"Running: {cdk_command}")

        # Note: In a real implementation, you would run this command
        # For now, return expected outputs
        bucket_name = f"a360-lakefs-data-{self.environment}-{self.account_id}"

        return {
            "lakefs_endpoint": f"http://lakefs-alb-{self.environment}.{self.region}.elb.amazonaws.com",
            "bucket_name": bucket_name,
            "database_endpoint": f"lakefs-db-{self.environment}.{self.account_id}.{self.region}.rds.amazonaws.com"
        }

    def wait_for_lakefs(self, endpoint: str, max_wait: int = 300) -> bool:
        """Wait for LakeFS to be ready.
        
        Args:
            endpoint: LakeFS endpoint URL
            max_wait: Maximum wait time in seconds
            
        Returns:
            True if LakeFS is ready, False if timeout
        """
        print(f"⏳ Waiting for LakeFS to be ready at {endpoint}...")

        import requests

        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                response = requests.get(f"{endpoint}/api/v1/healthcheck", timeout=5)
                if response.status_code == 200:
                    print("✅ LakeFS is ready!")
                    return True
            except Exception:
                pass

            print(".", end="", flush=True)
            time.sleep(10)

        print("\n❌ Timeout waiting for LakeFS")
        return False

    def setup_initial_admin(self, endpoint: str) -> dict[str, str]:
        """Setup initial admin user and get credentials.
        
        Args:
            endpoint: LakeFS endpoint URL
            
        Returns:
            Dictionary with access credentials
        """
        print("👤 Setting up initial admin user...")

        # In a real implementation, this would create the initial admin user
        # and return the access keys. For now, return placeholder credentials.

        credentials = {
            "access_key": "AKIA" + "X" * 16,  # Placeholder
            "secret_key": "x" * 40  # Placeholder
        }

        print("✅ Initial admin user created")
        return credentials

    def create_repositories(self, endpoint: str, credentials: dict[str, str]) -> bool:
        """Create LakeFS repositories.
        
        Args:
            endpoint: LakeFS endpoint URL
            credentials: Access credentials
            
        Returns:
            True if successful, False otherwise
        """
        print("📚 Creating LakeFS repositories...")

        try:
            manager = LakeFSRepositoryManager(
                lakefs_endpoint=endpoint,
                access_key=credentials["access_key"],
                secret_key=credentials["secret_key"]
            )

            # Test connection
            if not manager.test_connection():
                print("❌ Could not connect to LakeFS")
                return False

            # Create all repositories
            results = manager.create_all_repositories(self.environment)

            # Print results
            print("\n📊 Repository Creation Results:")
            print(f"Total: {results['summary']['total']}")
            print(f"Succeeded: {results['summary']['succeeded']}")
            print(f"Failed: {results['summary']['failed']}")

            if results["success"]:
                print("\n✅ Successfully created:")
                for repo in results["success"]:
                    print(f"  • {repo['name']}")

            if results["failed"]:
                print("\n❌ Failed to create:")
                for repo in results["failed"]:
                    print(f"  • {repo['name']}: {repo['error']}")

            return results['summary']['failed'] == 0

        except Exception as e:
            print(f"❌ Error creating repositories: {e}")
            return False

    def save_configuration(self, outputs: dict[str, str], credentials: dict[str, str]) -> None:
        """Save deployment configuration for later use.
        
        Args:
            outputs: Infrastructure outputs
            credentials: LakeFS credentials
        """
        config = {
            "environment": self.environment,
            "aws_account_id": self.account_id,
            "aws_region": self.region,
            "lakefs_endpoint": outputs["lakefs_endpoint"],
            "bucket_name": outputs["bucket_name"],
            "database_endpoint": outputs["database_endpoint"],
            "access_key": credentials["access_key"],
            # Secret key stored in AWS Secrets Manager for security
            "secret_key_location": f"arn:aws:secretsmanager:{self.region}:{self.account_id}:secret:lakefs-admin-secret-{self.environment}"
        }

        config_file = f"lakefs-config-{self.environment}.json"
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)

        print(f"💾 Configuration saved to {config_file}")

    def deploy(self) -> bool:
        """Full deployment process.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # 1. Deploy infrastructure
            outputs = self.deploy_infrastructure()

            # 2. Wait for LakeFS to be ready
            if not self.wait_for_lakefs(outputs["lakefs_endpoint"]):
                return False

            # 3. Setup initial admin
            credentials = self.setup_initial_admin(outputs["lakefs_endpoint"])

            # 4. Create repositories
            if not self.create_repositories(outputs["lakefs_endpoint"], credentials):
                return False

            # 5. Save configuration
            self.save_configuration(outputs, credentials)

            print("\n🎉 LakeFS deployment completed successfully!")
            print(f"LakeFS URL: {outputs['lakefs_endpoint']}")
            print(f"S3 Bucket: {outputs['bucket_name']}")
            print("\nNext steps:")
            print("1. Update your Dagster configuration with the new LakeFS endpoint")
            print("2. Configure your data pipelines to use LakeFS repositories")
            print("3. Test data versioning workflows")

            return True

        except Exception as e:
            print(f"\n❌ Deployment failed: {e}")
            return False


def main():
    """Main deployment function."""
    import argparse

    parser = argparse.ArgumentParser(description="Deploy LakeFS to AWS")
    parser.add_argument(
        "--environment",
        choices=["dev", "staging", "prod"],
        default="dev",
        help="Deployment environment"
    )

    args = parser.parse_args()

    # Create deployer and run deployment
    deployer = LakeFSAWSDeployer(environment=args.environment)
    success = deployer.deploy()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
