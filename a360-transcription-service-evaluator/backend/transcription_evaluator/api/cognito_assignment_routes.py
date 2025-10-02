"""FastAPI routes for script assignments with Cognito integration.

This module provides API endpoints for managing script assignments
using AWS Cognito for authentication and Verified Permissions for authorization.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from uuid import UUID
import logging

from fastapi import APIRouter, HTTPException, Depends, status, Query
from pydantic import BaseModel, Field

from ..aws.authorizers import CognitoClaims
from ..api.cognito_auth_routes import get_current_user
from ..services.cognito_assignment_service import CognitoAssignmentService, get_assignment_service
from ..aws.cognito_client import get_cognito_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/assignments", tags=["assignments"])


# Pydantic models for request/response
class CreateAssignmentRequest(BaseModel):
    """Request model for creating a new assignment."""
    script_id: UUID
    assigned_to_cognito_id: str = Field(..., description="Cognito user ID of assignee")
    assignment_type: str = Field(..., pattern="^(record|evaluate|review)$")
    priority: int = Field(default=3, ge=1, le=5)
    due_date: Optional[datetime] = None
    notes: Optional[str] = Field(default=None, max_length=2000)


class BulkAssignmentRequest(BaseModel):
    """Request model for bulk assignment creation."""
    script_ids: List[UUID] = Field(..., min_items=1)
    user_assignments: Dict[str, List[str]] = Field(
        ..., 
        description="Map of cognito_user_id to list of assignment types"
    )
    priority: int = Field(default=3, ge=1, le=5)
    due_date: Optional[datetime] = None


class UpdateAssignmentStatusRequest(BaseModel):
    """Request model for updating assignment status."""
    status: str = Field(..., pattern="^(pending|in_progress|completed|skipped)$")
    notes: Optional[str] = Field(default=None, max_length=2000)


class ReassignmentRequest(BaseModel):
    """Request model for reassigning an assignment."""
    new_assignee_cognito_id: str = Field(..., description="Cognito user ID of new assignee")
    reason: Optional[str] = Field(default=None, max_length=500)


class AssignmentResponse(BaseModel):
    """Response model for assignment information."""
    assignment_id: str
    script_id: str
    script_title: str
    script_difficulty: Optional[int]
    assigned_to_cognito_id: str
    assigned_to_name: str
    assigned_by_cognito_id: str
    assigned_by_name: str
    assignment_type: str
    status: str
    priority: int
    due_date: Optional[str]
    notes: Optional[str]
    created_at: str
    updated_at: str
    completed_at: Optional[str]


class AssignmentStatsResponse(BaseModel):
    """Response model for assignment statistics."""
    total_assignments: int
    by_status: Dict[str, int]
    by_type: Dict[str, int]
    by_priority: Dict[int, int]
    overdue_count: int
    completed_this_week: int
    average_completion_time_hours: Optional[float]


class VoiceActorResponse(BaseModel):
    """Response model for voice actor information."""
    cognito_id: str
    email: str
    name: str
    is_active: bool


# Dependency to get assignment service
def get_assignment_service_dependency() -> CognitoAssignmentService:
    """Get assignment service instance."""
    return get_assignment_service()


@router.post("/", response_model=Dict[str, Any])
async def create_assignment(
    request: CreateAssignmentRequest,
    current_user: CognitoClaims = Depends(get_current_user),
    assignment_service: CognitoAssignmentService = Depends(get_assignment_service_dependency)
) -> Dict[str, Any]:
    """Create a new script assignment.
    
    Args:
        request: Assignment creation request
        current_user: Current authenticated user
        assignment_service: Assignment service instance
        
    Returns:
        Created assignment information
    """
    try:
        assignment = await assignment_service.create_assignment(
            script_id=request.script_id,
            assigned_to_cognito_id=request.assigned_to_cognito_id,
            assignment_type=request.assignment_type,
            assigned_by_cognito_id=current_user.sub,
            priority=request.priority,
            due_date=request.due_date,
            notes=request.notes
        )
        
        return {
            "success": True,
            "assignment": assignment,
            "message": "Assignment created successfully"
        }
        
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Assignment creation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Assignment creation failed"
        )


@router.post("/bulk", response_model=Dict[str, Any])
async def create_bulk_assignments(
    request: BulkAssignmentRequest,
    current_user: CognitoClaims = Depends(get_current_user),
    assignment_service: CognitoAssignmentService = Depends(get_assignment_service_dependency)
) -> Dict[str, Any]:
    """Create multiple assignments in bulk.
    
    Args:
        request: Bulk assignment request
        current_user: Current authenticated user
        assignment_service: Assignment service instance
        
    Returns:
        Bulk assignment results
    """
    try:
        result = await assignment_service.bulk_assign_scripts(
            script_ids=request.script_ids,
            user_assignments=request.user_assignments,
            assigned_by_cognito_id=current_user.sub,
            priority=request.priority,
            due_date=request.due_date
        )
        
        return {
            "success": True,
            "results": result,
            "message": f"Created {result['created_count']} assignments, {result['failed_count']} failed"
        }
        
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Bulk assignment creation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bulk assignment creation failed"
        )


@router.get("/my", response_model=List[AssignmentResponse])
async def get_my_assignments(
    status_filter: Optional[str] = Query(None, pattern="^(pending|in_progress|completed|skipped)$"),
    assignment_type_filter: Optional[str] = Query(None, pattern="^(record|evaluate|review)$"),
    limit: int = Query(50, ge=1, le=200),
    current_user: CognitoClaims = Depends(get_current_user),
    assignment_service: CognitoAssignmentService = Depends(get_assignment_service_dependency)
) -> List[AssignmentResponse]:
    """Get assignments for the current user.
    
    Args:
        status_filter: Optional status filter
        assignment_type_filter: Optional assignment type filter
        limit: Maximum number of assignments to return
        current_user: Current authenticated user
        assignment_service: Assignment service instance
        
    Returns:
        List of user's assignments
    """
    try:
        assignments = await assignment_service.get_user_assignments(
            cognito_user_id=current_user.sub,
            status_filter=status_filter,
            assignment_type_filter=assignment_type_filter,
            limit=limit
        )
        
        return [AssignmentResponse(**assignment) for assignment in assignments]
        
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to get assignments for {current_user.sub}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve assignments"
        )


@router.get("/users/{cognito_user_id}", response_model=List[AssignmentResponse])
async def get_user_assignments(
    cognito_user_id: str,
    status_filter: Optional[str] = Query(None, pattern="^(pending|in_progress|completed|skipped)$"),
    assignment_type_filter: Optional[str] = Query(None, pattern="^(record|evaluate|review)$"),
    limit: int = Query(50, ge=1, le=200),
    current_user: CognitoClaims = Depends(get_current_user),
    assignment_service: CognitoAssignmentService = Depends(get_assignment_service_dependency)
) -> List[AssignmentResponse]:
    """Get assignments for a specific user (admin/manager access).
    
    Args:
        cognito_user_id: Cognito user ID to get assignments for
        status_filter: Optional status filter
        assignment_type_filter: Optional assignment type filter
        limit: Maximum number of assignments to return
        current_user: Current authenticated user
        assignment_service: Assignment service instance
        
    Returns:
        List of user's assignments
    """
    try:
        assignments = await assignment_service.get_user_assignments(
            cognito_user_id=cognito_user_id,
            status_filter=status_filter,
            assignment_type_filter=assignment_type_filter,
            limit=limit
        )
        
        return [AssignmentResponse(**assignment) for assignment in assignments]
        
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to get assignments for {cognito_user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve assignments"
        )


@router.put("/{assignment_id}/status", response_model=Dict[str, Any])
async def update_assignment_status(
    assignment_id: UUID,
    request: UpdateAssignmentStatusRequest,
    current_user: CognitoClaims = Depends(get_current_user),
    assignment_service: CognitoAssignmentService = Depends(get_assignment_service_dependency)
) -> Dict[str, Any]:
    """Update assignment status.
    
    Args:
        assignment_id: UUID of assignment to update
        request: Status update request
        current_user: Current authenticated user
        assignment_service: Assignment service instance
        
    Returns:
        Update result
    """
    try:
        success = await assignment_service.update_assignment_status(
            assignment_id=assignment_id,
            new_status=request.status,
            cognito_user_id=current_user.sub,
            notes=request.notes
        )
        
        if success:
            return {
                "success": True,
                "message": f"Assignment status updated to {request.status}"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Assignment status update failed"
            )
            
    except HTTPException:
        raise
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to update assignment {assignment_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Assignment status update failed"
        )


@router.put("/{assignment_id}/reassign", response_model=Dict[str, Any])
async def reassign_assignment(
    assignment_id: UUID,
    request: ReassignmentRequest,
    current_user: CognitoClaims = Depends(get_current_user),
    assignment_service: CognitoAssignmentService = Depends(get_assignment_service_dependency)
) -> Dict[str, Any]:
    """Reassign an assignment to a different user.
    
    Args:
        assignment_id: UUID of assignment to reassign
        request: Reassignment request
        current_user: Current authenticated user
        assignment_service: Assignment service instance
        
    Returns:
        Reassignment result
    """
    try:
        success = await assignment_service.reassign_assignment(
            assignment_id=assignment_id,
            new_assignee_cognito_id=request.new_assignee_cognito_id,
            reassigned_by_cognito_id=current_user.sub,
            reason=request.reason
        )
        
        if success:
            return {
                "success": True,
                "message": "Assignment reassigned successfully"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Assignment reassignment failed"
            )
            
    except HTTPException:
        raise
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to reassign assignment {assignment_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Assignment reassignment failed"
        )


@router.get("/stats/my", response_model=AssignmentStatsResponse)
async def get_my_assignment_stats(
    current_user: CognitoClaims = Depends(get_current_user),
    assignment_service: CognitoAssignmentService = Depends(get_assignment_service_dependency)
) -> AssignmentStatsResponse:
    """Get assignment statistics for the current user.
    
    Args:
        current_user: Current authenticated user
        assignment_service: Assignment service instance
        
    Returns:
        User's assignment statistics
    """
    try:
        stats = await assignment_service.get_assignment_statistics(
            cognito_user_id=current_user.sub,
            requesting_user_id=current_user.sub
        )
        
        return AssignmentStatsResponse(**stats)
        
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to get assignment stats for {current_user.sub}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve assignment statistics"
        )


@router.get("/stats/users/{cognito_user_id}", response_model=AssignmentStatsResponse)
async def get_user_assignment_stats(
    cognito_user_id: str,
    current_user: CognitoClaims = Depends(get_current_user),
    assignment_service: CognitoAssignmentService = Depends(get_assignment_service_dependency)
) -> AssignmentStatsResponse:
    """Get assignment statistics for a specific user (admin/manager access).
    
    Args:
        cognito_user_id: Cognito user ID to get stats for
        current_user: Current authenticated user
        assignment_service: Assignment service instance
        
    Returns:
        User's assignment statistics
    """
    try:
        stats = await assignment_service.get_assignment_statistics(
            cognito_user_id=cognito_user_id,
            requesting_user_id=current_user.sub
        )
        
        return AssignmentStatsResponse(**stats)
        
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to get assignment stats for {cognito_user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve assignment statistics"
        )


@router.get("/pending", response_model=List[AssignmentResponse])
async def get_pending_assignments(
    limit: int = Query(100, ge=1, le=500),
    current_user: CognitoClaims = Depends(get_current_user),
    assignment_service: CognitoAssignmentService = Depends(get_assignment_service_dependency)
) -> List[AssignmentResponse]:
    """Get all pending assignments (admin/manager access).
    
    Args:
        limit: Maximum number of assignments to return
        current_user: Current authenticated user
        assignment_service: Assignment service instance
        
    Returns:
        List of pending assignments
    """
    try:
        # This would require additional authorization logic and service method
        # For now, redirect to user's own pending assignments
        assignments = await assignment_service.get_user_assignments(
            cognito_user_id=current_user.sub,
            status_filter="pending",
            limit=limit
        )
        
        return [AssignmentResponse(**assignment) for assignment in assignments]
        
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to get pending assignments: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve pending assignments"
        )


@router.get("/overdue", response_model=List[AssignmentResponse])
async def get_overdue_assignments(
    limit: int = Query(100, ge=1, le=500),
    current_user: CognitoClaims = Depends(get_current_user),
    assignment_service: CognitoAssignmentService = Depends(get_assignment_service_dependency)
) -> List[AssignmentResponse]:
    """Get all overdue assignments for the current user.
    
    Args:
        limit: Maximum number of assignments to return
        current_user: Current authenticated user
        assignment_service: Assignment service instance
        
    Returns:
        List of overdue assignments
    """
    try:
        # Get all pending/in_progress assignments and filter overdue on client
        assignments = await assignment_service.get_user_assignments(
            cognito_user_id=current_user.sub,
            limit=limit
        )
        
        # Filter for overdue assignments
        now = datetime.utcnow()
        overdue_assignments = []
        
        for assignment in assignments:
            if (assignment.get('due_date') and 
                assignment.get('status') in ['pending', 'in_progress']):
                try:
                    due_date = datetime.fromisoformat(assignment['due_date'].replace('Z', '+00:00'))
                    if due_date < now:
                        overdue_assignments.append(assignment)
                except (ValueError, TypeError):
                    continue
        
        return [AssignmentResponse(**assignment) for assignment in overdue_assignments]
        
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to get overdue assignments: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve overdue assignments"
        )


@router.get("/voice-actors", response_model=List[VoiceActorResponse])
async def get_available_voice_actors(
    current_user: CognitoClaims = Depends(get_current_user)
) -> List[VoiceActorResponse]:
    """Get all available voice actors for assignment.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        List of available voice actors
    """
    try:
        # Check if user has permission to assign (admin role required)
        if 'admin' not in current_user.cognito_groups:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can view available voice actors"
            )
        
        cognito_client = get_cognito_client()
        
        # Get all users and filter for voice actors
        users_response = await cognito_client.list_users(limit=100)
        voice_actors = []
        
        for user in users_response['users']:
            if 'voice_actor' in user.groups and user.is_active:
                voice_actors.append(VoiceActorResponse(
                    cognito_id=user.user_id,
                    email=user.email,
                    name=user.name or user.email,
                    is_active=user.is_active
                ))
        
        logger.info(
            f"Retrieved {len(voice_actors)} available voice actors",
            extra={"requesting_user": current_user.sub}
        )
        
        return voice_actors
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get voice actors: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve voice actors"
        )