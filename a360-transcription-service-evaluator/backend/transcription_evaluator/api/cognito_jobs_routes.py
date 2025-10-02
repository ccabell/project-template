"""Job queue management routes with Cognito authentication.

This module provides authenticated endpoints for managing ground truth generation jobs
and tracking their status with proper user access controls.
"""

import logging
import os
from typing import Any, Dict, List, Optional
from datetime import datetime

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..aws.authorizers import CognitoUser, require_cognito_auth, require_admin_access
from ..config.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["jobs"])


class JobStatusResponse(BaseModel):
    """Response model for job status."""
    
    job_id: str = Field(..., description="Job identifier")
    user_id: str = Field(..., description="User who created the job")
    status: str = Field(..., description="Job status")
    created_at: str = Field(..., description="Job creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")
    result_path: Optional[str] = Field(None, description="Path to job result")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional job metadata")
    script_title: Optional[str] = Field(None, description="Script title for completed jobs")


class UserJobsResponse(BaseModel):
    """Response model for user jobs list."""
    
    user_id: str = Field(..., description="User identifier")
    jobs: List[JobStatusResponse] = Field(..., description="List of user jobs")
    total_count: int = Field(..., description="Total number of jobs")


class AllJobsResponse(BaseModel):
    """Response model for all jobs (admin only)."""
    
    jobs: List[JobStatusResponse] = Field(..., description="List of all jobs")
    total_count: int = Field(..., description="Total number of jobs")


# Initialize DynamoDB client
def get_dynamodb_client():
    """Get DynamoDB client with proper configuration."""
    try:
        return boto3.client("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))
    except Exception as e:
        logger.error(f"Failed to create DynamoDB client: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database configuration error"
        )


def get_jobs_table():
    """Get jobs table name from environment."""
    table_name = os.getenv("JOBS_TABLE")
    if not table_name:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Jobs table not configured"
        )
    return table_name


def dynamodb_item_to_job(item: Dict[str, Any]) -> JobStatusResponse:
    """Convert DynamoDB item to JobStatusResponse."""
    return JobStatusResponse(
        job_id=item.get("job_id", {}).get("S", ""),
        user_id=item.get("user_id", {}).get("S", ""),
        status=item.get("status", {}).get("S", "unknown"),
        created_at=item.get("created_at", {}).get("S", ""),
        updated_at=item.get("updated_at", {}).get("S"),
        result_path=item.get("result_path", {}).get("S"),
        error_message=item.get("error_message", {}).get("S"),
        metadata={
            k: v.get("S", "") for k, v in item.get("metadata", {}).get("M", {}).items()
        } if "metadata" in item else None,
        script_title=item.get("script_title", {}).get("S")
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    current_user: CognitoUser = Depends(require_cognito_auth)
) -> JobStatusResponse:
    """Get status of a specific job.
    
    Users can only view their own jobs unless they have admin access.
    
    Args:
        job_id: Job identifier
        current_user: Authenticated Cognito user
        
    Returns:
        JobStatusResponse with job details
        
    Raises:
        HTTPException: If job not found or user lacks access
    """
    try:
        dynamodb_client = get_dynamodb_client()
        table_name = get_jobs_table()
        
        response = dynamodb_client.get_item(
            TableName=table_name,
            Key={
                "job_id": {"S": job_id}
            }
        )
        
        if "Item" not in response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        job = dynamodb_item_to_job(response["Item"])
        
        # Check access permissions - users can only see their own jobs unless admin
        if job.user_id != current_user.email and "admin" not in current_user.groups:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied - you can only view your own jobs"
            )
        
        logger.info(f"Job status retrieved for {job_id} by user {current_user.email}")
        
        return job
        
    except HTTPException:
        raise
    except ClientError as e:
        logger.error(f"DynamoDB error retrieving job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve job from database"
        )
    except Exception as e:
        logger.error(f"Error retrieving job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve job: {str(e)}"
        )


