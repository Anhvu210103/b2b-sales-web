"""Deal schemas."""

from datetime import datetime
from typing import Optional, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, EmailStr, HttpUrl

from app.models.deal import DealStage, ActivityType
from app.schemas.common import PaginatedResponse
from app.schemas.user import UserResponse


class DealBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    lead_id: UUID
    
    value: Optional[float] = Field(None, ge=0)
    currency: str = "VND"
    probability: int = Field(default=10, ge=0, le=100)
    
    expected_close_date: Optional[datetime] = None
    source: Optional[str] = Field(None, max_length=100)
    campaign_id: Optional[UUID] = None
    
    tags: Optional[list[str]] = None
    custom_fields: Optional[dict] = None
    loss_reason: Optional[str] = None
    competitor: Optional[str] = Field(None, max_length=100)


class DealCreate(DealBase):
    stage: DealStage = Field(default="lead")
    assigned_to: Optional[UUID] = None


class DealUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    stage: Optional[DealStage] = None
    value: Optional[float] = Field(None, ge=0)
    probability: Optional[int] = Field(None, ge=0, le=100)
    expected_close_date: Optional[datetime] = None
    actual_close_date: Optional[datetime] = None
    source: Optional[str] = Field(None, max_length=100)
    assigned_to: Optional[UUID] = None
    tags: Optional[list[str]] = None
    custom_fields: Optional[dict] = None
    loss_reason: Optional[str] = None
    competitor: Optional[str] = Field(None, max_length=100)


class DealStageUpdate(BaseModel):
    stage: DealStage
    loss_reason: Optional[str] = None


class DealResponse(DealBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    stage: DealStage
    stage_changed_at: datetime
    
    assigned_to: Optional[UUID] = None
    assigned_user_name: Optional[str] = None
    
    expected_close_date: Optional[datetime] = None
    actual_close_date: Optional[datetime] = None
    
    created_at: datetime
    updated_at: datetime
    
    lead_name: Optional[str] = None
    lead_email: Optional[str] = None
    assigned_user: Optional[UserResponse] = None
    activities_count: int = 0
    outreach_count: int = 0


class DealPipelineResponse(BaseModel):
    stages: dict[str, list[DealResponse]]
    totals: dict[str, int]
    values: dict[str, float]


class DealActivityBase(BaseModel):
    deal_id: UUID
    lead_id: Optional[UUID] = None
    type: ActivityType
    subject: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    metadata: Optional[dict] = None
    outcome: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(None, ge=0)
    assigned_to: Optional[UUID] = None
    due_at: Optional[datetime] = None
    meeting_url: Optional[HttpUrl] = None
    outreach_log_id: Optional[UUID] = None


class DealActivityCreate(DealActivityBase):
    pass


class DealActivityUpdate(BaseModel):
    type: Optional[ActivityType] = None
    subject: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    metadata: Optional[dict] = None
    outcome: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(None, ge=0)
    assigned_to: Optional[UUID] = None
    due_at: Optional[datetime] = None
    meeting_url: Optional[HttpUrl] = None
    completed_at: Optional[datetime] = None


class DealActivityResponse(DealActivityBase):
    metadata: Optional[dict] = Field(None, validation_alias="metadata_")
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    outcome: Optional[str] = None
    duration_minutes: Optional[int] = None
    created_by: Optional[UUID] = None
    created_by_name: Optional[str] = None
    assigned_to: Optional[UUID] = None
    assigned_user_name: Optional[str] = None
    due_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    outreach_log_id: Optional[UUID] = None
    meeting_url: Optional[str] = None
    
    created_at: datetime
    updated_at: datetime


class LeadListBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    is_dynamic: bool = False
    filters: Optional[dict] = None
    lead_ids: Optional[list[str]] = None


class LeadListCreate(LeadListBase):
    pass


class LeadListUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_dynamic: Optional[bool] = None
    filters: Optional[dict] = None
    lead_ids: Optional[list[str]] = None


class LeadListResponse(LeadListBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    total_count: int = 0
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime