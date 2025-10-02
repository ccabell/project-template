"""Brand and terms management routes with Cognito authentication.

This module provides authenticated endpoints for managing medical brands and terms
used in ground truth generation and transcription evaluation.
"""

import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..aws.authorizers import CognitoUser, require_cognito_auth, require_admin_access
from ..config.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["brands-terms"])


class BrandRequest(BaseModel):
    """Request model for brand operations."""
    
    name: str = Field(..., description="Brand name", min_length=1, max_length=100)
    vertical: Optional[str] = Field(None, description="Medical vertical category")
    difficulty: Optional[str] = Field("intermediate", description="Difficulty level (easy, intermediate, hard)")
    category: Optional[str] = Field(None, description="Brand category")
    pronunciation: Optional[str] = Field(None, description="Pronunciation guide")


class TermRequest(BaseModel):
    """Request model for term operations."""
    
    name: str = Field(..., description="Medical term", min_length=1, max_length=200)
    vertical: Optional[str] = Field(None, description="Medical vertical category")
    difficulty: Optional[str] = Field("intermediate", description="Difficulty level (easy, intermediate, hard)")
    category: Optional[str] = Field(None, description="Term category")
    pronunciation: Optional[str] = Field(None, description="Pronunciation guide")


class BrandsResponse(BaseModel):
    """Response model for brands list."""
    
    brands: List[str] = Field(..., description="List of brand names")
    total_count: int = Field(..., description="Total number of brands")


class TermsResponse(BaseModel):
    """Response model for terms list."""
    
    terms: List[str] = Field(..., description="List of medical terms")
    total_count: int = Field(..., description="Total number of terms")


class OperationResponse(BaseModel):
    """Response model for operations."""
    
    success: bool = Field(..., description="Operation success status")
    message: str = Field(..., description="Operation message")


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


def get_medical_brands_table():
    """Get medical brands table name from environment."""
    table_name = os.getenv("MEDICAL_BRANDS_TABLE_NAME")
    if not table_name:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Medical brands table not configured"
        )
    return table_name


def get_medical_terms_table():
    """Get medical terms table name from environment."""
    table_name = os.getenv("MEDICAL_TERMS_TABLE_NAME")
    if not table_name:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Medical terms table not configured"
        )
    return table_name


@router.get("/brands", response_model=BrandsResponse)
async def get_brands(
    current_user: CognitoUser = Depends(require_cognito_auth),
    admin_access: bool = Depends(require_admin_access)
) -> BrandsResponse:
    """Get all brand names from DynamoDB.
    
    Requires admin access to view brands.
    
    Args:
        current_user: Authenticated Cognito user
        admin_access: Admin access verification
        
    Returns:
        BrandsResponse with list of brands
        
    Raises:
        HTTPException: If retrieval fails or user lacks permissions
    """
    try:
        dynamodb_client = get_dynamodb_client()
        table_name = get_medical_brands_table()
        
        response = dynamodb_client.scan(
            TableName=table_name,
            FilterExpression="attribute_exists(#name) AND #active = :active",
            ExpressionAttributeNames={
                "#name": "name",
                "#active": "is_active"
            },
            ExpressionAttributeValues={
                ":active": {"BOOL": True}
            }
        )
        
        brands = []
        for item in response.get("Items", []):
            if "name" in item:
                brand_data = {
                    "name": item["name"]["S"],
                    "difficulty": item.get("difficulty", {}).get("S", "unknown"),
                    "category": item.get("category", {}).get("S", ""),
                    "vertical": item.get("vertical", {}).get("S", "")
                }
                brands.append(brand_data)
        
        logger.info(f"Retrieved {len(brands)} active brands for user {current_user.email}")
        
        return BrandsResponse(
            brands=[brand["name"] for brand in sorted(brands, key=lambda x: x["name"])],
            total_count=len(brands)
        )
        
    except HTTPException:
        raise
    except ClientError as e:
        logger.error(f"DynamoDB error retrieving brands: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve brands from database"
        )
    except Exception as e:
        logger.error(f"Error retrieving brands: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve brands: {str(e)}"
        )


