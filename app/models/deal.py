"""Deal pipeline models."""

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
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DealStage(str, enum.Enum):
    """Deal pipeline stages."""

    LEAD = "lead"
    QUALIFIED = "qualified"
    DEMO_SCHEDULED = "demo_scheduled"
    DEMO_COMPLETED = "demo_completed"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    CONTRACT = "contract"
    WON = "won"
    LOST = "lost"
    ON_HOLD = "on_hold"


class ActivityType(str, enum.Enum):
    """Types of activities."""

    EMAIL = "email"
    CALL = "call"
    MEETING = "meeting"
    DEMO = "demo"
    NOTE = "note"
    TASK = "task"
    EMAIL_SENT = "email_sent"
    EMAIL_OPENED = "email_opened"
    EMAIL_CLICKED = "email_clicked"
    EMAIL_REPLIED = "email_replied"
    LINKEDIN_CONNECT = "linkedin_connect"
    LINKEDIN_MESSAGE = "linkedin_message"
    ZALO_MESSAGE = "zalo_message"
    MEETING_SCHEDULED = "meeting_scheduled"
    MEETING_COMPLETED = "meeting_completed"
    DEMO_SCHEDULED = "demo_scheduled"
    DEMO_COMPLETED = "demo_completed"
    PROPOSAL_SENT = "proposal_sent"
    CONTRACT_SENT = "contract_sent"
    CONTRACT_SIGNED = "contract_signed"
    PAYMENT_RECEIVED = "payment_received"
    NOTE_ADDED = "note_added"
    STATUS_CHANGED = "status_changed"
    ASSIGNED = "assigned"
    OTHER = "other"


class Deal(Base):
    """Deal / Opportunity model."""

    __tablename__ = "deals"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    
    # Lead reference
    lead_id: Mapped[UUID] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # Deal info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Pipeline
    stage: Mapped[DealStage] = mapped_column(
        Enum(DealStage), nullable=False, default=DealStage.LEAD, index=True
    )
    stage_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    
    # Value
    value: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="VND")
    probability: Mapped[int] = mapped_column(default=10)  # 0-100%
    
    # Dates
    expected_close_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    actual_close_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    # Source
    source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    campaign_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("outreach_campaigns.id"), nullable=True
    )
    
    # Assignment
    assigned_to: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    
    # Metadata
    tags: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)
    custom_fields: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    loss_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    competitor: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    
    # Relationships
    lead: Mapped["Lead"] = relationship("Lead", back_populates="deals")
    assigned_user: Mapped[Optional["User"]] = relationship(
        "User", back_populates="assigned_deals", foreign_keys=[assigned_to]
    )
    activities: Mapped[list["DealActivity"]] = relationship(
        "DealActivity", back_populates="deal", cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        Index("ix_deals_stage_assigned", "stage", "assigned_to"),
        Index("ix_deals_expected_close", "expected_close_date"),
        Index("ix_deals_value_stage", "value", "stage"),
    )

    def __repr__(self) -> str:
        return f"<Deal(id={self.id}, name={self.name}, stage={self.stage}, value={self.value})>"


class DealActivity(Base):
    """Activity log for deals."""

    __tablename__ = "deal_activities"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    
    # References
    deal_id: Mapped[UUID] = mapped_column(
        ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lead_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), nullable=True, index=True
    )
    
    # Activity info
    type: Mapped[ActivityType] = mapped_column(
        Enum(ActivityType), nullable=False, index=True
    )
    subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Metadata
    metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Outcome
    outcome: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # e.g., "scheduled", "completed", "no_answer", "voicemail"
    
    # Timing
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_minutes: Mapped[Optional[int]] = mapped_column(nullable=True)
    
    # Assignment
    created_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    assigned_to: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    due_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Related objects
    outreach_log_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("outreach_logs.id"), nullable=True
    )
    meeting_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    
    # Relationships
    deal: Mapped["Deal"] = relationship("Deal", back_populates="activities")
    lead: Mapped[Optional["Lead"]] = relationship("Lead", back_populates="activities")
    creator: Mapped[Optional["User"]] = relationship(
        "User", back_populates="created_activities", foreign_keys=[created_by]
    )
    assignee: Mapped[Optional["User"]] = relationship(
        "User", back_populates="assigned_activities", foreign_keys=[assigned_to]
    )
    outreach_log: Mapped[Optional["OutreachLog"]] = relationship("OutreachLog")

    __table_args__ = (
        Index("ix_activities_deal_type", "deal_id", "type"),
        Index("ix_activities_due", "due_at"),
        Index("ix_activities_created_by", "created_by"),
    )

    def __repr__(self) -> str:
        return f"<DealActivity(id={self.id}, deal={self.deal_id}, type={self.type})>"


class LeadList(Base):
    """Static or dynamic lists of leads for campaigns."""

    __tablename__ = "lead_lists"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Dynamic list criteria (if not static)
    is_dynamic: Mapped[bool] = mapped_column(default=False)
    filters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Static members (if not dynamic)
    lead_ids: Mapped[Optional[list[UUID]]] = mapped_column(JSON, nullable=True)
    
    # Stats
    total_count: Mapped[int] = mapped_column(default=0)
    
    created_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<LeadList(id={self.id}, name={self.name}, dynamic={self.is_dynamic})>"