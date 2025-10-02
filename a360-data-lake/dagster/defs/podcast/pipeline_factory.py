"""Factory for creating podcast ingestion pipelines.

This module provides a factory function that creates complete Dagster
pipelines for individual RSS podcast feeds, including assets, sensors,
and jobs.
"""

from dataclasses import dataclass
import httpx
from datetime import datetime
import dagster as dg
import feedparser
from defs.podcast.utils import get_audio_url_from_entry, get_s3_key, sanitize_episode_id, sanitize_s3_metadata
from utils.audio_processing import process_audio_with_ffmpeg
from dagster_aws.s3 import S3Resource
from defs.podcast.resources import DeepgramResource
from defs.podcast.utils import make_bias_analysis_prompt
from defs.aws.resources import BedrockResource, SecretsManagerResource
from defs.aws.utils import parse_bedrock_json_response
import os


ENV = (os.getenv("ENVIRONMENT") or "dev").lower()


def _podcast_bucket(tier: str) -> str:
    return f"a360-{ENV}-podcast-{tier}"


class ProcessedAudioConfig(dg.Config):
    """Configuration for processed audio asset."""

    speed_factor: float = 2.0


@dataclass
class RSSFeedDefinition:
    """Configuration for an RSS podcast feed."""

    name: str
    url: str
    max_backfill_size: int = 3


