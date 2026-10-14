"""Outreach models."""

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


class OutreachChannel(str, enum.Enum):
    """Communication channel for outreach."""

    EMAIL = "email"
    ZALO = "zalo"
    LINKEDIN = "linkedin"
    PHONE = "phone"
    FACEBOOK = "facebook"
    MEETING = "meeting"
    DEMO = "demo"
    EVENT = "event"
    OTHER = "other"


class OutreachStatus(str, enum.Enum):
    """Status of an outreach attempt."""

    PENDING = "pending"
    SCHEDULED = "scheduled"
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    CLICKED = "clicked"
    REPLIED = "replied"
    BOUNCED = "bounced"
    FAILED = "failed"
    OPTED_OUT = "opted_out"
    SKIPPED = "skipped"


class OutreachLog(Base):
    """Individual outreach attempt record."""

    __tablename__ = "outreach_logs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    
    # Lead reference
    lead_id: Mapped[UUID] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # Channel & sequence
    channel: Mapped[OutreachChannel] = mapped_column(
        Enum(OutreachChannel), nullable=False, index=True
    )
    sequence_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("outreach_sequences.id"), nullable=True, index=True
    )
    step_number: Mapped[int] = mapped_column(default=1)
    
    # Contact details
    recipient_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    recipient_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    recipient_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    recipient_linkedin: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Message content
    subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    template_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("outreach_templates.id"), nullable=True
    )
    personalization_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Status tracking
    status: Mapped[OutreachStatus] = mapped_column(
        Enum(OutreachStatus), nullable=False, default=OutreachStatus.PENDING, index=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # External IDs
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    thread_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    in_reply_to: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Tracking
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    clicked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    replied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Engagement
    open_count: Mapped[int] = mapped_column(default=0)
    click_count: Mapped[int] = mapped_column(default=0)
    reply_count: Mapped[int] = mapped_column(default=0)
    
    # Metadata
    sent_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    campaign_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("outreach_campaigns.id"), nullable=True, index=True
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    
    # Relationships
    lead: Mapped["Lead"] = relationship("Lead", back_populates="outreach_logs")
    template: Mapped[Optional["OutreachTemplate"]] = relationship("OutreachTemplate")
    sequence: Mapped[Optional["OutreachSequence"]] = relationship("OutreachSequence", back_populates="logs")
    campaign: Mapped[Optional["OutreachCampaign"]] = relationship("OutreachCampaign", back_populates="logs")
    sender: Mapped[Optional["User"]] = relationship("User", back_populates="sent_outreach", foreign_keys=[sent_by])

    __table_args__ = (
        Index("ix_outreach_logs_lead_channel", "lead_id", "channel"),
        Index("ix_outreach_logs_status_scheduled", "status", "scheduled_at"),
        Index("ix_outreach_logs_campaign", "campaign_id"),
    )

    def __repr__(self) -> str:
        return f"<OutreachLog(id={self.id}, lead={self.lead_id}, channel={self.channel}, status={self.status})>"


class OutreachTemplate(Base):
    """Message templates for outreach."""

    __tablename__ = "outreach_templates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    channel: Mapped[OutreachChannel] = mapped_column(
        Enum(OutreachChannel), nullable=False, index=True
    )
    
    # Content
    subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Variables (for personalization)
    variables: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)
    variable_examples: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Targeting
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    company_size: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    job_titles: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)
    
    # Metadata
    is_active: Mapped[bool] = mapped_column(default=True)
    is_system: Mapped[bool] = mapped_column(default=False)
    language: Mapped[str] = mapped_column(String(10), default="vi")
    
    # Performance
    sent_count: Mapped[int] = mapped_column(default=0)
    open_rate: Mapped[float] = mapped_column(default=0.0)
    reply_rate: Mapped[float] = mapped_column(default=0.0)
    
    # Ownership
    created_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_templates_channel_active", "channel", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<OutreachTemplate(id={self.id}, name={self.name}, channel={self.channel})>"


