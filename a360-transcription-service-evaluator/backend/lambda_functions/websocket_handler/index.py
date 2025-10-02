"""
WebSocket handler for real-time audio recording.

This Lambda function handles WebSocket connections for real-time audio streaming
from voice actors during script recording sessions.
"""

import json
import os
import boto3
import base64
from typing import Dict, Any
from datetime import datetime, timezone
import uuid

# AWS Lambda PowerTools
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext

# Initialize PowerTools
tracer = Tracer(service="voice-actor-websocket")
logger = Logger(service="voice-actor-websocket")
metrics = Metrics(namespace="VoiceActorPlatform", service="voice-actor-websocket")

# Initialize AWS clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

# Environment variables
RECORDINGS_BUCKET = os.environ.get('RECORDINGS_BUCKET')
CONNECTIONS_TABLE = os.environ.get('CONNECTIONS_TABLE')

@tracer.capture_lambda_handler
@logger.inject_lambda_context
@metrics.log_metrics
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Main WebSocket handler for audio streaming."""
    try:
        route_key = event.get('requestContext', {}).get('routeKey', '')
        connection_id = event.get('requestContext', {}).get('connectionId', '')
        
        logger.info(f"WebSocket event: {route_key} for connection: {connection_id}")
        metrics.add_metric(name="WebSocketRequest", unit=MetricUnit.Count, value=1)
        metrics.add_metadata(key="route", value=route_key)
        
        if route_key == '$connect':
            return handle_connect(connection_id, event)
        elif route_key == '$disconnect':
            return handle_disconnect(connection_id)
        elif route_key == 'audio_chunk':
            return handle_audio_chunk(connection_id, event)
        elif route_key == 'start_recording':
            return handle_start_recording(connection_id, event)
        elif route_key == 'stop_recording':
            return handle_stop_recording(connection_id, event)
        else:
            logger.warning(f"Unknown route: {route_key}")
            metrics.add_metric(name="UnknownRoute", unit=MetricUnit.Count, value=1)
            return {'statusCode': 400}
            
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}", exc_info=True)
        metrics.add_metric(name="WebSocketError", unit=MetricUnit.Count, value=1)
        return {'statusCode': 500}

@tracer.capture_method
def handle_connect(connection_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle new WebSocket connection."""
    try:
        # Store connection information
        connections_table = dynamodb.Table(CONNECTIONS_TABLE)
        connections_table.put_item(Item={
            'connection_id': connection_id,
            'connected_at': datetime.now(timezone.utc).isoformat(),
            'status': 'connected'
        })
        
        logger.info(f"Connection established: {connection_id}")
        metrics.add_metric(name="ConnectionEstablished", unit=MetricUnit.Count, value=1)
        return {'statusCode': 200}
        
    except Exception as e:
        logger.error(f"Connection error: {str(e)}")
        metrics.add_metric(name="ConnectionError", unit=MetricUnit.Count, value=1)
        return {'statusCode': 500}

@tracer.capture_method
def handle_disconnect(connection_id: str) -> Dict[str, Any]:
    """Handle WebSocket disconnection."""
    try:
        # Remove connection from table
        connections_table = dynamodb.Table(CONNECTIONS_TABLE)
        connections_table.delete_item(Key={'connection_id': connection_id})
        
        logger.info(f"Connection closed: {connection_id}")
        metrics.add_metric(name="ConnectionClosed", unit=MetricUnit.Count, value=1)
        return {'statusCode': 200}
        
    except Exception as e:
        logger.error(f"Disconnect error: {str(e)}")
        return {'statusCode': 500}

