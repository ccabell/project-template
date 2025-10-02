"""Dagster repository for a360 data platform pipelines.
This module defines the main repository containing all jobs, schedules,
sensors, and resources for the data platform.
"""

import logging

from dagster import Definitions

from defs.aws.resources import get_aws_resources
from defs.consultation_pipeline.pipeline_factory import consultation_pipeline_factory, ConsultationDefinition

logger = logging.getLogger(__name__)

try:
    from defs.podcast.pipeline_factory import podcast_pipeline_factory, RSSFeedDefinition
    from defs.podcast.resources import get_podcast_resources

    PODCAST_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Podcast pipeline not available (missing dependencies): {e}")
    PODCAST_AVAILABLE = False

try:
    import defs.consultation_pipeline.resources

    CONSULTATION_RESOURCES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Consultation pipeline resources not available: {e}")
    CONSULTATION_RESOURCES_AVAILABLE = False


def create_definitions() -> Definitions:
    """Create Dagster definitions for the repository.
    Returns:
        Definitions object containing all repository components.
    """
    # Health check for potential issues
    logger.info("Performing repository health check...")

    # Check for missing environment variables that might cause issues
    missing_env_vars = []
    optional_env_vars = ["LAKEFS_ENDPOINT", "LAKEFS_ACCESS_KEY_ID", "LAKEFS_SECRET_ACCESS_KEY"]

    import os

    for var in optional_env_vars:
        if var not in os.environ:
            missing_env_vars.append(var)

    if missing_env_vars and PODCAST_AVAILABLE:
        logger.warning(f"Optional environment variables missing for podcast pipeline: {missing_env_vars}")
        logger.warning("Podcast pipeline resources may be limited")

    # Check AWS resources availability
    try:
        aws_resources = get_aws_resources()
        logger.info(f"AWS resources available: {list(aws_resources.keys())}")
    except Exception as e:
        logger.error(f"AWS resources failed: {e}")
        raise

    podcast_feeds = [
        {
            "name": "get_real_with_ravichadrans",
            "url": "https://anchor.fm/s/dcc0f33c/podcast/rss",
            "max_backfill_size": 3,
        },
        {
            "name": "a_plastic_surgeon_journal",
            "url": "https://anchor.fm/s/400acf7c/podcast/rss",
            "max_backfill_size": 3,
        },
        {
            "name": "beauty_and_the_surgeon",
            "url": "https://beautyandthesurgeon.libsyn.com/rss",
            "max_backfill_size": 3,
        },
        {
            "name": "beautifully_healthy",
            "url": "https://anchor.fm/s/101f0fbc/podcast/rss",
            "max_backfill_size": 3,
        },
        {
            "name": "business_aesthetics_podcast",
            "url": "https://businessofaestheticsorg.libsyn.com/rss",
            "max_backfill_size": 3,
        },
    ]

    consultation_tenants = [
        {
            "tenant_id": "aesthetics360_demo",
            "tenant_name": "aesthetics360_demo",
            "environment": "dev",
            "max_backfill_size": 5,
        },
    ]

    definitions_list = []

    if PODCAST_AVAILABLE:
        for feed in podcast_feeds:
            feed_defs = podcast_pipeline_factory(RSSFeedDefinition(**feed))
            definitions_list.append(feed_defs)

    for tenant in consultation_tenants:
        consultation_defs = consultation_pipeline_factory(ConsultationDefinition(**tenant))
        definitions_list.append(consultation_defs)

    aws_resources = get_aws_resources()
    all_resource_sets = [aws_resources]

    if PODCAST_AVAILABLE:
        try:
            podcast_resources = get_podcast_resources()
            if podcast_resources:  # Only add if not empty
                all_resource_sets.append(podcast_resources)
        except Exception as e:
            logger.error(f"Failed to get podcast resources: {e}")
            podcast_resources = {}
    else:
        podcast_resources = {}

    # Note: Skip consultation_resources as they duplicate AWS resources
    # The consultation pipeline will use the AWS resources directly
    consultation_resources = {}

    all_keys = []
    for resource_set in all_resource_sets:
        all_keys.extend(resource_set.keys())

    duplicate_keys = {key for key in all_keys if all_keys.count(key) > 1}
    if duplicate_keys:
        raise ValueError(f"Resource key conflicts detected: {duplicate_keys}")

    all_resources = {**aws_resources, **podcast_resources, **consultation_resources}

    return Definitions.merge(*definitions_list).with_resources(all_resources)


defs = create_definitions()
