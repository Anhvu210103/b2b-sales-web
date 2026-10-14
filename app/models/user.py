"""User and authentication models."""

import enum
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    """User roles in the system."""

    ADMIN = "admin"
    MANAGER = "manager"
    SALES_REP = "sales_rep"
    SDR = "sdr"
    VIEWER = "viewer"


class User(Base):
    """User model."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    
    # Auth
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    is_superuser: Mapped[bool] = mapped_column(default=False)
    
    # Profile
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Role
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole), nullable=False, default=UserRole.SDR, index=True
    )
    
    # Department/Team
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    manager_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    
    # Settings
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Ho_Chi_Minh")
    language: Mapped[str] = mapped_column(String(10), default="vi")
    notifications_enabled: Mapped[bool] = mapped_column(default=True)
    
    # Email signatures
    email_signature: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Calendar integration
    google_calendar_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    outlook_calendar_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # LinkedIn/Zalo tokens
    linkedin_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    zalo_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Stats
    total_leads_assigned: Mapped[int] = mapped_column(default=0)
    total_deals_won: Mapped[int] = mapped_column(default=0)
    total_revenue: Mapped[float] = mapped_column(default=0.0)
    
    # Timestamps
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    
    # Relationships
    assigned_leads: Mapped[list["Lead"]] = relationship(
        "Lead", back_populates="assigned_user", foreign_keys="Lead.assigned_to"
    )
    assigned_deals: Mapped[list["Deal"]] = relationship(
        "Deal", back_populates="assigned_user", foreign_keys="Deal.assigned_to"
    )
    created_activities: Mapped[list["DealActivity"]] = relationship(
        "DealActivity", back_populates="creator", foreign_keys="DealActivity.created_by"
    )
    assigned_activities: Mapped[list["DealActivity"]] = relationship(
        "DealActivity", back_populates="assignee", foreign_keys="DealActivity.assigned_to"
    )
    managed_users: Mapped[list["User"]] = relationship(
        "User", back_populates="manager", foreign_keys="User.manager_id"
    )
    manager: Mapped[Optional["User"]] = relationship(
        "User", back_populates="managed_users", foreign_keys="User.manager_id", remote_side="User.id"
    )
    sent_outreach: Mapped[list["OutreachLog"]] = relationship(
        "OutreachLog", back_populates="sender", foreign_keys="OutreachLog.sent_by"
    )
    created_templates: Mapped[list["OutreachTemplate"]] = relationship(
        "OutreachTemplate", foreign_keys="OutreachTemplate.created_by"
    )
    created_sequences: Mapped[list["OutreachSequence"]] = relationship(
        "OutreachSequence", foreign_keys="OutreachSequence.created_by"
    )
    created_campaigns: Mapped[list["OutreachCampaign"]] = relationship(
        "OutreachCampaign", foreign_keys="OutreachCampaign.created_by"
    )
    created_leads: Mapped[list["LeadList"]] = relationship(
        "LeadList", foreign_keys="LeadList.created_by"
    )
    
    __table_args__ = (
        Index("ix_users_email_active", "email", "is_active"),
        Index("ix_users_role_active", "role", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"


class AuditLog(Base):
    """Audit trail for important actions."""

    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    
    # Actor
    user_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    user_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Action
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # e.g., "lead.created", "deal.stage_changed", "email.sent"
    
    # Target
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource_id: Mapped[Optional[UUID]] = mapped_column(nullable=True, index=True)
    
    # Details
    old_values: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    new_values: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)
    
    # Context
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    
    # Relationships
    user: Mapped[Optional["User"]] = relationship("User")

    __table_args__ = (
        Index("ix_audit_logs_user_action", "user_id", "action"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
        Index("ix_audit_logs_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog(action={self.action}, resource={self.resource_type}:{self.resource_id})>"