def podcast_pipeline_factory(feed_definition: RSSFeedDefinition) -> dg.Definitions:
    """Create Dagster pipeline for podcast feed.

    Args:
        feed_definition: RSS feed configuration.

    Returns:
        Definitions object with assets, sensors, and jobs.
    """
    partition_def = dg.DynamicPartitionsDefinition(name=f"{feed_definition.name}_episodes")

    class AudioConfig(dg.Config):
        """Configuration for audio processing."""

        audio_url: str
        episode_title: str
        published_date: str

    @dg.asset(
        name=f"{feed_definition.name}_raw_audio",
        partitions_def=partition_def,
        compute_kind="python",
        group_name="podcast_ingestion",
    )
    def raw_audio_asset(
        context: dg.AssetExecutionContext,
        config: AudioConfig,
        s3: S3Resource,
    ) -> dg.MaterializeResult:
        """Download and store raw podcast audio.

        Args:
            context: Dagster execution context.
            config: Audio configuration with URL and metadata.
            s3: S3 resource for storage.

        Returns:
            Materialization result with metadata.
        """

        audio_key = get_s3_key(
            "bronze",
            "podcasts",
            feed_definition.name,
            context.partition_key,
            "audio.mp3",
        )

        context.log.info(f"Downloading audio from {config.audio_url}")

        client = s3.get_client()
        bucket = context.op_config.get("s3_bucket", _podcast_bucket("bronze"))

        existing = client.list_objects_v2(Bucket=bucket, Prefix=audio_key)
        if existing.get("Contents"):
            context.log.info("Audio already exists, skipping download")
            return dg.MaterializeResult(
                metadata={
                    "status": "cached",
                    "key": audio_key,
                    "episode_title": config.episode_title,
                },
            )

        response = httpx.get(config.audio_url, follow_redirects=True, timeout=300)
        response.raise_for_status()

        client.put_object(
            Bucket=bucket,
            Key=audio_key,
            Body=response.content,
            Metadata=sanitize_s3_metadata(
                {
                    "episode_title": config.episode_title,
                    "published_date": config.published_date,
                    "source_url": config.audio_url,
                }
            ),
        )

        return dg.MaterializeResult(
            metadata={
                "status": "downloaded",
                "key": audio_key,
                "size_bytes": len(response.content),
                "episode_title": config.episode_title,
            },
        )

    @dg.asset(
        name=f"{feed_definition.name}_processed_audio",
        partitions_def=partition_def,
        deps=[raw_audio_asset],
        compute_kind="ffmpeg",
        group_name="podcast_ingestion",
    )
    def processed_audio_asset(
        context: dg.AssetExecutionContext,
        s3: S3Resource,
        config: ProcessedAudioConfig,
    ) -> dg.MaterializeResult:
        """Process audio with ffmpeg for optimization.

        Args:
            context: Dagster execution context.
            s3: S3 resource for storage.

        Returns:
            Materialization result with processing metadata.
        """

        client = s3.get_client()

        input_key = get_s3_key(
            "bronze",
            "podcasts",
            feed_definition.name,
            context.partition_key,
            "audio.mp3",
        )

        output_key = get_s3_key(
            "bronze",
            "podcasts",
            feed_definition.name,
            context.partition_key,
            f"audio_{str(config.speed_factor).replace('.', '_').rstrip('0').rstrip('_')}x.mp3",
        )

        context.log.info(f"Processing audio with ffmpeg at {config.speed_factor}x speed")

        # make the bronze bucket name configurable, with a sensible default
        bronze_bucket = context.op_config.get("s3_bronze_bucket", _podcast_bucket("bronze"))
        response = client.get_object(Bucket=bronze_bucket, Key=input_key)
        audio_data = response["Body"].read()

        processed_data, duration_original, duration_processed = process_audio_with_ffmpeg(
            audio_data,
            speed_factor=config.speed_factor,
            sample_rate=22050,
            bitrate="64k",
        )

        client.put_object(
            Bucket=bronze_bucket,
            Key=output_key,
            Body=processed_data,
            Metadata={
                "original_duration": str(duration_original),
                "processed_duration": str(duration_processed),
                "speed_factor": str(config.speed_factor),
            },
        )

        return dg.MaterializeResult(
            metadata={
                "output_key": output_key,
                "original_duration_seconds": duration_original,
                "processed_duration_seconds": duration_processed,
                "reduction_percent": round((1 - duration_processed / duration_original) * 100, 2),
                "processed_size_bytes": len(processed_data),
            },
        )

    @dg.asset(
        name=f"{feed_definition.name}_transcript",
        partitions_def=partition_def,
        deps=[processed_audio_asset],
        compute_kind="deepgram",
        group_name="podcast_ingestion",
    )
    def transcript_asset(
        context: dg.AssetExecutionContext,
        s3: S3Resource,
        deepgram: DeepgramResource,
        secrets_manager: SecretsManagerResource,
    ) -> dg.MaterializeResult:
        """Transcribe audio using Deepgram batch API.

        Args:
            context: Dagster execution context.
            s3: S3 resource for storage.
            deepgram: Deepgram resource.
            secrets_manager: AWS Secrets Manager resource.
            lakefs: LakeFS resource for versioning.

        Returns:
            Materialization result with transcript metadata.
        """
        import json

        client = s3.get_client()

        audio_key = get_s3_key(
            "bronze",
            "podcasts",
            feed_definition.name,
            context.partition_key,
            f"audio_{str(ProcessedAudioConfig().speed_factor).replace('.', '_').rstrip('0').rstrip('_')}x.mp3",
        )

        transcript_key = get_s3_key(
            "silver",
            "podcasts",
            feed_definition.name,
            context.partition_key,
            "transcript.json",
        )

        context.log.info("Fetching processed audio for transcription")

        response = client.get_object(Bucket=_podcast_bucket("bronze"), Key=audio_key)
        audio_data = response["Body"].read()
        context.log.info("Sending audio to Deepgram for transcription")
        dg_client = deepgram.get_client(secrets_manager)
        transcript_result = deepgram.transcribe_batch(dg_client, audio_data)

        transcript_data = {
            "podcast": feed_definition.name,
            "episode_id": context.partition_key,
            "transcription_timestamp": datetime.utcnow().isoformat(),
            "model": "nova-3-medical",
            "results": transcript_result,
        }

        # lakefs_client = lakefs.get_client()
        # branch_name = f"transcript-{context.run_id}"
        # lakefs.create_branch(lakefs_client, branch_name)

        client.put_object(
            Bucket=_podcast_bucket("silver"),
            Key=transcript_key,
            Body=json.dumps(transcript_data, indent=2),
            ContentType="application/json",
        )

        if transcript_result.get("results", {}).get("channels", []):
            transcript_text = transcript_result["results"]["channels"][0]["alternatives"][0]["transcript"]
            word_count = len(transcript_text.split())
        else:
            transcript_text = ""
            word_count = 0

        return dg.MaterializeResult(
            metadata={
                "transcript_key": transcript_key,
                "word_count": word_count,
                "duration": transcript_result.get("metadata", {}).get("duration", 0),
                # "lakefs_branch": branch_name,
                "model": "nova-3-medical",
            },
        )

    @dg.asset(
        name=f"{feed_definition.name}_cleaned_transcript",
        partitions_def=partition_def,
        deps=[transcript_asset],
        compute_kind="bedrock",
        group_name="podcast_ingestion",
    )
    def cleaned_transcript_asset(
        context: dg.AssetExecutionContext,
        s3: S3Resource,
        bedrock: BedrockResource,
    ) -> dg.MaterializeResult:
        import json
        from itertools import groupby

        client = s3.get_client()

        transcript_key = get_s3_key(
            "silver", "podcasts", feed_definition.name, context.partition_key, "transcript.json"
        )
        cleaned_key = get_s3_key(
            "silver", "podcasts", feed_definition.name, context.partition_key, "cleaned_transcript.json"
        )

        response = client.get_object(Bucket=_podcast_bucket("silver"), Key=transcript_key)
        transcript_data = json.loads(response["Body"].read())

        words = transcript_data["results"]["results"]["channels"][0]["alternatives"][0].get("words", [])

        if not words:
            context.log.warning("No words with diarization found")
            return dg.MaterializeResult(metadata={"status": "skipped", "reason": "no_diarization"})

        # Group by speaker turns
        speaker_segments = []
        for speaker, group in groupby(words, key=lambda w: w["speaker"]):
            group_list = list(group)
            text = " ".join(w["punctuated_word"] for w in group_list)
            speaker_segments.append(
                {
                    "speaker": speaker,
                    "start": group_list[0]["start"],
                    "end": group_list[-1]["end"],
                    "text": text,
                }
            )

        # Send one Bedrock prompt with all segments
        prompt = f"""
<!-- SYSTEM -->
<system>
You are an expert in detecting advertisement segments within podcast transcripts. Your task is to classify each segment as "ad" or "content" based on textual indicators.
</system>

<!-- CONTEXT -->
<context>
Domain: Podcasts  
Objective: Identify which speaker segments are advertisements versus regular content.  
Output: JSON array of objects, each containing the segment index and classification.
</context>

<!-- INPUT -->
<input>
<segments><![CDATA[
{json.dumps([{"index": i, "text": s["text"]} for i, s in enumerate(speaker_segments)], indent=2)}
]]></segments>
</input>

<!-- INSTRUCTIONS -->
<instructions>
1. Analyze each segment's text and determine if it is an advertisement ("ad") or regular content ("content").  
2. Indicators of "ad" include: promotional language, discount codes, sponsor mentions, direct product/service pitches.  
3. Indicators of "content" include: discussion of main topics, host commentary unrelated to promotions, educational material.  
4. Classify strictly based on textual content, not assumptions.  
5. Return results in the exact JSON format specified below, preserving the original order of segments.
</instructions>

<!-- OUTPUT FORMAT -->
<output_format>
[
  {{ "index": 0, "label": "content" }},
  {{ "index": 1, "label": "ad" }}
  /* repeat for each segment */
]
</output_format>

<!-- NOTES -->
<notes>
• Return **only** the JSON array—no extra text.  
• Do not infer ads unless explicit indicators exist.  
• Maintain the input order in your output.
</notes>
"""

        result_text = bedrock.invoke_model(prompt)

        try:
            label_results = json.loads(result_text)
        except Exception as e:
            context.log.warning(f"LLM output could not be parsed: {e}")
            return dg.MaterializeResult(metadata={"status": "error", "reason": "parse_error"})

        ad_indexes = {entry["index"] for entry in label_results if entry["label"] == "ad"}
        context.log.info(f"Identified ad segments: {sorted(ad_indexes)}")

        cleaned_transcript = " ".join(seg["text"] for i, seg in enumerate(speaker_segments) if i not in ad_indexes)

        # Replace full transcript text
        transcript_data["results"]["results"]["channels"][0]["alternatives"][0]["transcript"] = cleaned_transcript

        client.put_object(
            Bucket=_podcast_bucket("silver"),
            Key=cleaned_key,
            Body=json.dumps(transcript_data, indent=2),
            ContentType="application/json",
        )

        return dg.MaterializeResult(
            metadata={
                "cleaned_transcript_key": cleaned_key,
                "total_segments": len(speaker_segments),
                "ads_removed": len(ad_indexes),
                "cleaned_word_count": len(cleaned_transcript.split()),
            }
        )

    @dg.asset(
        name=f"{feed_definition.name}_summary",
        partitions_def=partition_def,
        deps=[cleaned_transcript_asset],
        compute_kind="bedrock",
        group_name="podcast_ingestion",
    )
    def summary_asset(
        context: dg.AssetExecutionContext,
        s3: S3Resource,
        bedrock: BedrockResource,
    ) -> dg.MaterializeResult:
        """Generate summary using AWS Bedrock.

        Args:
            context: Dagster execution context.
            s3: S3 resource for storage.
            bedrock: Bedrock resource for LLM.

        Returns:
            Materialization result with summary metadata.
        """
        import json
        from datetime import datetime

        client = s3.get_client()

        transcript_key = get_s3_key(
            "silver",
            "podcasts",
            feed_definition.name,
            context.partition_key,
            "cleaned_transcript.json",
        )

        summary_key = get_s3_key(
            "gold",
            "podcasts",
            feed_definition.name,
            context.partition_key,
            "summary.json",
        )

        context.log.info("Loading transcript for summarization")

        response = client.get_object(Bucket=_podcast_bucket("silver"), Key=transcript_key)
        transcript_data = json.loads(response["Body"].read())
        transcript_text = ""
        if transcript_data["results"].get("results", {}).get("channels", []):
            transcript_text = transcript_data["results"]["results"]["channels"][0]["alternatives"][0]["transcript"]
        if not transcript_text:
            context.log.warning("No transcript text found, skipping summary")
            return dg.MaterializeResult(metadata={"status": "skipped", "reason": "no_transcript"})
        context.log.info("Generating summary with Bedrock")
        prompt = f"""
<!-- SYSTEM -->
<system>
You are a medical podcast summarizer. Your role is to extract and organize key information from medical podcast transcripts into a clear, structured format.
</system>

<!-- CONTEXT -->
<context>
Domain: Medical Podcasts  
Objective: Produce a comprehensive, structured summary suitable for healthcare professionals.  
Output: JSON object containing key topics, insights, expert opinions, practical takeaways, and warnings.
</context>

<!-- INPUT -->
<input>
<transcript><![CDATA[
{transcript_text}
]]></transcript>
</input>

<!-- INSTRUCTIONS -->
<instructions>
1. Read the transcript carefully, identifying the main topics discussed.  
2. Extract key medical insights, findings, or research results.  
3. Capture expert opinions, clearly attributing them when possible.  
4. Provide practical, actionable takeaways for healthcare professionals.  
5. Note any warnings, disclaimers, or cautions mentioned in the podcast.  
6. Output the summary in the JSON structure specified below.
</instructions>

<!-- OUTPUT FORMAT -->
<output_format>
{{
  "main_topics": ["<string>", "..."],
  "key_insights": ["<string>", "..."],
  "expert_opinions": ["<string>", "..."],
  "practical_takeaways": ["<string>", "..."],
  "warnings": ["<string>", "..."]
}}
</output_format>

<!-- NOTES -->
<notes>
• Ensure accuracy; do not add information not present in the transcript.  
• Use concise, professional language appropriate for medical contexts.  
• Return only the JSON object—no extra commentary.
</notes>
"""

        summary_text = bedrock.invoke_model(prompt)

        try:
            parsed_summary = parse_bedrock_json_response(summary_text)
        except ValueError as e:
            context.log.warning(f"Summary parsing failed: {e}")
            parsed_summary = {
                "error": str(e),
                "raw_summary": summary_text,
            }
        summary_data = {
            "podcast": feed_definition.name,
            "episode_id": context.partition_key,
            "summary_timestamp": datetime.utcnow().isoformat(),
            "model": "claude-sonnet-4",
            "summary": parsed_summary,
            "transcript_word_count": len(transcript_text.split()),
        }

        client.put_object(
            Bucket=_podcast_bucket("gold"),
            Key=summary_key,
            Body=json.dumps(summary_data, indent=2),
            ContentType="application/json",
        )

        return dg.MaterializeResult(
            metadata={
                "summary_key": summary_key,
                "model": "claude-sonnet-4",
                "transcript_words": len(transcript_text.split()),
            },
        )

    @dg.asset(
        name=f"{feed_definition.name}_bias_assessment",
        partitions_def=partition_def,
        deps=[cleaned_transcript_asset, summary_asset],
        compute_kind="bedrock",
        group_name="podcast_ingestion",
    )
    def bias_assessment_asset(
        context: dg.AssetExecutionContext,
        s3: S3Resource,
        bedrock: BedrockResource,
    ) -> dg.MaterializeResult:
        """Generate summary using AWS Bedrock.

        Args:
            context: Dagster execution context.
            s3: S3 resource for storage.
            bedrock: Bedrock resource for LLM.

        Returns:
            Materialization result with summary metadata.
        """
        import json
        from datetime import datetime

        client = s3.get_client()

        transcript_key = get_s3_key(
            "silver",
            "podcasts",
            feed_definition.name,
            context.partition_key,
            "cleaned_transcript.json",
        )

        summary_key = get_s3_key(
            "gold",
            "podcasts",
            feed_definition.name,
            context.partition_key,
            "summary.json",
        )

        bias_assessment_key = get_s3_key(
            "gold",
            "podcasts",
            feed_definition.name,
            context.partition_key,
            "bias_assessment.json",
        )

        context.log.info("Loading transcript for bias assessment")

        response = client.get_object(Bucket=_podcast_bucket("silver"), Key=transcript_key)
        transcript_data = json.loads(response["Body"].read())
        transcript_text = ""
        if transcript_data["results"].get("results", {}).get("channels", []):
            transcript_text = transcript_data["results"]["results"]["channels"][0]["alternatives"][0]["transcript"]

        if not transcript_text:
            context.log.warning("No transcript text found, skipping bias assessment")
            return dg.MaterializeResult(metadata={"status": "skipped", "reason": "no_transcript"})

        context.log.info("Loading summary for bias assessment")

        response = client.get_object(Bucket=_podcast_bucket("gold"), Key=summary_key)
        summary_data = json.loads(response["Body"].read()).get("summary", {}).get("podcast_summary", {})
        if not summary_data:
            context.log.warning("No summary data found, skipping bias assessment")
            return dg.MaterializeResult(metadata={"status": "skipped", "reason": "no_summary"})

        context.log.info("Generating bias assessment with Bedrock")

        prompt = make_bias_analysis_prompt(transcript_text, summary_data)

        bias_assessment_text = bedrock.invoke_model(prompt)

        try:
            parsed_bias_assessment = parse_bedrock_json_response(bias_assessment_text)
        except ValueError as e:
            context.log.warning(f"Bias assessment parsing failed: {e}")
            parsed_bias_assessment = {
                "error": str(e),
                "raw_summary": bias_assessment_text,
            }
        bias_assessment_data = {
            "podcast": feed_definition.name,
            "episode_id": context.partition_key,
            "summary_timestamp": datetime.utcnow().isoformat(),
            "model": "claude-sonnet-4",
            "bias_assessment": parsed_bias_assessment,
            "transcript_word_count": len(transcript_text.split()),
        }

        client.put_object(
            Bucket=_podcast_bucket("gold"),
            Key=bias_assessment_key,
            Body=json.dumps(bias_assessment_data, indent=2),
            ContentType="application/json",
        )

        return dg.MaterializeResult(
            metadata={
                "bias_assessment_key": bias_assessment_key,
                "model": "claude-sonnet-4",
                "transcript_words": len(transcript_text.split()),
            },
        )

    job_name = f"{feed_definition.name}_ingestion_job"

    ingestion_job = dg.define_asset_job(
        name=job_name,
        selection=dg.AssetSelection.assets(
            raw_audio_asset,
            processed_audio_asset,
            transcript_asset,
            cleaned_transcript_asset,
            summary_asset,
            bias_assessment_asset,
        ),
        partitions_def=partition_def,
    )

    @dg.asset_check(
        asset=transcript_asset,
        name=f"{feed_definition.name}_transcript_quality_check",
        description="Validates transcript quality and accuracy metrics",
    )
    def transcript_quality_check(
        context: dg.AssetCheckExecutionContext,
        s3: S3Resource,
    ) -> dg.AssetCheckResult:
        """Check transcript quality metrics."""
        import json

        client = s3.get_client()
        transcript_key = get_s3_key(
            "silver",
            "podcasts",
            feed_definition.name,
            context.get_step_execution_context().partition_key,
            "transcript.json",
        )

        response = client.get_object(Bucket=_podcast_bucket("silver"), Key=transcript_key)
        transcript_data = json.loads(response["Body"].read())

        # Extract quality metrics from Deepgram response
        results = transcript_data.get("results", {}).get("results", {})
        channels = results.get("channels", [])

        if not channels:
            return dg.AssetCheckResult(passed=False, description="No transcript channels found")

        alternatives = channels[0].get("alternatives", [])
        if not alternatives:
            return dg.AssetCheckResult(passed=False, description="No transcript alternatives found")

        # Check confidence score
        confidence = alternatives[0].get("confidence", 0.0)

        # Determine if check passes
        confidence_check = confidence >= 0.9

        return dg.AssetCheckResult(
            passed=confidence_check,
            description="Transcript quality check: confidence",
            metadata={
                "confidence": confidence,
            },
        )

    @dg.sensor(
        name=f"{feed_definition.name}_rss_sensor",
        minimum_interval_seconds=3600,
        default_status=dg.DefaultSensorStatus.RUNNING,
        job=ingestion_job,
    )
    def rss_sensor(context: dg.SensorEvaluationContext):
        """Monitor RSS feed for new episodes.

        Args:
            context: Sensor evaluation context.

        Returns:
            Sensor result with run requests.
        """
        etag = context.cursor
        context.log.info(f"Checking RSS feed with etag: {etag}")

        feed = feedparser.parse(feed_definition.url, etag=etag)

        if not feed.entries:
            context.log.info("No new entries found")
            return dg.SensorResult(cursor=str(feed.etag) if hasattr(feed, "etag") else etag)

        num_entries = len(feed.entries)
        context.log.info(f"Found {num_entries} entries")

        if num_entries > feed_definition.max_backfill_size:
            entries = feed.entries[: feed_definition.max_backfill_size]
        else:
            entries = feed.entries

        partition_requests = []
        run_requests = []

        for entry in entries:
            episode_id = sanitize_episode_id(str(entry.id) if hasattr(entry, "id") else "unknown")
            audio_url = get_audio_url_from_entry(entry)

            if not audio_url:
                context.log.warning(f"No audio URL found for entry {entry.id}")
                continue

            partition_requests.append(episode_id)

            run_requests.append(
                dg.RunRequest(
                    partition_key=episode_id,
                    run_config=dg.RunConfig(
                        ops={
                            raw_audio_asset.key.to_user_string().replace("/", "__"): AudioConfig(
                                audio_url=audio_url,
                                episode_title=str(entry.title) if hasattr(entry, "title") else "unknown",
                                published_date=str(entry.published) if hasattr(entry, "published") else "unknown",
                            ),
                        },
                    ),
                ),
            )

        return dg.SensorResult(
            run_requests=run_requests,
            dynamic_partitions_requests=[
                partition_def.build_add_request(partition_requests),
            ],
            cursor=str(feed.etag) if hasattr(feed, "etag") else None,
        )

    return dg.Definitions(
        assets=[
            raw_audio_asset,
            processed_audio_asset,
            transcript_asset,
            cleaned_transcript_asset,
            summary_asset,
            bias_assessment_asset,
        ],
        asset_checks=[transcript_quality_check],
        jobs=[ingestion_job],
        sensors=[rss_sensor],
    )
