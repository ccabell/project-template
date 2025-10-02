"""AWS resource definitions for Dagster pipelines.
This module provides configured AWS resources including S3, Secrets Manager,
and Bedrock clients for use in Dagster assets and ops.
"""

from dagster import ConfigurableResource
from botocore.client import BaseClient
from botocore.exceptions import ClientError, ConnectionError, BotoCoreError, ParamValidationError
from botocore.config import Config
import boto3
from pydantic import Field
import json
import binascii
import uuid
import os

# Handle optional dagster_aws dependency
try:
    from dagster_aws.s3 import S3Resource
except ImportError:
    # Fallback S3Resource for development/testing environments
    import logging as _logging

    _logging.getLogger(__name__).warning("dagster_aws.s3 not available; using local S3Resource fallback.")

    class S3Resource(ConfigurableResource):
        region_name: str = Field(default="us-east-1")

        def get_client(self) -> BaseClient:
            return boto3.client("s3", region_name=self.region_name)


class BedrockResource(ConfigurableResource):
    """Resource for interacting with AWS Bedrock service."""

    region_name: str = Field(default="us-east-1", description="AWS region for Bedrock")
    model_id: str = Field(
        default="arn:aws:bedrock:us-east-1:{account}:inference-profile/us.anthropic.claude-sonnet-4-20250514-v1:0",
        description="Bedrock model identifier or inference-profile ARN (account ID resolved dynamically)",
    )
    connect_timeout_secs: int = Field(default=5, description="Bedrock client connect timeout (s)")
    read_timeout_secs: int = Field(default=30, description="Bedrock client read timeout (s)")
    max_retries: int = Field(default=3, description="Bedrock client max retry attempts")

    def get_client(self) -> BaseClient:
        """Get configured Bedrock client.
        Returns:
            Configured boto3 Bedrock client.
        """
        cfg = Config(
            connect_timeout=self.connect_timeout_secs,
            read_timeout=self.read_timeout_secs,
            retries={"max_attempts": self.max_retries, "mode": "standard"},
        )
        return boto3.client("bedrock-runtime", region_name=self.region_name, config=cfg)

    def _get_account_id(self) -> str:
        """Get current AWS account ID dynamically.
        Returns:
            AWS account ID as string.
        """
        try:
            sts_client = boto3.client("sts", region_name=self.region_name)
            response = sts_client.get_caller_identity()
            return response["Account"]
        except (ClientError, ConnectionError):
            # Fallback to environment variable
            acct = os.getenv("AWS_ACCOUNT_ID") or os.getenv("CDK_DEFAULT_ACCOUNT")
            if acct and acct.isdigit() and len(acct) == 12:
                import logging
                logging.getLogger(__name__).warning(
                    "Using fallback AWS account ID from environment: %s", acct[:4] + "****" + acct[-4:]
                )
                return acct
            raise RuntimeError("Unable to resolve AWS account ID and no AWS_ACCOUNT_ID/CDK_DEFAULT_ACCOUNT fallback set.")

    def resolve_model_id(self, model_id: str) -> str:
        """Resolve model ID with dynamic account ID if needed.
        Args:
            model_id: Model ID that may contain account placeholder.
        Returns:
            Resolved model ID with actual account ID.
        """
        # Replace {account} placeholder with actual account ID
        if "{account}" in model_id:
            account_id = self._get_account_id()
            return model_id.replace("{account}", account_id)
        
        # If it's an inference profile ARN with hardcoded account, make it dynamic
        if "arn:aws:bedrock:" in model_id and ":inference-profile/" in model_id:
            # Extract the inference profile name and region
            parts = model_id.split(":")
            if len(parts) >= 6:
                region = parts[3]
                profile_name = parts[5].split("/")[-1]
                account_id = self._get_account_id()
                return f"arn:aws:bedrock:{region}:{account_id}:inference-profile/{profile_name}"
        
        return model_id

    def invoke_text_model(
        self, prompt: str, max_tokens: int = 1024, system: str | None = None, extra: dict | None = None, model_id: str | None = None
    ) -> str:
        """Invoke Bedrock text generation model with prompt.
        Args:
            prompt: Input prompt for the model.
            max_tokens: Maximum tokens in response.
            system: System message (optional).
            extra: Additional parameters (optional).
            model_id: Override default model ID (optional).
        Returns:
            Model response text.
        """
        try:
            client = self.get_client()

            messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]

            payload = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "messages": messages,
            }
            if system:
                payload["system"] = system
            if extra:
                payload.update(extra)

            resolved_model_id = self.resolve_model_id(model_id or self.model_id)
            response = client.invoke_model(
                modelId=resolved_model_id,
                body=json.dumps(payload).encode("utf-8"),
                contentType="application/json",
                accept="application/json",
            )
            result = json.loads(response["body"].read())

            # 1) Anthropic messages: top-level content list
            content = result.get("content")
            if isinstance(content, list) and content:
                texts = [i.get("text", "") for i in content if isinstance(i, dict) and i.get("type") == "text"]
                if texts:
                    return "\n\n".join(texts)

            # 2) Bedrock Anthropic wrapper: output.message.content
            msg_content = result.get("output", {}).get("message", {}).get("content", [])
            if isinstance(msg_content, list) and msg_content:
                texts = [i.get("text", "") for i in msg_content if isinstance(i, dict) and i.get("type") == "text"]
                if texts:
                    return "\n\n".join(texts)

            # 3) Fallbacks used by some providers
            if isinstance(result.get("output_text"), str):
                return result["output_text"]
            for key in ("output", "completion"):
                if key in result:
                    return str(result[key])
            return ""
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse Bedrock response: {str(e)}") from e
        except (ClientError, BotoCoreError, ConnectionError, TimeoutError, ParamValidationError) as e:
            raise RuntimeError(f"Failed to invoke Bedrock model: {str(e)}") from e

    def invoke_embedding_model(self, texts: list[str], model_id: str = "cohere.embed-english-v3") -> list[list[float]]:
        """Invoke Bedrock embedding model to generate embeddings.
        Args:
            texts: List of texts to generate embeddings for.
            model_id: Embedding model ID (default: Cohere).
        Returns:
            List of embedding vectors.
        """
        try:
            client = self.get_client()
            
            if model_id.startswith("cohere."):
                # Cohere embedding model format
                payload = {
                    "input_type": "search_document",
                    "texts": texts,
                    "embedding_types": ["float"],
                }
            elif model_id.startswith("amazon.titan-embed"):
                # Titan embedding model format
                payload = {
                    "inputText": texts[0] if len(texts) == 1 else texts,
                }
            else:
                raise ValueError(f"Unsupported embedding model: {model_id}")

            response = client.invoke_model(
                modelId=model_id,
                body=json.dumps(payload).encode("utf-8"),
                contentType="application/json",
                accept="application/json",
            )
            result = json.loads(response["body"].read())

            # Handle different response formats
            if model_id.startswith("cohere."):
                return result.get("embeddings", [])
            elif model_id.startswith("amazon.titan-embed"):
                embedding = result.get("embedding", [])
                return [embedding] if len(texts) == 1 else embedding
            else:
                return []

        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse embedding response: {str(e)}") from e
        except (ClientError, BotoCoreError, ConnectionError, TimeoutError, ParamValidationError) as e:
            raise RuntimeError(f"Failed to invoke embedding model: {str(e)}") from e

    # Backward compatibility methods
    def invoke_model(
        self, prompt: str = None, max_tokens: int = 1024, system: str | None = None, extra: dict | None = None,
        model_id: str = None, body: str = None
    ) -> str | dict:
        """Backward compatibility method - supports both old and new API patterns.
        
        New pattern: invoke_model(prompt="...", max_tokens=1024)
        Old pattern: invoke_model(model_id="...", body="...")
        """
        if body is not None and model_id is not None:
            # Old API pattern - return raw response for compatibility
            try:
                client = self.get_client()
                response = client.invoke_model(
                    modelId=model_id,
                    body=body,
                    contentType="application/json",
                    accept="application/json",
                )
                return json.loads(response["body"].read())
            except Exception as e:
                raise RuntimeError(f"Failed to invoke model: {str(e)}") from e
        else:
            # New API pattern - delegate to text model method
            return self.invoke_text_model(prompt or "", max_tokens, system, extra, model_id)