@router.post("/brands", response_model=OperationResponse)
async def add_brand(
    request: BrandRequest,
    current_user: CognitoUser = Depends(require_cognito_auth),
    admin_access: bool = Depends(require_admin_access)
) -> OperationResponse:
    """Add a new brand name to DynamoDB.
    
    Requires admin access to add brands.
    
    Args:
        request: Brand creation request
        current_user: Authenticated Cognito user
        admin_access: Admin access verification
        
    Returns:
        OperationResponse with success status
        
    Raises:
        HTTPException: If creation fails or user lacks permissions
    """
    try:
        dynamodb_client = get_dynamodb_client()
        table_name = get_medical_brands_table()
        
        # Generate unique brand ID
        brand_id = str(uuid.uuid4())
        current_time = datetime.utcnow().isoformat() + "Z"
        
        # Create DynamoDB item with new schema
        item = {
            "brand_id": {"S": brand_id},
            "name": {"S": request.name},
            "difficulty": {"S": request.difficulty or "intermediate"},
            "is_active": {"BOOL": True},
            "created_by": {"S": current_user.email},
            "created_at": {"S": current_time}
        }
        
        if request.vertical:
            item["vertical"] = {"S": request.vertical}
        if request.category:
            item["category"] = {"S": request.category}
        if request.pronunciation:
            item["pronunciation"] = {"S": request.pronunciation}
        
        # Check for duplicate names
        existing_response = dynamodb_client.scan(
            TableName=table_name,
            FilterExpression="#name = :name",
            ExpressionAttributeNames={"#name": "name"},
            ExpressionAttributeValues={":name": {"S": request.name}}
        )
        
        if existing_response.get("Items"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Brand '{request.name}' already exists"
            )
        
        dynamodb_client.put_item(
            TableName=table_name,
            Item=item
        )
        
        logger.info(f"Brand '{request.name}' added by user {current_user.email}")
        
        return OperationResponse(
            success=True,
            message=f"Brand '{request.name}' added successfully"
        )
        
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Brand '{request.name}' already exists"
            )
        logger.error(f"DynamoDB error adding brand: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add brand to database"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding brand: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add brand: {str(e)}"
        )


@router.delete("/brands/{brand_name}", response_model=OperationResponse)
async def delete_brand(
    brand_name: str,
    current_user: CognitoUser = Depends(require_cognito_auth),
    admin_access: bool = Depends(require_admin_access)
) -> OperationResponse:
    """Delete a brand name from DynamoDB.
    
    Requires admin access to delete brands.
    
    Args:
        brand_name: Name of brand to delete
        current_user: Authenticated Cognito user
        admin_access: Admin access verification
        
    Returns:
        OperationResponse with success status
        
    Raises:
        HTTPException: If deletion fails or user lacks permissions
    """
    try:
        dynamodb_client = get_dynamodb_client()
        table_name = get_medical_brands_table()
        
        # First, find the brand by name to get its brand_id
        response = dynamodb_client.scan(
            TableName=table_name,
            FilterExpression="#name = :name",
            ExpressionAttributeNames={"#name": "name"},
            ExpressionAttributeValues={":name": {"S": brand_name}}
        )
        
        items = response.get("Items", [])
        if not items:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Brand '{brand_name}' not found"
            )
        
        # Delete the brand using its brand_id
        brand_id = items[0]["brand_id"]["S"]
        dynamodb_client.delete_item(
            TableName=table_name,
            Key={"brand_id": {"S": brand_id}}
        )
        
        logger.info(f"Brand '{brand_name}' deleted by user {current_user.email}")
        
        return OperationResponse(
            success=True,
            message=f"Brand '{brand_name}' deleted successfully"
        )
        
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Brand '{brand_name}' not found"
            )
        logger.error(f"DynamoDB error deleting brand: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete brand from database"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting brand: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete brand: {str(e)}"
        )


@router.get("/terms", response_model=TermsResponse)
async def get_terms(
    current_user: CognitoUser = Depends(require_cognito_auth),
    admin_access: bool = Depends(require_admin_access)
) -> TermsResponse:
    """Get all medical terms from DynamoDB.
    
    Requires admin access to view terms.
    
    Args:
        current_user: Authenticated Cognito user
        admin_access: Admin access verification
        
    Returns:
        TermsResponse with list of terms
        
    Raises:
        HTTPException: If retrieval fails or user lacks permissions
    """
    try:
        dynamodb_client = get_dynamodb_client()
        table_name = get_medical_terms_table()
        
        response = dynamodb_client.scan(
            TableName=table_name,
            FilterExpression="attribute_exists(#name) AND #active = :active",
            ExpressionAttributeNames={
                "#name": "name",
                "#active": "is_active"
            },
            ExpressionAttributeValues={
                ":active": {"BOOL": True}
            }
        )
        
        terms = []
        for item in response.get("Items", []):
            if "name" in item:
                term_data = {
                    "name": item["name"]["S"],
                    "difficulty": item.get("difficulty", {}).get("S", "unknown"),
                    "category": item.get("category", {}).get("S", ""),
                    "vertical": item.get("vertical", {}).get("S", "")
                }
                terms.append(term_data)
        
        logger.info(f"Retrieved {len(terms)} active terms for user {current_user.email}")
        
        return TermsResponse(
            terms=[term["name"] for term in sorted(terms, key=lambda x: x["name"])],
            total_count=len(terms)
        )
        
    except HTTPException:
        raise
    except ClientError as e:
        logger.error(f"DynamoDB error retrieving terms: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve terms from database"
        )
    except Exception as e:
        logger.error(f"Error retrieving terms: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve terms: {str(e)}"
        )


