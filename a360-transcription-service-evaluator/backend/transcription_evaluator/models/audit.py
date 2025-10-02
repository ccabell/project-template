"""Audit logging models for A360 Transcription Service Evaluator.

This module provides Pydantic models for audit logging functionality,
supporting comprehensive activity tracking and security monitoring.

The audit system tracks user actions, resource access, and system events
with structured logging for compliance and security analysis.

Example:
    Creating an audit log entry:

    >>> from transcription_evaluator.models.audit import AuditLogCreate
    >>> audit_entry = AuditLogCreate(
    ...     user_id="123e4567-e89b-12d3-a456-426614174000",
    ...     action="user_login",
    ...     resource_type="authentication",
    ...     details={"ip_address": "192.168.1.1", "success": True}
    ... )
"""

from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID
from pydantic import BaseModel, Field
from ipaddress import IPv4Address, IPv6Address
from typing import Union


class AuditLogBase(BaseModel):
    """Base audit log model with common fields."""
    
    user_id: Optional[UUID] = Field(None, description="ID of the user performing the action")
    action: str = Field(..., min_length=1, max_length=100, description="Action performed")
    resource_type: Optional[str] = Field(None, max_length=100, description="Type of resource accessed")
    resource_id: Optional[str] = Field(None, max_length=255, description="ID of the resource accessed")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional action details")
    ip_address: Optional[Union[IPv4Address, IPv6Address]] = Field(None, description="IP address of the request")
    user_agent: Optional[str] = Field(None, description="User agent string")


class AuditLogCreate(AuditLogBase):
    """Model for creating new audit log entries."""
    pass


class AuditLogResponse(AuditLogBase):
    """Model for audit log API responses."""
    
    id: UUID = Field(..., description="Unique audit log entry ID")
    created_at: datetime = Field(..., description="Timestamp when the audit entry was created")
    
    class Config:
        from_attributes = True


class AuditLogFilter(BaseModel):
    """Model for filtering audit log queries."""
    
    user_id: Optional[UUID] = Field(None, description="Filter by user ID")
    action: Optional[str] = Field(None, description="Filter by action type")
    resource_type: Optional[str] = Field(None, description="Filter by resource type")
    resource_id: Optional[str] = Field(None, description="Filter by resource ID")
    start_date: Optional[datetime] = Field(None, description="Filter entries after this date")
    end_date: Optional[datetime] = Field(None, description="Filter entries before this date")
    ip_address: Optional[Union[IPv4Address, IPv6Address]] = Field(None, description="Filter by IP address")
    limit: int = Field(50, ge=1, le=1000, description="Maximum number of results")
    offset: int = Field(0, ge=0, description="Number of results to skip")