@router.get("/users/{user_id}/jobs", response_model=UserJobsResponse)
async def get_user_jobs(
    user_id: str,
    current_user: CognitoUser = Depends(require_cognito_auth),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of jobs to return"),
    status_filter: Optional[str] = Query(None, description="Filter by job status")
) -> UserJobsResponse:
    """Get all jobs for a specific user.
    
    Users can only view their own jobs unless they have admin access.
    
    Args:
        user_id: User identifier (email)
        current_user: Authenticated Cognito user
        limit: Maximum number of jobs to return
        status_filter: Optional status filter
        
    Returns:
        UserJobsResponse with user's jobs
        
    Raises:
        HTTPException: If user lacks access
    """
    try:
        # Check access permissions - users can only see their own jobs unless admin
        if user_id != current_user.email and "admin" not in current_user.groups:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied - you can only view your own jobs"
            )
        
        dynamodb_client = get_dynamodb_client()
        table_name = get_jobs_table()
        
        # Query using GSI on user_id
        query_params = {
            "TableName": table_name,
            "IndexName": "UserJobsIndex",  # Assumes GSI exists
            "KeyConditionExpression": "user_id = :user_id",
            "ExpressionAttributeValues": {
                ":user_id": {"S": user_id}
            },
            "Limit": limit,
            "ScanIndexForward": False  # Most recent first
        }
        
        # Add status filter if provided
        if status_filter:
            query_params["FilterExpression"] = "#status = :status"
            query_params["ExpressionAttributeNames"] = {"#status": "status"}
            query_params["ExpressionAttributeValues"][":status"] = {"S": status_filter}
        
        response = dynamodb_client.query(**query_params)
        
        jobs = []
        for item in response.get("Items", []):
            jobs.append(dynamodb_item_to_job(item))
        
        logger.info(f"Retrieved {len(jobs)} jobs for user {user_id} by {current_user.email}")
        
        return UserJobsResponse(
            user_id=user_id,
            jobs=jobs,
            total_count=len(jobs)
        )
        
    except HTTPException:
        raise
    except ClientError as e:
        logger.error(f"DynamoDB error retrieving jobs for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve jobs from database"
        )
    except Exception as e:
        logger.error(f"Error retrieving jobs for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve jobs: {str(e)}"
        )


@router.get("/jobs", response_model=AllJobsResponse)
async def get_all_jobs(
    current_user: CognitoUser = Depends(require_cognito_auth),
    admin_access: bool = Depends(require_admin_access),
    limit: int = Query(default=100, ge=1, le=500, description="Maximum number of jobs to return"),
    status_filter: Optional[str] = Query(None, description="Filter by job status")
) -> AllJobsResponse:
    """Get all jobs across all users.
    
    Requires admin access to view all jobs.
    
    Args:
        current_user: Authenticated Cognito user
        admin_access: Admin access verification
        limit: Maximum number of jobs to return
        status_filter: Optional status filter
        
    Returns:
        AllJobsResponse with all jobs
        
    Raises:
        HTTPException: If user lacks admin access
    """
    try:
        dynamodb_client = get_dynamodb_client()
        table_name = get_jobs_table()
        
        scan_params = {
            "TableName": table_name,
            "Limit": limit
        }
        
        # Add status filter if provided
        if status_filter:
            scan_params["FilterExpression"] = "#status = :status"
            scan_params["ExpressionAttributeNames"] = {"#status": "status"}
            scan_params["ExpressionAttributeValues"] = {":status": {"S": status_filter}}
        
        response = dynamodb_client.scan(**scan_params)
        
        jobs = []
        for item in response.get("Items", []):
            jobs.append(dynamodb_item_to_job(item))
        
        # Sort by creation date (most recent first)
        jobs.sort(key=lambda x: x.created_at, reverse=True)
        
        logger.info(f"Retrieved {len(jobs)} total jobs by admin {current_user.email}")
        
        return AllJobsResponse(
            jobs=jobs,
            total_count=len(jobs)
        )
        
    except HTTPException:
        raise
    except ClientError as e:
        logger.error(f"DynamoDB error retrieving all jobs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve jobs from database"
        )
    except Exception as e:
        logger.error(f"Error retrieving all jobs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve jobs: {str(e)}"
        )


@router.delete("/jobs/{job_id}")
async def delete_job(
    job_id: str,
    current_user: CognitoUser = Depends(require_cognito_auth)
) -> Dict[str, Any]:
    """Delete a specific job.
    
    Users can only delete their own jobs unless they have admin access.
    
    Args:
        job_id: Job identifier
        current_user: Authenticated Cognito user
        
    Returns:
        Success response
        
    Raises:
        HTTPException: If job not found or user lacks access
    """
    try:
        dynamodb_client = get_dynamodb_client()
        table_name = get_jobs_table()
        
        # First, get the job to check ownership
        response = dynamodb_client.get_item(
            TableName=table_name,
            Key={
                "job_id": {"S": job_id}
            }
        )
        
        if "Item" not in response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        job = dynamodb_item_to_job(response["Item"])
        
        # Check access permissions - users can only delete their own jobs unless admin
        if job.user_id != current_user.email and "admin" not in current_user.groups:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied - you can only delete your own jobs"
            )
        
        # Delete the job
        dynamodb_client.delete_item(
            TableName=table_name,
            Key={
                "job_id": {"S": job_id}
            }
        )
        
        logger.info(f"Job {job_id} deleted by user {current_user.email}")
        
        return {
            "success": True,
            "message": f"Job {job_id} deleted successfully"
        }
        
    except HTTPException:
        raise
    except ClientError as e:
        logger.error(f"DynamoDB error deleting job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete job from database"
        )
    except Exception as e:
        logger.error(f"Error deleting job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete job: {str(e)}"
        )