class SecretsManagerResource(ConfigurableResource):
    """Resource for AWS Secrets Manager access."""

    region_name: str = Field(default="us-east-1", description="AWS region")

    def get_secret(self, secret_name: str) -> str:
        """Retrieve secret value from AWS Secrets Manager.
        Args:
            secret_name: Name of the secret to retrieve.
        Returns:
            Secret value as string.
        """
        try:
            client = boto3.client("secretsmanager", region_name=self.region_name)
            response = client.get_secret_value(SecretId=secret_name)

            # Handle both string and binary secret types
            if "SecretString" in response:
                return response["SecretString"]
            else:
                import base64

                return base64.b64decode(response["SecretBinary"]).decode("utf-8")
        except (ClientError, binascii.Error, UnicodeDecodeError) as e:
            raise RuntimeError(f"Failed to retrieve secret '{secret_name}': {e}") from e


class ComprehendMedicalResource(ConfigurableResource):
    """Enhanced resource for comprehensive PHI/PII detection using AWS Comprehend Medical plus custom patterns."""

    region_name: str = Field(default="us-east-1", description="AWS region for Comprehend Medical")
    confidence_threshold: float = Field(default=0.7, description="Minimum confidence threshold for entity detection")
    
    def get_client(self) -> BaseClient:
        """Get configured Comprehend Medical client.
        Returns:
            Configured boto3 Comprehend Medical client.
        """
        return boto3.client("comprehendmedical", region_name=self.region_name)

    def _get_pii_regex_patterns(self) -> dict:
        """Get comprehensive regex patterns for PII detection.
        Returns:
            Dictionary mapping entity types to compiled regex patterns.
        """
        import re
        
        # Primary context-aware patterns
        primary_patterns = {
            "SSN": re.compile(r"(?:SSN|Social Security|Social Security Number):?\s*(\d{3}[-.]?\d{2}[-.]?\d{4})\b", re.IGNORECASE),
            "PHONE": re.compile(r"(?:Phone|Tel|Telephone|Cell|Mobile):?\s*(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})", re.IGNORECASE),
            "EMAIL": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
            "CREDIT_CARD": re.compile(r"(?:Credit Card|Card|CC):?\s*((?:\d{4}[-\s]?){3}\d{4})\b", re.IGNORECASE),
            "ADDRESS": re.compile(r"(?:Address|Addr):?\s*(\d+\s+[A-Za-z0-9\s,.-]+?(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Court|Ct)(?:\s+[A-Za-z\s]+)?,?\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?)\b", re.IGNORECASE),
            "DRIVERS_LICENSE": re.compile(r"(?:Driver['\s]?s?\s?License|DL|License):?\s*([A-Z]{2}[-.]?[A-Z0-9]{6,12})\b", re.IGNORECASE),
            "BANK_ACCOUNT": re.compile(r"(?:Bank Account|Account|Account Number|Acct):?\s*(\d{8,17})\b", re.IGNORECASE),
            "ROUTING_NUMBER": re.compile(r"(?:Routing|Routing Number|ABA):?\s*([0-9]{9})\b", re.IGNORECASE),
            "DATE_OF_BIRTH": re.compile(r"(?:DOB|Date of Birth|Born):?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{4})\b", re.IGNORECASE),
        }
        
        # Fallback patterns for standalone entities (lower priority)
        fallback_patterns = {
            "PHONE_STANDALONE": re.compile(r"\b\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
            "SSN_STANDALONE": re.compile(r"\b\d{3}[-.]?\d{2}[-.]?\d{4}\b"),
            "CREDIT_CARD_STANDALONE": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
            "ZIP_CODE": re.compile(r"\b\d{5}(?:[-]\d{4})?\b"),
            "IP_ADDRESS": re.compile(r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"),
            "URL": re.compile(r"https?://[A-Za-z0-9.-]+(?:/[A-Za-z0-9._~:/?#[\]@!$&'()*+,;=-]*)?"),
            "NPI_NUMBER": re.compile(r"\bNPI:?\s*(\d{10})\b", re.IGNORECASE),
            "MEDICAL_LICENSE": re.compile(r"License #:?\s*([A-Z]{2}-[A-Z]{2}-\d{5})\b", re.IGNORECASE),
        }
        
        # Combine all patterns
        all_patterns = {}
        all_patterns.update(primary_patterns)
        all_patterns.update(fallback_patterns)
        
        return all_patterns
    
    def _detect_custom_pii(self, text: str) -> list:
        """Detect PII using custom regex patterns.
        Args:
            text: Input text to analyze.
        Returns:
            List of detected PII entities with position information.
        """
        entities = []
        patterns = self._get_pii_regex_patterns()
        
        for entity_type, pattern in patterns.items():
            for match in pattern.finditer(text):
                # Use the first capture group if available, otherwise the whole match
                if match.groups():
                    entity_text = match.group(1)
                    begin_offset = match.start(1)
                    end_offset = match.end(1)
                else:
                    entity_text = match.group()
                    begin_offset = match.start()
                    end_offset = match.end()
                
                entities.append({
                    "Text": entity_text,
                    "Type": entity_type,
                    "BeginOffset": begin_offset,
                    "EndOffset": end_offset,
                    "Score": 0.95,  # High confidence for regex matches
                    "Source": "regex"
                })
        
        return entities

    def detect_phi(self, text: str) -> dict:
        """Detect PHI (Protected Health Information) in text using AWS Comprehend Medical.
        Args:
            text: Input text to analyze.
        Returns:
            Dictionary containing detected PHI entities.
        """
        try:
            if len(text.encode("utf-8")) > 20000:
                raise ValueError("detect_phi text exceeds Comprehend Medical 20KB limit; chunk upstream.")
            client = self.get_client()
            return client.detect_phi(Text=text)
        except (ClientError, BotoCoreError, ConnectionError, TimeoutError, ValueError) as e:
            raise RuntimeError(f"Failed to detect PHI: {e}") from e
    
    def detect_comprehensive_pii_phi(self, text: str) -> dict:
        """Detect comprehensive PHI/PII using both AWS Comprehend Medical and custom regex patterns.
        Args:
            text: Input text to analyze.
        Returns:
            Dictionary containing all detected PHI/PII entities from both sources.
        """
        all_entities = []
        
        try:
            # Detect PHI using AWS Comprehend Medical (medical-specific)
            if len(text.encode("utf-8")) <= 20000:
                phi_response = self.detect_phi(text)
                
                # Add high-confidence PHI entities
                for entity in phi_response.get("Entities", []):
                    if entity.get("Score", 0) >= self.confidence_threshold:
                        entity["Source"] = "comprehend_medical"
                        all_entities.append(entity)
            
            # Detect general PII using custom regex patterns
            custom_pii = self._detect_custom_pii(text)
            all_entities.extend(custom_pii)
            
            # Remove duplicates (overlapping entities)
            all_entities = self._remove_overlapping_entities(all_entities)
            
            return {
                "Entities": all_entities,
                "DetectionMethods": ["comprehend_medical", "regex_patterns"],
                "TotalEntities": len(all_entities),
                "ConfidenceThreshold": self.confidence_threshold
            }
            
        except Exception as e:
            # Fallback to regex-only detection if Comprehend Medical fails
            custom_pii = self._detect_custom_pii(text)
            return {
                "Entities": custom_pii,
                "DetectionMethods": ["regex_patterns"],
                "TotalEntities": len(custom_pii),
                "ConfidenceThreshold": self.confidence_threshold,
                "Note": f"Comprehend Medical failed: {e}"
            }
    
    def _remove_overlapping_entities(self, entities: list) -> list:
        """Remove overlapping entities, keeping the most specific/appropriate one.
        Args:
            entities: List of detected entities.
        Returns:
            List of non-overlapping entities.
        """
        if not entities:
            return []
        
        # Define entity type priority (higher priority = more specific/preferred)
        entity_priority = {
            "SSN": 10,
            "CREDIT_CARD": 9,
            "DRIVERS_LICENSE": 8,
            "EMAIL": 7,
            "PHONE": 6,
            "ADDRESS": 5,
            "BANK_ACCOUNT": 4,
            "ROUTING_NUMBER": 3,
            "MEDICAL_LICENSE": 6,
            "NPI_NUMBER": 5,
            "DATE_OF_BIRTH": 4,
            "ZIP_CODE": 2,
            "IP_ADDRESS": 1,
            "URL": 1,
            # Standalone patterns have lower priority than context-aware ones
            "PHONE_STANDALONE": 5,
            "SSN_STANDALONE": 9,
            "CREDIT_CARD_STANDALONE": 8
        }
        
        # Group entities by position
        position_groups = {}
        for entity in entities:
            pos_key = (entity["BeginOffset"], entity["EndOffset"])
            if pos_key not in position_groups:
                position_groups[pos_key] = []
            position_groups[pos_key].append(entity)
        
        # For each position, keep the highest priority entity
        filtered_entities = []
        for pos_group in position_groups.values():
            if len(pos_group) == 1:
                filtered_entities.append(pos_group[0])
            else:
                # Multiple entities at same position - pick the highest priority
                best_entity = max(pos_group, key=lambda x: (
                    entity_priority.get(x["Type"], 0),
                    x["Score"]
                ))
                filtered_entities.append(best_entity)
        
        # Now handle overlapping entities at different positions
        filtered_entities.sort(key=lambda x: x["BeginOffset"])
        final_entities = []
        
        for entity in filtered_entities:
            # Check if this entity overlaps with any already added entity
            overlaps = False
            for existing in final_entities:
                if not (entity["EndOffset"] <= existing["BeginOffset"] or 
                       entity["BeginOffset"] >= existing["EndOffset"]):
                    # Overlapping - keep the higher priority one
                    if (entity_priority.get(entity["Type"], 0) > 
                        entity_priority.get(existing["Type"], 0)):
                        # Remove the existing lower priority entity
                        final_entities.remove(existing)
                    else:
                        overlaps = True
                    break
            
            if not overlaps:
                final_entities.append(entity)
        
        return final_entities

    def detect_entities(self, text: str) -> dict:
        """Detect medical entities in text.
        Args:
            text: Input text to analyze.
        Returns:
            Dictionary containing detected medical entities.
        """
        try:
            if len(text.encode("utf-8")) > 20000:
                raise ValueError("detect_entities text exceeds Comprehend Medical 20KB limit; chunk upstream.")
            client = self.get_client()
            return client.detect_entities_v2(Text=text)
        except (ClientError, BotoCoreError, ConnectionError, TimeoutError, ValueError) as e:
            raise RuntimeError(f"Failed to detect medical entities: {e}") from e


class MacieResource(ConfigurableResource):
    """Resource for AWS Macie service."""

    region_name: str = Field(default="us-east-1", description="AWS region for Macie")

    def get_client(self) -> BaseClient:
        """Get configured Macie client.
        Returns:
            Configured boto3 Macie client.
        """
        return boto3.client("macie2", region_name=self.region_name)

    def _get_account_id(self) -> str:
        """Get current AWS account ID.
        Returns:
            AWS account ID as string.
        """
        try:
            sts_client = boto3.client("sts", region_name=self.region_name)
            response = sts_client.get_caller_identity()
            return response["Account"]
        except (ClientError, ConnectionError):
            acct = os.getenv("AWS_ACCOUNT_ID")
            if acct and acct.isdigit() and len(acct) == 12:
                return acct
            raise RuntimeError("Unable to resolve AWS account ID and no AWS_ACCOUNT_ID fallback set.")

    def create_classification_job(self, job_name: str, s3_bucket: str, s3_prefix: str = "") -> dict:
        """Create a Macie classification job.
        Args:
            job_name: Name for the classification job.
            s3_bucket: S3 bucket to analyze.
            s3_prefix: Optional S3 prefix to limit analysis.
        Returns:
            Dictionary containing job creation response.
        """
        try:
            client = self.get_client()

            job_definition = {
                "clientToken": f"{job_name}-{uuid.uuid4().hex[:8]}",
                "name": job_name,
                "jobType": "ONE_TIME",
                "s3JobDefinition": {
                    "bucketDefinitions": [{"accountId": self._get_account_id(), "buckets": [s3_bucket]}]
                },
                "managedDataIdentifierSelector": "ALL",
            }

            if s3_prefix:
                job_definition["s3JobDefinition"]["scoping"] = {
                    "includes": {
                        "and": [
                            {
                                "simpleScopeTerm": {
                                    "comparator": "STARTS_WITH",
                                    "key": "OBJECT_KEY",
                                    "values": [s3_prefix],
                                }
                            }
                        ]
                    }
                }

            return client.create_classification_job(**job_definition)
        except (ClientError, BotoCoreError, ConnectionError, TimeoutError) as e:
            raise RuntimeError(f"Failed to create Macie classification job: {e}") from e

    def get_classification_job(self, job_id: str) -> dict:
        """Get details of a Macie classification job.
        Args:
            job_id: ID of the classification job.
        Returns:
            Dictionary containing job details.
        """
        try:
            client = self.get_client()
            return client.describe_classification_job(jobId=job_id)
        except (ClientError, BotoCoreError, ConnectionError, TimeoutError) as e:
            raise RuntimeError(f"Failed to get Macie classification job: {e}") from e


def get_aws_resources() -> dict[str, ConfigurableResource]:
    """Get configured AWS resources for Dagster.
    Returns:
        Dictionary of AWS resources.
    """
    session = boto3.session.Session()
    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or (session.region_name or "us-east-1")
    model_id = os.getenv("BEDROCK_MODEL_ID", "arn:aws:bedrock:us-east-1:{account}:inference-profile/us.anthropic.claude-sonnet-4:0")
    return {
        "s3": S3Resource(region_name=region),
        "bedrock": BedrockResource(region_name=region, model_id=model_id),
        "secrets_manager": SecretsManagerResource(region_name=region),
        "comprehend_medical": ComprehendMedicalResource(region_name=region),
        "macie": MacieResource(region_name=region),
    }
