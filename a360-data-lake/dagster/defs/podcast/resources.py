"""Podcast pipeline resources for Dagster.
This module provides resources specific to podcast processing including
Deepgram client and LakeFS integration.
"""

from dagster import ConfigurableResource, EnvVar
from deepgram import DeepgramClient, PrerecordedOptions, FileSource
from lakefs_client.client import LakeFSClient
from lakefs_client import models, Configuration
from pydantic import Field
from typing import Any
import json


class DeepgramResource(ConfigurableResource):
    """Resource for Deepgram transcription API access."""

    api_key_secret_name: str = Field(
        default="dagster/a360-dagster/deepgram-api-key",
        description="AWS Secrets Manager secret name for API key",
    )

    def get_client(self, secrets_manager) -> DeepgramClient:
        """Get configured Deepgram client.
        Args:
            secrets_manager: AWS Secrets Manager resource.
        Returns:
            Configured Deepgram client.
        """
        try:
            api_key = secrets_manager.get_secret(self.api_key_secret_name)
            return DeepgramClient(api_key)
        except Exception as e:
            raise RuntimeError(f"Failed to create Deepgram client: {e}") from e

    def transcribe_batch(self, client: DeepgramClient, audio_data: bytes, sample_rate: int = 22050) -> dict[str, Any]:
        """Transcribe audio using batch API.
        Args:
            client: Deepgram client instance.
            audio_data: Audio file data as bytes.
            sample_rate: Audio sample rate.
        Returns:
            Transcription results dictionary.
        """
        try:
            source: FileSource = {"buffer": audio_data}

            options = PrerecordedOptions(
                model="nova-3-medical",
                smart_format=True,
                punctuate=True,
                paragraphs=True,
                diarize=True,
                language="en",
            )

            response = client.listen.rest.v("1").transcribe_file(source, options)
            return json.loads(response.to_json())
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse Deepgram response: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to transcribe audio: {e}") from e


class LakeFSResource(ConfigurableResource):
    """Resource for LakeFS data versioning."""

    endpoint: str = Field(description="LakeFS endpoint URL")
    access_key_id: str = Field(description="LakeFS access key ID")
    secret_access_key: str = Field(description="LakeFS secret access key")
    repository: str = Field(default="a360-datalake", description="LakeFS repository name")

    def get_client(self) -> LakeFSClient:
        """Get configured LakeFS client.
        Returns:
            Configured LakeFS client.
        """
        try:
            configuration = Configuration()
            configuration.username = self.access_key_id
            configuration.password = self.secret_access_key
            configuration.host = self.endpoint

            return LakeFSClient(configuration)
        except Exception as e:
            raise RuntimeError(f"Failed to create LakeFS client: {e}") from e

    def create_branch(self, client: LakeFSClient, branch_name: str, source: str = "main") -> str:
        """Create new branch in LakeFS.
        Args:
            client: LakeFS client instance.
            branch_name: Name for new branch.
            source: Source branch to create from.
        Returns:
            Branch ID.
        """
        try:
            branch_creation = models.BranchCreation(name=branch_name, source=source)
            result = client.branches.create_branch(repository=self.repository, branch_creation=branch_creation)
            return result.id
        except Exception as e:
            raise RuntimeError(f"Failed to create branch '{branch_name}' in repository '{self.repository}': {e}") from e


def get_podcast_resources() -> dict[str, ConfigurableResource]:
    """Get podcast-specific resources.
    Returns:
        Dictionary of podcast resources.
    """
    try:
        return {
            "deepgram": DeepgramResource(),
            "lakefs": LakeFSResource(
                endpoint=EnvVar("LAKEFS_ENDPOINT"),
                access_key_id=EnvVar("LAKEFS_ACCESS_KEY_ID"),
                secret_access_key=EnvVar("LAKEFS_SECRET_ACCESS_KEY"),
            ),
        }
    except Exception as e:
        # Return empty dict if environment variables are not available
        print(f"Podcast resources not available due to missing environment variables: {e}")
        return {}
