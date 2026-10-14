"""User and auth schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    role: UserRole = UserRole.SDR
    department: Optional[str] = Field(None, max_length=100)
    manager_id: Optional[UUID] = None
    timezone: str = "Asia/Ho_Chi_Minh"
    language: str = "vi"
    notifications_enabled: bool = True


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)
    is_active: bool = True
    is_superuser: bool = False


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    role: Optional[UserRole] = None
    department: Optional[str] = Field(None, max_length=100)
    manager_id: Optional[UUID] = None
    timezone: Optional[str] = None
    language: Optional[str] = None
    notifications_enabled: Optional[bool] = None
    is_active: Optional[bool] = None


class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    timezone: Optional[str] = None
    language: Optional[str] = None
    notifications_enabled: Optional[bool] = None
    email_signature: Optional[str] = None
    avatar_url: Optional[str] = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    email: str
    full_name: str
    phone: Optional[str] = None
    role: UserRole
    department: Optional[str] = None
    manager_id: Optional[UUID] = None
    timezone: str
    language: str
    notifications_enabled: bool
    is_active: bool
    is_superuser: bool
    avatar_url: Optional[str] = None
    email_signature: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime] = None
    
    # Stats
    total_leads_assigned: int = 0
    total_deals_won: int = 0
    total_revenue: float = 0.0


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    sub: Optional[str] = None
    role: Optional[str] = None
    exp: Optional[int] = None