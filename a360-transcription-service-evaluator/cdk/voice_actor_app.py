#!/usr/bin/env python3
"""
CDK App for Voice Actor Transcription Platform.

This app deploys the complete voice actor platform with Lambda-based architecture
for better reliability and easier debugging.
"""

import aws_cdk as cdk
from stacks.voice_actor_stack import VoiceActorStack

app = cdk.App()

# Deploy the voice actor stack
VoiceActorStack(
    app, 
    "VoiceActorStack",
    env=cdk.Environment(
        account=app.node.try_get_context("account") or "471112502741",
        region=app.node.try_get_context("region") or "us-east-1"
    ),
    description="Voice Actor Transcription Platform with Lambda Architecture"
)

app.synth()