@router.post("/terms", response_model=OperationResponse)
async def add_term(
    request: TermRequest,
    current_user: CognitoUser = Depends(require_cognito_auth),
    admin_access: bool = Depends(require_admin_access)
) -> OperationResponse:
    """Add a new medical term to DynamoDB.
    
    Requires admin access to add terms.
    
    Args:
        request: Term creation request
        current_user: Authenticated Cognito user
        admin_access: Admin access verification
        
    Returns:
        OperationResponse with success status
        
    Raises:
        HTTPException: If creation fails or user lacks permissions
    """
    try:
        dynamodb_client = get_dynamodb_client()
        table_name = get_medical_terms_table()
        
        # Generate unique term ID
        term_id = str(uuid.uuid4())
        current_time = datetime.utcnow().isoformat() + "Z"
        
        # Create DynamoDB item with new schema
        item = {
            "term_id": {"S": term_id},
            "name": {"S": request.name},
            "difficulty": {"S": request.difficulty or "intermediate"},
            "is_active": {"BOOL": True},
            "created_by": {"S": current_user.email},
            "created_at": {"S": current_time}
        }
        
        if request.vertical:
            item["vertical"] = {"S": request.vertical}
        if request.category:
            item["category"] = {"S": request.category}
        if request.pronunciation:
            item["pronunciation"] = {"S": request.pronunciation}
        
        # Check for duplicate names
        existing_response = dynamodb_client.scan(
            TableName=table_name,
            FilterExpression="#name = :name",
            ExpressionAttributeNames={"#name": "name"},
            ExpressionAttributeValues={":name": {"S": request.name}}
        )
        
        if existing_response.get("Items"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Term '{request.name}' already exists"
            )
        
        dynamodb_client.put_item(
            TableName=table_name,
            Item=item
        )
        
        logger.info(f"Term '{request.name}' added by user {current_user.email}")
        
        return OperationResponse(
            success=True,
            message=f"Term '{request.name}' added successfully"
        )
        
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Term '{request.name}' already exists"
            )
        logger.error(f"DynamoDB error adding term: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add term to database"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding term: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add term: {str(e)}"
        )


@router.delete("/terms/{term_name}", response_model=OperationResponse)
async def delete_term(
    term_name: str,
    current_user: CognitoUser = Depends(require_cognito_auth),
    admin_access: bool = Depends(require_admin_access)
) -> OperationResponse:
    """Delete a medical term from DynamoDB.
    
    Requires admin access to delete terms.
    
    Args:
        term_name: Name of term to delete
        current_user: Authenticated Cognito user
        admin_access: Admin access verification
        
    Returns:
        OperationResponse with success status
        
    Raises:
        HTTPException: If deletion fails or user lacks permissions
    """
    try:
        dynamodb_client = get_dynamodb_client()
        table_name = get_medical_terms_table()
        
        # First, find the term by name to get its term_id
        response = dynamodb_client.scan(
            TableName=table_name,
            FilterExpression="#name = :name",
            ExpressionAttributeNames={"#name": "name"},
            ExpressionAttributeValues={":name": {"S": term_name}}
        )
        
        items = response.get("Items", [])
        if not items:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Term '{term_name}' not found"
            )
        
        # Delete the term using its term_id
        term_id = items[0]["term_id"]["S"]
        dynamodb_client.delete_item(
            TableName=table_name,
            Key={"term_id": {"S": term_id}}
        )
        
        logger.info(f"Term '{term_name}' deleted by user {current_user.email}")
        
        return OperationResponse(
            success=True,
            message=f"Term '{term_name}' deleted successfully"
        )
        
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Term '{term_name}' not found"
            )
        logger.error(f"DynamoDB error deleting term: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete term from database"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting term: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete term: {str(e)}"
        )