"""Lead schemas."""

from datetime import datetime
from typing import Optional, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, EmailStr, HttpUrl

from app.models.lead import LeadSource, LeadStatus, CompanySize
from app.schemas.common import PaginatedResponse


class LeadBase(BaseModel):
    """Base lead fields."""
    
    company_name: str = Field(..., min_length=1, max_length=255)
    domain: Optional[str] = Field(None, max_length=255)
    website: Optional[HttpUrl] = None
    
    industry: Optional[str] = Field(None, max_length=100)
    company_size: Optional[CompanySize] = None
    employee_count: Optional[int] = Field(None, ge=0)
    revenue_range: Optional[str] = Field(None, max_length=50)
    
    city: Optional[str] = Field(None, max_length=100)
    district: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = None
    
    source: LeadSource = LeadSource.MANUAL
    source_details: Optional[dict] = None
    source_url: Optional[HttpUrl] = None
    
    tags: Optional[list[str]] = None
    notes: Optional[str] = None


class LeadCreate(LeadBase):
    """Schema for creating a lead."""
    
    # Contact info
    primary_email: Optional[EmailStr] = None
    primary_phone: Optional[str] = Field(None, max_length=50)
    primary_contact_name: Optional[str] = Field(None, max_length=100)
    primary_contact_title: Optional[str] = Field(None, max_length=100)
    
    # Assigned user
    assigned_to: Optional[UUID] = None


class LeadUpdate(BaseModel):
    """Schema for updating a lead."""
    
    company_name: Optional[str] = Field(None, min_length=1, max_length=255)
    domain: Optional[str] = Field(None, max_length=255)
    website: Optional[HttpUrl] = None
    
    industry: Optional[str] = Field(None, max_length=100)
    company_size: Optional[CompanySize] = None
    employee_count: Optional[int] = Field(None, ge=0)
    revenue_range: Optional[str] = Field(None, max_length=50)
    
    city: Optional[str] = Field(None, max_length=100)
    district: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = None
    
    source: Optional[LeadSource] = None
    source_details: Optional[dict] = None
    source_url: Optional[HttpUrl] = None
    
    status: Optional[LeadStatus] = None
    status_reason: Optional[str] = None
    
    primary_email: Optional[EmailStr] = None
    primary_phone: Optional[str] = Field(None, max_length=50)
    primary_contact_name: Optional[str] = Field(None, max_length=100)
    primary_contact_title: Optional[str] = Field(None, max_length=100)
    
    linkedin_url: Optional[str] = None
    facebook_url: Optional[str] = None
    
    contacts: Optional[list[dict]] = None
    enrichment_data: Optional[dict] = None
    signals: Optional[list[dict]] = None
    
    tags: Optional[list[str]] = None
    notes: Optional[str] = None
    assigned_to: Optional[UUID] = None


class LeadResponse(LeadBase):
    """Lead response with all fields."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    status: Any
    status_reason: Optional[str] = None
    
    primary_email: Optional[EmailStr] = None
    primary_phone: Optional[str] = None
    primary_contact_name: Optional[str] = None
    primary_contact_title: Optional[str] = None
    
    linkedin_url: Optional[str] = None
    facebook_url: Optional[str] = None
    
    contacts: Optional[list[dict]] = None
    enrichment_data: Optional[dict] = None
    signals: Optional[list[dict]] = None
    
    fit_score: float = 0.0
    intent_score: float = 0.0
    engagement_score: float = 0.0
    
    assigned_to: Optional[UUID] = None
    assigned_user_name: Optional[str] = None
    
    created_at: datetime
    updated_at: datetime
    last_contacted_at: Optional[datetime] = None
    next_followup_at: Optional[datetime] = None
    
    outreach_count: int = 0
    deal_count: int = 0
    activity_count: int = 0


class LeadListResponse(BaseModel):
    """Minimal lead info for lists."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    company_name: str
    domain: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[CompanySize] = None
    city: Optional[str] = None
    source: Any
    status: Any
    primary_email: Optional[EmailStr] = None
    assigned_to: Optional[UUID] = None
    fit_score: float = 0.0
    intent_score: float = 0.0
    created_at: datetime
    next_followup_at: Optional[datetime] = None


class LeadEnrichRequest(BaseModel):
    """Request to enrich a lead."""
    
    lead_id: UUID
    force_refresh: bool = False
    sources: Optional[list[str]] = None


class LeadScoreRequest(BaseModel):
    """Request to score a lead."""
    
    lead_id: UUID
    force_refresh: bool = False


class LeadImportRow(BaseModel):
    """Single row for CSV/Excel import."""
    
    company_name: str
    domain: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    employee_count: Optional[int] = None
    city: Optional[str] = None
    address: Optional[str] = None
    primary_email: Optional[str] = None
    primary_phone: Optional[str] = None
    primary_contact_name: Optional[str] = None
    primary_contact_title: Optional[str] = None
    source: Optional[str] = None
    tags: Optional[str] = None  # comma-separated
    notes: Optional[str] = None


class LeadExportRequest(BaseModel):
    """Request to export leads."""
    
    ids: Optional[list[str]] = None
    filters: Optional[dict] = None
    fields: Optional[list[str]] = None
    format: str = "csv"  # csv, xlsx, json
