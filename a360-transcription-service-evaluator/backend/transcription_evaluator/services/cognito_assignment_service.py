"""Script assignment service with Cognito integration.

This service handles script assignments for voice actors, evaluators, and reviewers
using AWS Cognito for user identification and Verified Permissions for authorization.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_

from ..aws.verified_permissions import (
    AuthorizationDecision,
    VerifiedPermissionsClient,
    get_verified_permissions_client,
)
from ..config.settings import get_database_session
from ..models.cognito_models import Script, ScriptAssignment, get_user_by_cognito_id
from ..services.cognito_user_service import CognitoUserService, get_user_service

logger = logging.getLogger(__name__)


class CognitoAssignmentService:
    """Service for managing script assignments with Cognito integration."""

    def __init__(
        self,
        avp_client: Optional[VerifiedPermissionsClient] = None,
        user_service: Optional[CognitoUserService] = None,
    ):
        """Initialize the assignment service.

        Args:
            avp_client: Verified Permissions client for authorization
            user_service: User service for user operations
        """
        self.avp_client = avp_client or get_verified_permissions_client()
        self.user_service = user_service or get_user_service()

    async def create_assignment(
        self,
        script_id: UUID,
        assigned_to_cognito_id: str,
        assignment_type: str,
        assigned_by_cognito_id: str,
        priority: int = 3,
        due_date: Optional[datetime] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new script assignment.

        Args:
            script_id: UUID of the script to assign
            assigned_to_cognito_id: Cognito ID of user being assigned
            assignment_type: Type of assignment ('record', 'evaluate', 'review')
            assigned_by_cognito_id: Cognito ID of user creating assignment
            priority: Assignment priority (1-5)
            due_date: Optional due date
            notes: Optional assignment notes

        Returns:
            Dict containing assignment information
        """
        # Check authorization
        is_authorized = await self._check_authorization(
            assigned_by_cognito_id, "AssignScript", "Script", str(script_id)
        )
        if not is_authorized:
            raise PermissionError("Insufficient permissions to create assignments")

        try:
            with get_database_session() as db:
                # Verify script exists
                script = db.query(Script).filter(Script.id == script_id).first()
                if not script:
                    raise ValueError("Script not found")

                # Verify users exist
                assignee = get_user_by_cognito_id(db, assigned_to_cognito_id)
                assigner = get_user_by_cognito_id(db, assigned_by_cognito_id)

                if not assignee or not assigner:
                    raise ValueError("Invalid user ID provided")

                # Check for existing active assignment
                existing = (
                    db.query(ScriptAssignment)
                    .filter(
                        and_(
                            ScriptAssignment.script_id == script_id,
                            ScriptAssignment.assigned_to_cognito_id
                            == assigned_to_cognito_id,
                            ScriptAssignment.assignment_type == assignment_type,
                            ScriptAssignment.status.in_(["pending", "in_progress"]),
                        )
                    )
                    .first()
                )

                if existing:
                    raise ValueError(
                        "Active assignment already exists for this user and script"
                    )

                # Create assignment
                assignment = ScriptAssignment(
                    script_id=script_id,
                    assigned_to_cognito_id=assigned_to_cognito_id,
                    assigned_by_cognito_id=assigned_by_cognito_id,
                    assignment_type=assignment_type,
                    priority=priority,
                    due_date=due_date,
                    notes=notes,
                )

                db.add(assignment)
                db.commit()
                db.refresh(assignment)

                logger.info(
                    f"Created assignment {assignment.id} for script {script_id}"
                )

                return {
                    "assignment_id": str(assignment.id),
                    "script_id": str(assignment.script_id),
                    "script_title": script.title,
                    "assigned_to_cognito_id": assignment.assigned_to_cognito_id,
                    "assigned_to_name": assignee.full_name,
                    "assigned_by_cognito_id": assignment.assigned_by_cognito_id,
                    "assigned_by_name": assigner.full_name,
                    "assignment_type": assignment.assignment_type,
                    "status": assignment.status,
                    "priority": assignment.priority,
                    "due_date": assignment.due_date.isoformat()
                    if assignment.due_date
                    else None,
                    "notes": assignment.notes,
                    "created_at": assignment.created_at.isoformat()
                    if getattr(assignment, "created_at", None)
                    else None,
                }

        except Exception as e:
            logger.error(f"Failed to create assignment: {str(e)}")
            raise

    async def get_user_assignments(
        self,
        cognito_user_id: str,
        status_filter: Optional[str] = None,
        assignment_type_filter: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get assignments for a specific user.

        Args:
            cognito_user_id: Cognito ID of user
            status_filter: Optional status filter
            assignment_type_filter: Optional assignment type filter
            limit: Maximum number of assignments to return

        Returns:
            List of assignment dictionaries
        """
        # Check authorization (users can view their own assignments)
        is_authorized = await self._check_authorization(
            cognito_user_id, "ViewAssignment", "Assignment"
        )
        if not is_authorized:
            raise PermissionError("Insufficient permissions to view assignments")

        try:
            with get_database_session() as db:
                query = db.query(ScriptAssignment).filter(
                    ScriptAssignment.assigned_to_cognito_id == cognito_user_id
                )

                if status_filter:
                    query = query.filter(ScriptAssignment.status == status_filter)

                if assignment_type_filter:
                    query = query.filter(
                        ScriptAssignment.assignment_type == assignment_type_filter
                    )

                assignments = (
                    query.order_by(
                        ScriptAssignment.due_date.nulls_last(),
                        ScriptAssignment.priority,
                        ScriptAssignment.created_at.desc(),
                    )
                    .limit(limit)
                    .all()
                )

                result = []
                for assignment in assignments:
                    # Get related data
                    script = (
                        db.query(Script)
                        .filter(Script.id == assignment.script_id)
                        .first()
                    )
                    assigner = get_user_by_cognito_id(
                        db, assignment.assigned_by_cognito_id
                    )

                    assignment_data = {
                        "assignment_id": str(assignment.id),
                        "script_id": str(assignment.script_id),
                        "script_title": script.title if script else "Unknown",
                        "script_difficulty": script.difficulty_level
                        if script
                        else None,
                        "assignment_type": assignment.assignment_type,
                        "status": assignment.status,
                        "priority": assignment.priority,
                        "due_date": assignment.due_date.isoformat()
                        if assignment.due_date
                        else None,
                        "notes": assignment.notes,
                        "assigned_by_name": assigner.full_name
                        if assigner
                        else "Unknown",
                        "created_at": assignment.created_at.isoformat()
                        if getattr(assignment, "created_at", None)
                        else None,
                        "updated_at": assignment.updated_at.isoformat()
                        if getattr(assignment, "updated_at", None)
                        else None,
                        "completed_at": assignment.completed_at.isoformat()
                        if assignment.completed_at
                        else None,
                    }

                    result.append(assignment_data)

                return result

        except Exception as e:
            logger.error(
                f"Failed to get assignments for user {cognito_user_id}: {str(e)}"
            )
            raise

    async def update_assignment_status(
        self,
        assignment_id: UUID,
        new_status: str,
        cognito_user_id: str,
        notes: Optional[str] = None,
    ) -> bool:
        """Update assignment status.

        Args:
            assignment_id: UUID of assignment to update
            new_status: New status value
            cognito_user_id: Cognito ID of user making the update
            notes: Optional notes about the status change

        Returns:
            True if update successful
        """
        try:
            with get_database_session() as db:
                assignment = (
                    db.query(ScriptAssignment)
                    .filter(ScriptAssignment.id == assignment_id)
                    .first()
                )

                if not assignment:
                    raise ValueError("Assignment not found")

                # Check authorization (assignee can update their own assignments)
                if assignment.assigned_to_cognito_id != cognito_user_id:
                    is_authorized = await self._check_authorization(
                        cognito_user_id,
                        "UpdateAssignment",
                        "Assignment",
                        str(assignment_id),
                    )
                    if not is_authorized:
                        raise PermissionError(
                            "Insufficient permissions to update assignment"
                        )

                # Update status
                old_status = assignment.status
                assignment.status = new_status

                if notes:
                    assignment.notes = f"{assignment.notes or ''}\n\n[{datetime.now(UTC).isoformat()}] {notes}".strip()

                if new_status == "completed":
                    assignment.completed_at = datetime.now(UTC)

                db.commit()

                logger.info(
                    f"Updated assignment {assignment_id} status from {old_status} to {new_status}"
                )
                return True

        except Exception as e:
            logger.error(f"Failed to update assignment {assignment_id}: {str(e)}")
            raise

    async def bulk_assign_scripts(
        self,
        script_ids: List[UUID],
        user_assignments: Dict[str, List[str]],  # cognito_user_id -> [assignment_types]
        assigned_by_cognito_id: str,
        priority: int = 3,
        due_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Bulk assign multiple scripts to multiple users.

        Args:
            script_ids: List of script UUIDs to assign
            user_assignments: Dict mapping cognito_user_id to list of assignment types
            assigned_by_cognito_id: Cognito ID of user creating assignments
            priority: Assignment priority
            due_date: Optional due date for all assignments

        Returns:
            Dict containing assignment results
        """
        # Check authorization
        is_authorized = await self._check_authorization(
            assigned_by_cognito_id, "BulkAssignScripts", "Script"
        )
        if not is_authorized:
            raise PermissionError("Insufficient permissions to create bulk assignments")

        try:
            created_assignments = []
            failed_assignments = []

            with get_database_session() as db:
                for script_id in script_ids:
                    for cognito_user_id, assignment_types in user_assignments.items():
                        for assignment_type in assignment_types:
                            try:
                                assignment = ScriptAssignment(
                                    script_id=script_id,
                                    assigned_to_cognito_id=cognito_user_id,
                                    assigned_by_cognito_id=assigned_by_cognito_id,
                                    assignment_type=assignment_type,
                                    priority=priority,
                                    due_date=due_date,
                                )

                                db.add(assignment)
                                created_assignments.append(
                                    {
                                        "script_id": str(script_id),
                                        "assigned_to": cognito_user_id,
                                        "assignment_type": assignment_type,
                                    }
                                )

                            except Exception as e:
                                failed_assignments.append(
                                    {
                                        "script_id": str(script_id),
                                        "assigned_to": cognito_user_id,
                                        "assignment_type": assignment_type,
                                        "error": str(e),
                                    }
                                )

                db.commit()

                logger.info(
                    f"Bulk assignment created {len(created_assignments)} assignments, {len(failed_assignments)} failed"
                )

                return {
                    "created_count": len(created_assignments),
                    "failed_count": len(failed_assignments),
                    "created_assignments": created_assignments,
                    "failed_assignments": failed_assignments,
                }

        except Exception as e:
            logger.error(f"Bulk assignment failed: {str(e)}")
            raise

    async def get_assignment_statistics(
        self, cognito_user_id: str, requesting_user_id: str
    ) -> Dict[str, Any]:
        """Get assignment statistics for a user.

        Args:
            cognito_user_id: Cognito ID of user to get stats for
            requesting_user_id: Cognito ID of user requesting stats

        Returns:
            Dict containing assignment statistics
        """
        # Check authorization (users can view their own stats, admins can view all)
        if cognito_user_id != requesting_user_id:
            is_authorized = await self._check_authorization(
                requesting_user_id, "ViewUserStats", "User", cognito_user_id
            )
            if not is_authorized:
                raise PermissionError(
                    "Insufficient permissions to view user statistics"
                )

        try:
            with get_database_session() as db:
                assignments = (
                    db.query(ScriptAssignment)
                    .filter(ScriptAssignment.assigned_to_cognito_id == cognito_user_id)
                    .all()
                )

                stats = {
                    "total_assignments": len(assignments),
                    "by_status": {},
                    "by_type": {},
                    "by_priority": {},
                    "overdue_count": 0,
                    "completed_this_week": 0,
                    "average_completion_time_hours": None,
                }

                completion_times = []
                now = datetime.now(UTC)
                week_ago = now - timedelta(days=7)

                for assignment in assignments:
                    # Count by status
                    status = assignment.status
                    stats["by_status"][status] = stats["by_status"].get(status, 0) + 1

                    # Count by type
                    type_name = assignment.assignment_type
                    stats["by_type"][type_name] = stats["by_type"].get(type_name, 0) + 1

                    # Count by priority
                    priority = assignment.priority
                    stats["by_priority"][priority] = (
                        stats["by_priority"].get(priority, 0) + 1
                    )

                    # Check if overdue
                    if (
                        assignment.due_date
                        and (
                            assignment.due_date.replace(tzinfo=UTC)
                            if assignment.due_date.tzinfo is None
                            else assignment.due_date
                        )
                        < now
                        and assignment.status in ["pending", "in_progress"]
                    ):
                        stats["overdue_count"] += 1

                    # Check if completed this week
                    if (
                        assignment.completed_at
                        and (
                            assignment.completed_at.replace(tzinfo=UTC)
                            if assignment.completed_at.tzinfo is None
                            else assignment.completed_at
                        )
                        > week_ago
                    ):
                        stats["completed_this_week"] += 1

                    # Calculate completion time
                    if assignment.completed_at and assignment.created_at:
                        completed = (
                            assignment.completed_at.replace(tzinfo=UTC)
                            if assignment.completed_at.tzinfo is None
                            else assignment.completed_at
                        )
                        created = (
                            assignment.created_at.replace(tzinfo=UTC)
                            if assignment.created_at.tzinfo is None
                            else assignment.created_at
                        )
                        completion_time = completed - created
                        completion_times.append(
                            completion_time.total_seconds() / 3600
                        )  # Convert to hours

                # Calculate average completion time
                if completion_times:
                    stats["average_completion_time_hours"] = sum(
                        completion_times
                    ) / len(completion_times)

                return stats

        except Exception as e:
            logger.error(
                f"Failed to get assignment statistics for {cognito_user_id}: {str(e)}"
            )
            raise

    async def reassign_assignment(
        self,
        assignment_id: UUID,
        new_assignee_cognito_id: str,
        reassigned_by_cognito_id: str,
        reason: Optional[str] = None,
    ) -> bool:
        """Reassign an assignment to a different user.

        Args:
            assignment_id: UUID of assignment to reassign
            new_assignee_cognito_id: Cognito ID of new assignee
            reassigned_by_cognito_id: Cognito ID of user making the reassignment
            reason: Optional reason for reassignment

        Returns:
            True if reassignment successful
        """
        # Check authorization
        is_authorized = await self._check_authorization(
            reassigned_by_cognito_id, "ReassignScript", "Assignment", str(assignment_id)
        )
        if not is_authorized:
            raise PermissionError("Insufficient permissions to reassign assignments")

        try:
            with get_database_session() as db:
                assignment = (
                    db.query(ScriptAssignment)
                    .filter(ScriptAssignment.id == assignment_id)
                    .first()
                )

                if not assignment:
                    raise ValueError("Assignment not found")

                # Verify new assignee exists
                new_assignee = get_user_by_cognito_id(db, new_assignee_cognito_id)
                if not new_assignee:
                    raise ValueError("New assignee not found")

                # Update assignment
                old_assignee_id = assignment.assigned_to_cognito_id
                assignment.assigned_to_cognito_id = new_assignee_cognito_id
                assignment.status = "pending"  # Reset to pending
                assignment.completed_at = None

                # Add reassignment note
                reassignment_note = f"[{datetime.now(UTC).isoformat()}] Reassigned from {old_assignee_id} to {new_assignee_cognito_id}"
                if reason:
                    reassignment_note += f" - Reason: {reason}"

                assignment.notes = (
                    f"{assignment.notes or ''}\n\n{reassignment_note}".strip()
                )

                db.commit()

                logger.info(
                    f"Reassigned assignment {assignment_id} to {new_assignee_cognito_id}"
                )
                return True

        except Exception as e:
            logger.error(f"Failed to reassign assignment {assignment_id}: {str(e)}")
            raise

    async def _check_authorization(
        self,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
    ) -> bool:
        """Check if user is authorized for action.

        Args:
            user_id: Cognito user ID
            action: Action to authorize
            resource_type: Type of resource
            resource_id: Specific resource ID

        Returns:
            True if authorized
        """
        try:
            with get_database_session() as db:
                user_profile = get_user_by_cognito_id(db, user_id)
                if not user_profile:
                    return False

                groups = await self.user_service.cognito_client.get_user_groups(
                    user_profile.email
                )

                response = await self.avp_client.is_authorized(
                    principal_id=user_id,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    principal_groups=groups,
                )

                return response.decision == AuthorizationDecision.ALLOW

        except Exception as e:
            logger.error(f"Authorization check failed for {user_id}: {str(e)}")
            return False


# Global service instance
_assignment_service: Optional[CognitoAssignmentService] = None


def get_assignment_service() -> CognitoAssignmentService:
    """Get or create the global assignment service instance.

    Returns:
        CognitoAssignmentService instance
    """
    global _assignment_service

    if _assignment_service is None:
        _assignment_service = CognitoAssignmentService()

    return _assignment_service