@tracer.capture_method
def handle_start_recording(connection_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle start recording request."""
    try:
        body = json.loads(event.get('body', '{}'))
        script_id = body.get('script_id')
        user_id = body.get('user_id')
        
        # Generate recording session ID
        recording_id = str(uuid.uuid4())
        
        # Store recording session info
        connections_table = dynamodb.Table(CONNECTIONS_TABLE)
        connections_table.update_item(
            Key={'connection_id': connection_id},
            UpdateExpression='SET recording_id = :recording_id, script_id = :script_id, user_id = :user_id, recording_status = :status',
            ExpressionAttributeValues={
                ':recording_id': recording_id,
                ':script_id': script_id,
                ':user_id': user_id,
                ':status': 'recording'
            }
        )
        
        # Send confirmation back to client
        send_to_connection(connection_id, {
            'action': 'recording_started',
            'recording_id': recording_id,
            'status': 'ready'
        })
        
        logger.info(f"Recording started: {recording_id} for connection: {connection_id}")
        metrics.add_metric(name="RecordingStarted", unit=MetricUnit.Count, value=1)
        return {'statusCode': 200}
        
    except Exception as e:
        logger.error(f"Start recording error: {str(e)}")
        return {'statusCode': 500}

@tracer.capture_method
def handle_audio_chunk(connection_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle incoming audio chunk."""
    try:
        body = json.loads(event.get('body', '{}'))
        audio_data = body.get('audio_data')  # Base64 encoded audio
        chunk_id = body.get('chunk_id', 0)
        
        # Get recording session info
        connections_table = dynamodb.Table(CONNECTIONS_TABLE)
        response = connections_table.get_item(Key={'connection_id': connection_id})
        
        if 'Item' not in response:
            logger.warning(f"No session found for connection: {connection_id}")
            return {'statusCode': 404}
        
        session = response['Item']
        recording_id = session.get('recording_id')
        user_id = session.get('user_id')
        script_id = session.get('script_id')
        
        if not recording_id:
            logger.warning(f"No active recording for connection: {connection_id}")
            return {'statusCode': 400}
        
        # Decode and store audio chunk in S3
        audio_bytes = base64.b64decode(audio_data)
        s3_key = f"recordings/{user_id}/{script_id}/{recording_id}/chunks/chunk_{chunk_id:06d}.wav"
        
        s3_client.put_object(
            Bucket=RECORDINGS_BUCKET,
            Key=s3_key,
            Body=audio_bytes,
            ContentType='audio/wav'
        )
        
        # Send acknowledgment back to client
        send_to_connection(connection_id, {
            'action': 'chunk_received',
            'chunk_id': chunk_id,
            'status': 'stored'
        })
        
        logger.info(f"Audio chunk {chunk_id} stored for recording: {recording_id}")
        metrics.add_metric(name="AudioChunkProcessed", unit=MetricUnit.Count, value=1)
        return {'statusCode': 200}
        
    except Exception as e:
        logger.error(f"Audio chunk error: {str(e)}")
        return {'statusCode': 500}

@tracer.capture_method
def handle_stop_recording(connection_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle stop recording request."""
    try:
        # Get recording session info
        connections_table = dynamodb.Table(CONNECTIONS_TABLE)
        response = connections_table.get_item(Key={'connection_id': connection_id})
        
        if 'Item' not in response:
            return {'statusCode': 404}
        
        session = response['Item']
        recording_id = session.get('recording_id')
        user_id = session.get('user_id')
        script_id = session.get('script_id')
        
        # Update session status
        connections_table.update_item(
            Key={'connection_id': connection_id},
            UpdateExpression='SET recording_status = :status, stopped_at = :stopped_at',
            ExpressionAttributeValues={
                ':status': 'completed',
                ':stopped_at': datetime.now(timezone.utc).isoformat()
            }
        )
        
        # TODO: Combine audio chunks into final recording file
        # This would typically involve:
        # 1. List all chunks from S3
        # 2. Download and concatenate them
        # 3. Upload final recording
        # 4. Clean up chunk files
        
        # Send completion confirmation
        send_to_connection(connection_id, {
            'action': 'recording_completed',
            'recording_id': recording_id,
            'status': 'processing',
            'message': 'Recording completed successfully. Processing audio file...'
        })
        
        logger.info(f"Recording stopped: {recording_id}")
        metrics.add_metric(name="RecordingStopped", unit=MetricUnit.Count, value=1)
        return {'statusCode': 200}
        
    except Exception as e:
        logger.error(f"Stop recording error: {str(e)}")
        return {'statusCode': 500}

@tracer.capture_method
def send_to_connection(connection_id: str, message: Dict[str, Any]) -> None:
    """Send message to WebSocket connection."""
    try:
        # Initialize API Gateway Management API client with endpoint URL
        endpoint_url = os.environ.get('WEBSOCKET_API_ENDPOINT')
        if endpoint_url:
            apigateway_client = boto3.client('apigatewaymanagementapi', endpoint_url=endpoint_url)
            
            apigateway_client.post_to_connection(
                ConnectionId=connection_id,
                Data=json.dumps(message).encode('utf-8')
            )
        else:
            logger.warning("WebSocket API endpoint URL not configured")
            
    except Exception as e:
        if 'GoneException' in str(type(e)):
            logger.info(f"Connection {connection_id} is no longer available")
            # Clean up connection from database
            try:
                connections_table = dynamodb.Table(CONNECTIONS_TABLE)
                connections_table.delete_item(Key={'connection_id': connection_id})
            except Exception as cleanup_error:
                logger.error(f"Failed to cleanup connection: {cleanup_error}")
        else:
            logger.error(f"Failed to send message to {connection_id}: {str(e)}")