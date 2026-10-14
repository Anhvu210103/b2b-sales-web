"""Outreach schemas."""

from datetime import datetime
from typing import Optional, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, EmailStr, HttpUrl

from app.models.outreach import OutreachChannel, OutreachStatus
from app.schemas.common import PaginatedResponse


# Templates
class OutreachTemplateBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    channel: Any
    subject: Optional[str] = Field(None, max_length=500)
    body: str = Field(..., min_length=1)
    
    variables: Optional[list[str]] = None
    variable_examples: Optional[dict] = None
    
    industry: Optional[str] = Field(None, max_length=100)
    company_size: Optional[str] = Field(None, max_length=50)
    job_titles: Optional[list[str]] = None
    
    is_active: bool = True
    language: str = "vi"


class OutreachTemplateCreate(OutreachTemplateBase):
    pass


class OutreachTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    channel: Optional[Any] = None
    subject: Optional[str] = Field(None, max_length=500)
    body: Optional[str] = None
    
    variables: Optional[list[str]] = None
    variable_examples: Optional[dict] = None
    
    industry: Optional[str] = Field(None, max_length=100)
    company_size: Optional[str] = Field(None, max_length=50)
    job_titles: Optional[list[str]] = None
    
    is_active: Optional[bool] = None
    language: Optional[str] = None


class OutreachTemplateResponse(OutreachTemplateBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    is_system: bool = False
    sent_count: int = 0
    open_rate: float = 0.0
    reply_rate: float = 0.0
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


# Sequences
class SequenceStepCreate(BaseModel):
    step_number: int = Field(..., ge=1)
    channel: Any
    template_id: Optional[UUID] = None
    
    custom_subject: Optional[str] = Field(None, max_length=500)
    custom_body: Optional[str] = None
    
    delay_days: int = Field(default=0, ge=0)
    send_time: Optional[str] = Field(None, pattern=r"^([01]\d|2[0-3]):([0-5]\d)$")
    
    condition: Optional[str] = None
    is_active: bool = True


class SequenceStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    sequence_id: UUID
    step_number: int
    channel: Any
    template_id: Optional[UUID] = None
    custom_subject: Optional[str] = None
    custom_body: Optional[str] = None
    delay_days: int
    send_time: Optional[str] = None
    condition: Optional[str] = None
    is_active: bool = True


class OutreachSequenceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    is_active: bool = True
    max_steps: int = Field(default=3, ge=1, le=10)
    
    step_delays: list[int] = Field(default=[0, 3, 7])
    
    target_industries: Optional[list[str]] = None
    target_company_sizes: Optional[list[str]] = None
    target_titles: Optional[list[str]] = None


class OutreachSequenceCreate(OutreachSequenceBase):
    steps: list[SequenceStepCreate] = Field(default_factory=list)


class OutreachSequenceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    max_steps: Optional[int] = Field(None, ge=1, le=10)
    step_delays: Optional[list[int]] = None
    target_industries: Optional[list[str]] = None
    target_company_sizes: Optional[list[str]] = None
    target_titles: Optional[list[str]] = None


class OutreachSequenceResponse(OutreachSequenceBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    total_enrolled: int = 0
    completion_rate: float = 0.0
    reply_rate: float = 0.0
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    steps: list[SequenceStepResponse] = Field(default_factory=list)


# Campaigns
class OutreachCampaignBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    sequence_id: Optional[UUID] = None
    channel: Any
    
    lead_filters: Optional[dict] = None
    lead_list_id: Optional[UUID] = None
    
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    send_time: str = "09:00"
    timezone: str = "Asia/Ho_Chi_Minh"
    days_of_week: list[int] = [0, 1, 2, 3, 4]
    
    daily_limit: int = Field(default=30, ge=1, le=200)
    max_per_lead: int = Field(default=1, ge=1, le=5)


class OutreachCampaignCreate(OutreachCampaignBase):
    pass


class OutreachCampaignUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    sequence_id: Optional[UUID] = None
    channel: Optional[Any] = None
    lead_filters: Optional[dict] = None
    lead_list_id: Optional[UUID] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    send_time: Optional[str] = None
    timezone: Optional[str] = None
    days_of_week: Optional[list[int]] = None
    daily_limit: Optional[int] = Field(None, ge=1, le=200)
    max_per_lead: Optional[int] = Field(None, ge=1, le=5)
    status: Optional[str] = None


class OutreachCampaignResponse(OutreachCampaignBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    status: str
    total_leads: int = 0
    sent_count: int = 0
    delivered_count: int = 0
    opened_count: int = 0
    replied_count: int = 0
    bounced_count: int = 0
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# Logs
class OutreachLogBase(BaseModel):
    lead_id: UUID
    channel: Any
    sequence_id: Optional[UUID] = None
    step_number: int = 1
    
    recipient_email: Optional[EmailStr] = None
    recipient_phone: Optional[str] = Field(None, max_length=50)
    recipient_name: Optional[str] = Field(None, max_length=100)
    recipient_linkedin: Optional[str] = None
    
    subject: Optional[str] = Field(None, max_length=500)
    body: Optional[str] = None
    template_id: Optional[UUID] = None
    personalization_data: Optional[dict] = None


class OutreachLogCreate(OutreachLogBase):
    pass


class OutreachLogUpdate(BaseModel):
    status: Optional[Any] = None
    error_message: Optional[str] = None
    external_id: Optional[str] = None
    thread_id: Optional[str] = None
    in_reply_to: Optional[str] = None


class OutreachLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    lead_id: UUID
    channel: Any
    sequence_id: Optional[UUID] = None
    step_number: int
    
    recipient_email: Optional[EmailStr] = None
    recipient_phone: Optional[str] = None
    recipient_name: Optional[str] = None
    recipient_linkedin: Optional[str] = None
    
    subject: Optional[str] = None
    body: Optional[str] = None
    template_id: Optional[UUID] = None
    personalization_data: Optional[dict] = None
    
    status: Any
    error_message: Optional[str] = None
    external_id: Optional[str] = None
    thread_id: Optional[str] = None
    in_reply_to: Optional[str] = None
    
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    clicked_at: Optional[datetime] = None
    replied_at: Optional[datetime] = None
    
    open_count: int = 0
    click_count: int = 0
    reply_count: int = 0
    
    sent_by: Optional[UUID] = None
    campaign_id: Optional[UUID] = None
    
    created_at: datetime
    updated_at: datetime
    scheduled_at: Optional[datetime] = None


class OutreachSendRequest(BaseModel):
    """Request to send outreach (single or bulk)."""
    
    lead_ids: list[str]
    channel: Any
    template_id: Optional[UUID] = None
    sequence_id: Optional[UUID] = None
    campaign_id: Optional[UUID] = None
    
    # Override content
    custom_subject: Optional[str] = None
    custom_body: Optional[str] = None
    
    # Scheduling
    send_immediately: bool = True
    scheduled_at: Optional[datetime] = None
    
    # Tracking
    track_opens: bool = True
    track_clicks: bool = True


class OutreachStatsResponse(BaseModel):
    total_sent: int = 0
    total_delivered: int = 0
    total_opened: int = 0
    total_clicked: int = 0
    total_replied: int = 0
    total_bounced: int = 0
    open_rate: float = 0.0
    click_rate: float = 0.0
    reply_rate: float = 0.0
    bounce_rate: float = 0.0
    
    by_channel: dict[str, dict] = {}
    by_template: dict[str, dict] = {}
    by_campaign: dict[str, dict] = {}
