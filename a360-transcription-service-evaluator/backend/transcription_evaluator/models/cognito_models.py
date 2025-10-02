"""Database models for Cognito-integrated transcription evaluator.

This module defines SQLAlchemy models that integrate with AWS Cognito
for authentication while maintaining application-specific data in PostgreSQL.
All user references use Cognito sub (UUID) instead of local user IDs.
"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey, Integer, 
    JSON, Numeric, String, Text, CheckConstraint, Index
)
from sqlalchemy.dialects.postgresql import INET, UUID as PGUUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func

Base = declarative_base()


class UserProfile(Base):
    """User profile table storing application-specific data.
    
    References Cognito users by their sub claim (UUID) instead of
    storing authentication data locally.
    """
    
    __tablename__ = "user_profiles"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    cognito_user_id = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    department = Column(String(100))
    role_level = Column(Integer, CheckConstraint('role_level BETWEEN 1 AND 4'))
    preferences = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    
    # Relationships
    created_scripts = relationship("Script", back_populates="creator", foreign_keys="Script.created_by_cognito_id")
    audio_recordings = relationship("AudioRecording", back_populates="recorder")
    evaluations = relationship("Evaluation", back_populates="evaluator")
    assigned_tasks = relationship("ScriptAssignment", back_populates="assignee", foreign_keys="ScriptAssignment.assigned_to_cognito_id")
    created_assignments = relationship("ScriptAssignment", back_populates="assigner", foreign_keys="ScriptAssignment.assigned_by_cognito_id")
    
    @validates('email')
    def validate_email(self, key: str, address: str) -> str:
        """Validate email format."""
        if '@' not in address:
            raise ValueError("Invalid email address")
        return address.lower()
    
    @validates('role_level')
    def validate_role_level(self, key: str, level: int) -> int:
        """Validate role level is within allowed range."""
        if not 1 <= level <= 4:
            raise ValueError("Role level must be between 1 and 4")
        return level
    
    def __repr__(self) -> str:
        return f"<UserProfile(cognito_id='{self.cognito_user_id}', email='{self.email}')>"


class Script(Base):
    """Script content for voice actor recordings."""
    
    __tablename__ = "scripts"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    medical_vertical = Column(String(100))
    difficulty_level = Column(Integer, CheckConstraint('difficulty_level BETWEEN 1 AND 5'))
    estimated_duration_seconds = Column(Integer)
    created_by_cognito_id = Column(String(255), ForeignKey('user_profiles.cognito_user_id'), nullable=False, index=True)
    status = Column(
        Enum('draft', 'active', 'archived', 'under_review', name='script_status'),
        default='draft'
    )
    script_metadata = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    creator = relationship("UserProfile", back_populates="created_scripts", foreign_keys=[created_by_cognito_id])
    audio_recordings = relationship("AudioRecording", back_populates="script", cascade="all, delete-orphan")
    assignments = relationship("ScriptAssignment", back_populates="script", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_scripts_status', 'status'),
        Index('idx_scripts_medical_vertical', 'medical_vertical'),
        Index('idx_scripts_difficulty_level', 'difficulty_level'),
    )
    
    @validates('difficulty_level')
    def validate_difficulty(self, key: str, level: int) -> int:
        """Validate difficulty level is within allowed range."""
        if level is not None and not 1 <= level <= 5:
            raise ValueError("Difficulty level must be between 1 and 5")
        return level
    
    @validates('estimated_duration_seconds')
    def validate_duration(self, key: str, duration: int) -> int:
        """Validate duration is positive."""
        if duration is not None and duration <= 0:
            raise ValueError("Duration must be positive")
        return duration
    
    def __repr__(self) -> str:
        return f"<Script(id='{self.id}', title='{self.title}', status='{self.status}')>"


class AudioRecording(Base):
    """Audio recordings of scripts."""
    
    __tablename__ = "audio_recordings"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    script_id = Column(PGUUID(as_uuid=True), ForeignKey('scripts.id'), nullable=False, index=True)
    recorded_by_cognito_id = Column(String(255), ForeignKey('user_profiles.cognito_user_id'), nullable=False, index=True)
    s3_bucket = Column(String(255), nullable=False)
    s3_key = Column(String(1000), nullable=False)
    file_size_bytes = Column(Integer)
    duration_seconds = Column(Numeric(10, 3))
    audio_format = Column(String(20))
    sample_rate = Column(Integer)
    recording_quality = Column(String(20))
    audio_metadata = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    script = relationship("Script", back_populates="audio_recordings")
    recorder = relationship("UserProfile", back_populates="audio_recordings")
    transcriptions = relationship("Transcription", back_populates="audio_recording", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_recordings_s3_location', 's3_bucket', 's3_key'),
    )
    
    @property
    def s3_url(self) -> str:
        """Generate S3 URL for the recording."""
        return f"s3://{self.s3_bucket}/{self.s3_key}"
    
    @validates('file_size_bytes')
    def validate_file_size(self, key: str, size: int) -> int:
        """Validate file size is positive."""
        if size is not None and size <= 0:
            raise ValueError("File size must be positive")
        return size
    
    def __repr__(self) -> str:
        return f"<AudioRecording(id='{self.id}', script_id='{self.script_id}', format='{self.audio_format}')>"


class Transcription(Base):
    """Transcriptions generated by ASR services."""
    
    __tablename__ = "transcriptions"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    audio_recording_id = Column(PGUUID(as_uuid=True), ForeignKey('audio_recordings.id'), nullable=False, index=True)
    transcription_service = Column(String(50), nullable=False, index=True)
    transcription_text = Column(Text, nullable=False)
    confidence_score = Column(Numeric(5, 4))
    word_level_timestamps = Column(JSON)
    service_metadata = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    audio_recording = relationship("AudioRecording", back_populates="transcriptions")
    evaluations = relationship("Evaluation", back_populates="transcription", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_transcriptions_service', 'transcription_service'),
        Index('idx_transcriptions_confidence', 'confidence_score'),
    )
    
    @validates('confidence_score')
    def validate_confidence(self, key: str, score: Decimal) -> Decimal:
        """Validate confidence score is between 0 and 1."""
        if score is not None and not 0 <= score <= 1:
            raise ValueError("Confidence score must be between 0 and 1")
        return score
    
    def __repr__(self) -> str:
        return f"<Transcription(id='{self.id}', service='{self.transcription_service}', confidence={self.confidence_score})>"


class Evaluation(Base):
    """Quality evaluations of transcriptions."""
    
    __tablename__ = "evaluations"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    transcription_id = Column(PGUUID(as_uuid=True), ForeignKey('transcriptions.id'), nullable=False, index=True)
    evaluator_cognito_id = Column(String(255), ForeignKey('user_profiles.cognito_user_id'), nullable=False, index=True)
    evaluation_type = Column(
        Enum('accuracy', 'pronunciation', 'fluency', 'overall', name='evaluation_type'),
        nullable=False
    )
    score = Column(Numeric(5, 2), CheckConstraint('score BETWEEN 0 AND 100'))
    detailed_feedback = Column(Text)
    corrections = Column(JSON)  # Suggested corrections
    evaluation_criteria = Column(JSON, default=dict)
    time_spent_seconds = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    transcription = relationship("Transcription", back_populates="evaluations")
    evaluator = relationship("UserProfile", back_populates="evaluations")
    
    # Indexes
    __table_args__ = (
        Index('idx_evaluations_type', 'evaluation_type'),
        Index('idx_evaluations_score', 'score'),
    )
    
    @validates('score')
    def validate_score(self, key: str, score: Decimal) -> Decimal:
        """Validate score is between 0 and 100."""
        if score is not None and not 0 <= score <= 100:
            raise ValueError("Score must be between 0 and 100")
        return score
    
    def __repr__(self) -> str:
        return f"<Evaluation(id='{self.id}', type='{self.evaluation_type}', score={self.score})>"


class ScriptAssignment(Base):
    """Script assignments for workflow management."""
    
    __tablename__ = "script_assignments"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    script_id = Column(PGUUID(as_uuid=True), ForeignKey('scripts.id'), nullable=False, index=True)
    assigned_to_cognito_id = Column(String(255), ForeignKey('user_profiles.cognito_user_id'), nullable=False, index=True)
    assigned_by_cognito_id = Column(String(255), ForeignKey('user_profiles.cognito_user_id'), nullable=False, index=True)
    assignment_type = Column(
        Enum('record', 'evaluate', 'review', name='assignment_type'),
        nullable=False
    )
    status = Column(
        Enum('pending', 'in_progress', 'completed', 'skipped', name='assignment_status'),
        default='pending'
    )
    priority = Column(Integer, CheckConstraint('priority BETWEEN 1 AND 5'), default=3)
    due_date = Column(DateTime(timezone=True))
    notes = Column(Text)
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    script = relationship("Script", back_populates="assignments")
    assignee = relationship("UserProfile", back_populates="assigned_tasks", foreign_keys=[assigned_to_cognito_id])
    assigner = relationship("UserProfile", back_populates="created_assignments", foreign_keys=[assigned_by_cognito_id])
    
    # Indexes
    __table_args__ = (
        Index('idx_assignments_status', 'status'),
        Index('idx_assignments_type', 'assignment_type'),
        Index('idx_assignments_due_date', 'due_date'),
    )
    
    @validates('priority')
    def validate_priority(self, key: str, priority: int) -> int:
        """Validate priority is within allowed range."""
        if priority is not None and not 1 <= priority <= 5:
            raise ValueError("Priority must be between 1 and 5")
        return priority
    
    def __repr__(self) -> str:
        return f"<ScriptAssignment(id='{self.id}', type='{self.assignment_type}', status='{self.status}')>"


class AuditLog(Base):
    """Audit log for tracking changes."""
    
    __tablename__ = "audit_logs"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    table_name = Column(String(100), nullable=False)
    record_id = Column(PGUUID(as_uuid=True), nullable=False)
    action = Column(Enum('INSERT', 'UPDATE', 'DELETE', name='audit_action'), nullable=False)
    old_values = Column(JSON)
    new_values = Column(JSON)
    changed_by_cognito_id = Column(String(255))  # Optional - might be system changes
    changed_at = Column(DateTime(timezone=True), server_default=func.now())
    ip_address = Column(INET)
    user_agent = Column(Text)
    
    # Indexes
    __table_args__ = (
        Index('idx_audit_logs_table_record', 'table_name', 'record_id'),
        Index('idx_audit_logs_changed_by', 'changed_by_cognito_id'),
        Index('idx_audit_logs_changed_at', 'changed_at'),
    )
    
    def __repr__(self) -> str:
        return f"<AuditLog(id='{self.id}', table='{self.table_name}', action='{self.action}')>"


class SystemSettings(Base):
    """System configuration settings."""
    
    __tablename__ = "system_settings"
    
    key = Column(String(255), primary_key=True)
    value = Column(JSON, nullable=False)
    description = Column(Text)
    updated_by_cognito_id = Column(String(255), ForeignKey('user_profiles.cognito_user_id'))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationship
    updated_by = relationship("UserProfile")
    
    def __repr__(self) -> str:
        return f"<SystemSettings(key='{self.key}')>"


# Helper functions for common queries
def get_user_by_cognito_id(session, cognito_user_id: str) -> Optional[UserProfile]:
    """Get user profile by Cognito user ID."""
    return session.query(UserProfile).filter(
        UserProfile.cognito_user_id == cognito_user_id
    ).first()


def get_active_scripts_by_user(session, cognito_user_id: str) -> List[Script]:
    """Get active scripts created by a user."""
    return session.query(Script).filter(
        Script.created_by_cognito_id == cognito_user_id,
        Script.status == 'active'
    ).all()


def get_pending_assignments_by_user(session, cognito_user_id: str) -> List[ScriptAssignment]:
    """Get pending assignments for a user."""
    return session.query(ScriptAssignment).filter(
        ScriptAssignment.assigned_to_cognito_id == cognito_user_id,
        ScriptAssignment.status == 'pending'
    ).order_by(ScriptAssignment.due_date.nulls_last(), ScriptAssignment.priority).all()


def get_script_with_recordings(session, script_id: UUID) -> Optional[Script]:
    """Get script with all associated recordings and transcriptions."""
    return session.query(Script).filter(
        Script.id == script_id
    ).first()  # Relationships will be loaded via lazy loading or explicit joins