class OutreachSequence(Base):
    """Multi-step outreach sequences."""

    __tablename__ = "outreach_sequences"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Configuration
    is_active: Mapped[bool] = mapped_column(default=True)
    max_steps: Mapped[int] = mapped_column(default=3)
    
    # Timing
    step_delays: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    # e.g., [0, 3, 7] = immediate, 3 days, 7 days
    
    # Targeting
    target_industries: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)
    target_company_sizes: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)
    target_titles: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)
    
    # Performance
    total_enrolled: Mapped[int] = mapped_column(default=0)
    completion_rate: Mapped[float] = mapped_column(default=0.0)
    reply_rate: Mapped[float] = mapped_column(default=0.0)
    
    created_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    logs: Mapped[list["OutreachLog"]] = relationship(
        "OutreachLog", back_populates="sequence", cascade="all, delete-orphan"
    )
    steps: Mapped[list["SequenceStep"]] = relationship(
        "SequenceStep", back_populates="sequence", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<OutreachSequence(id={self.id}, name={self.name})>"


class SequenceStep(Base):
    """Individual step in a sequence."""

    __tablename__ = "sequence_steps"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    
    sequence_id: Mapped[UUID] = mapped_column(
        ForeignKey("outreach_sequences.id", ondelete="CASCADE"), nullable=False
    )
    
    step_number: Mapped[int] = mapped_column(nullable=False)
    channel: Mapped[OutreachChannel] = mapped_column(
        Enum(OutreachChannel), nullable=False
    )
    
    template_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("outreach_templates.id"), nullable=True
    )
    
    # Custom content (overrides template)
    custom_subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    custom_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timing
    delay_days: Mapped[int] = mapped_column(default=0)
    send_time: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)  # HH:MM
    
    # Conditions
    condition: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # e.g., "not_replied", "not_opened", "clicked_link"
    
    is_active: Mapped[bool] = mapped_column(default=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    
    sequence: Mapped["OutreachSequence"] = relationship(
        "OutreachSequence", back_populates="steps"
    )
    template: Mapped[Optional["OutreachTemplate"]] = relationship("OutreachTemplate")

    def __repr__(self) -> str:
        return f"<SequenceStep(seq={self.sequence_id}, step={self.step_number}, channel={self.channel})>"


class OutreachCampaign(Base):
    """Outreach campaign for batch operations."""

    __tablename__ = "outreach_campaigns"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Configuration
    sequence_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("outreach_sequences.id"), nullable=True
    )
    channel: Mapped[OutreachChannel] = mapped_column(
        Enum(OutreachChannel), nullable=False
    )
    
    # Targeting
    lead_filters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    lead_list_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("lead_lists.id"), nullable=True
    )
    
    # Scheduling
    start_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    send_time: Mapped[str] = mapped_column(String(5), default="09:00")
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Ho_Chi_Minh")
    days_of_week: Mapped[list[int]] = mapped_column(JSON, default=[0, 1, 2, 3, 4])  # Mon-Fri
    
    # Limits
    daily_limit: Mapped[int] = mapped_column(default=30)
    max_per_lead: Mapped[int] = mapped_column(default=1)
    
    # Status
    status: Mapped[str] = mapped_column(String(50), default="draft", index=True)
    # draft, scheduled, running, paused, completed, cancelled
    
    # Stats
    total_leads: Mapped[int] = mapped_column(default=0)
    sent_count: Mapped[int] = mapped_column(default=0)
    delivered_count: Mapped[int] = mapped_column(default=0)
    opened_count: Mapped[int] = mapped_column(default=0)
    replied_count: Mapped[int] = mapped_column(default=0)
    bounced_count: Mapped[int] = mapped_column(default=0)
    
    created_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    logs: Mapped[list["OutreachLog"]] = relationship(
        "OutreachLog", back_populates="campaign"
    )

    def __repr__(self) -> str:
        return f"<OutreachCampaign(id={self.id}, name={self.name}, status={self.status})>"
