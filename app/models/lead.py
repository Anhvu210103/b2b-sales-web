"""Lead models."""

import enum
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LeadSource(str, enum.Enum):
    """Source of the lead."""

    YELLOWPAGES = "yellowpages"
    VIETNAMWORKS = "vietnamworks"
    TOP_CV = "topcv"
    APOLLO = "apollo"
    LINKEDIN = "linkedin"
    FACEBOOK = "facebook"
    NEWS_SIGNALS = "news_signals"
    ASSOCIATION = "association"
    PORTFOLIO = "portfolio"
    CRT_SH = "crt_sh"
    WHOIS = "whois"
    YEARBOOK = "yearbook"
    PARTNER_REFERRAL = "partner_referral"
    MANUAL = "manual"
    OTHER = "other"


class LeadStatus(str, enum.Enum):
    """Current status of the lead."""

    NEW = "new"
    ENRICHED = "enriched"
    CONTACTED = "contacted"
    REPLIED = "replied"
    INTERESTED = "interested"
    DEMO_SCHEDULED = "demo_scheduled"
    DEMO_COMPLETED = "demo_completed"
    PROPOSAL_SENT = "proposal_sent"
    NEGOTIATING = "negotiating"
    WON = "won"
    LOST = "lost"
    UNQUALIFIED = "unqualified"
    BOUNCED = "bounced"
    OPTED_OUT = "opted_out"


class CompanySize(str, enum.Enum):
    """Company size categories."""

    MICRO = "1-10"
    SMALL = "11-50"
    MEDIUM = "51-200"
    LARGE = "201-500"
    ENTERPRISE = "500+"


class Lead(Base):
    """Lead / Company model."""

    __tablename__ = "leads"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    
    # Basic info
    company_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    website: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Company details
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    company_size: Mapped[Optional[CompanySize]] = mapped_column(
        Enum(CompanySize), nullable=True, index=True
    )
    employee_count: Mapped[Optional[int]] = mapped_column(nullable=True)
    revenue_range: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Location
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    district: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Source tracking
    source: Mapped[LeadSource] = mapped_column(
        Enum(LeadSource), nullable=False, default=LeadSource.MANUAL, index=True
    )
    source_details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Status
    status: Mapped[LeadStatus] = mapped_column(
        Enum(LeadStatus), nullable=False, default=LeadStatus.NEW, index=True
    )
    status_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Enrichment data
    enrichment_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    facebook_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Contact info (best available)
    primary_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    primary_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    primary_contact_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    primary_contact_title: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # All contacts (enriched)
    contacts: Mapped[Optional[list[dict]]] = mapped_column(JSON, nullable=True)
    
    # Signals
    signals: Mapped[Optional[list[dict]]] = mapped_column(JSON, nullable=True)
    signal_score: Mapped[float] = mapped_column(default=0.0)
    
    # Scoring
    fit_score: Mapped[float] = mapped_column(default=0.0)  # How well they fit ICP
    intent_score: Mapped[float] = mapped_column(default=0.0)  # Buying signals
    engagement_score: Mapped[float] = mapped_column(default=0.0)  # Outreach engagement
    
    # Ownership
    assigned_to: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    
    # Tags
    tags: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)
    
    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    last_contacted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_followup_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    
    # Relationships
    assigned_user: Mapped[Optional["User"]] = relationship(
        "User", back_populates="assigned_leads", foreign_keys=[assigned_to]
    )
    outreach_logs: Mapped[list["OutreachLog"]] = relationship(
        "OutreachLog", back_populates="lead", cascade="all, delete-orphan"
    )
    deals: Mapped[list["Deal"]] = relationship(
        "Deal", back_populates="lead", cascade="all, delete-orphan"
    )
    activities: Mapped[list["DealActivity"]] = relationship(
        "DealActivity", back_populates="lead", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_leads_status_source", "status", "source"),
        Index("ix_leads_assigned_status", "assigned_to", "status"),
        Index("ix_leads_next_followup", "next_followup_at"),
    )

    def __repr__(self) -> str:
        return f"<Lead(id={self.id}, company={self.company_name}, status={self.status})>"