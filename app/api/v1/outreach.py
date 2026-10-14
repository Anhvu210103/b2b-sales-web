"""Outreach API routes."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, get_current_active_user, PaginationParams
from app.models.outreach import (
    OutreachLog, OutreachChannel, OutreachStatus,
    OutreachTemplate, OutreachSequence, OutreachCampaign, SequenceStep
)
from app.models.user import User
from app.schemas.outreach import (
    OutreachTemplateCreate, OutreachTemplateUpdate, OutreachTemplateResponse,
    OutreachSequenceCreate, OutreachSequenceUpdate, OutreachSequenceResponse,
    OutreachCampaignCreate, OutreachCampaignUpdate, OutreachCampaignResponse,
    OutreachLogCreate, OutreachLogUpdate, OutreachLogResponse,
    OutreachSendRequest, SequenceStepCreate, SequenceStepResponse,
    OutreachCampaignResponse, OutreachLogResponse, OutreachStatsResponse,
)
from app.schemas.common import PaginatedResponse, PaginationParams

router = APIRouter()


# Templates
@router.get("/templates", response_model=PaginatedResponse[OutreachTemplateResponse])
async def list_templates(
    pagination: PaginationParams = Depends(),
    channel: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List outreach templates."""
    query = select(OutreachTemplate)
    
    if pagination.search:
        search_term = f"%{pagination.search}%"
        query = query.where(OutreachTemplate.name.ilike(pagination.search))
    
    if channel:
        query = query.where(OutreachTemplate.channel == channel)
    if is_active is not None:
        query = query.where(OutreachTemplate.is_active == is_active)
    
    query = query.order_by(OutreachTemplate.created_at.desc())
    
    total = await db.scalar(select(func.count()).select_from(
        select(OutreachTemplate).where(query.whereclause).subquery()
    )) if pagination.search or channel or is_active is not None else \
        await db.scalar(select(func.count(OutreachTemplate.id)))
    
    offset = (pagination.page - 1) * pagination.page_size
    query = query.offset(offset).limit(pagination.page_size)
    
    result = await db.execute(query)
    templates = result.scalars().all()
    
    return PaginatedResponse.create(
        items=[OutreachTemplateResponse.model_validate(t) for t in templates],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.post("/templates", response_model=OutreachTemplateResponse, status_code=201)
async def create_template(
    template_data: OutreachTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create new template."""
    template = OutreachTemplate(
        **template_data.model_dump(),
        created_by=current_user.id,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    
    return OutreachTemplateResponse.model_validate(template)


@router.get("/templates/{template_id}", response_model=OutreachTemplateResponse)
async def get_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get template by ID."""
    result = await db.execute(select(OutreachTemplate).where(OutreachTemplate.id == template_id))
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return OutreachTemplateResponse.model_validate(template)


@router.patch("/templates/{template_id}", response_model=OutreachTemplateResponse)
async def update_template(
    template_id: str,
    template_update: OutreachTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update template."""
    result = await db.execute(select(OutreachTemplate).where(OutreachTemplate.id == template_id))
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    update_data = template_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(template, field, value)
    
    await db.commit()
    await db.refresh(template)
    
    return OutreachTemplateResponse.model_validate(template)


@router.delete("/templates/{template_id}", status_code=204)
async def delete_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Delete template."""
    result = await db.execute(select(OutreachTemplate).where(OutreachTemplate.id == template_id))
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    if template.is_system:
        raise HTTPException(status_code=403, detail="Cannot delete system template")
    
    await db.delete(template)
    await db.commit()


# Sequences
@router.get("/sequences", response_model=PaginatedResponse[OutreachSequenceResponse])
async def list_sequences(
    pagination: PaginationParams = Depends(),
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List outreach sequences."""
    query = select(OutreachSequence).options(selectinload(OutreachSequence.steps))
    
    if pagination.search:
        query = query.where(OutreachSequence.name.ilike(f"%{pagination.search}%"))
    if is_active is not None:
        query = query.where(OutreachSequence.is_active == is_active)
    
    query = query.order_by(OutreachSequence.created_at.desc())
    
    total = await db.scalar(select(func.count(OutreachSequence.id)))
    
    offset = (pagination.page - 1) * pagination.page_size
    query = query.offset(offset).limit(pagination.page_size)
    
    result = await db.execute(query)
    sequences = result.scalars().all()
    
    return PaginatedResponse.create(
        items=[OutreachSequenceResponse.model_validate(s) for s in sequences],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.post("/sequences", response_model=OutreachSequenceResponse, status_code=201)
async def create_sequence(
    sequence_data: OutreachSequenceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create outreach sequence."""
    sequence = OutreachSequence(
        **sequence_data.model_dump(exclude={"steps"}),
        created_by=current_user.id,
    )
    db.add(sequence)
    await db.flush()
    
    # Add steps
    for step_data in sequence_data.steps:
        step = SequenceStep(
            sequence_id=sequence.id,
            **step_data.model_dump(),
        )
        db.add(step)
    
    await db.commit()
    await db.refresh(sequence)
    await db.refresh(sequence, attribute_names=["steps"])
    
    return OutreachSequenceResponse.model_validate(sequence)


@router.get("/sequences/{sequence_id}", response_model=OutreachSequenceResponse)
async def get_sequence(
    sequence_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get sequence with steps."""
    result = await db.execute(
        select(OutreachSequence)
        .options(selectinload(OutreachSequence.steps).selectinload(SequenceStep.template))
        .where(OutreachSequence.id == sequence_id)
    )
    sequence = result.scalar_one_or_none()
    
    if not sequence:
        raise HTTPException(status_code=404, detail="Sequence not found")
    
    return OutreachSequenceResponse.model_validate(sequence)


@router.post("/send", response_model=dict)
async def send_outreach(
    request: OutreachSendRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Send outreach (email, Zalo, LinkedIn)."""
    from app.services.outreach_service import OutreachService
    
    service = OutreachService(db)
    result = await service.send_outreach(
        lead_ids=request.lead_ids,
        channel=request.channel,
        template_id=request.template_id,
        sequence_id=request.sequence_id,
        campaign_id=request.campaign_id,
        custom_subject=request.custom_subject,
        custom_body=request.custom_body,
        send_immediately=request.send_immediately,
        scheduled_at=request.scheduled_at,
        track_opens=request.track_opens,
        track_clicks=request.track_clicks,
        sender=current_user,
    )
    
    return result


@router.get("/logs", response_model=PaginatedResponse[OutreachLogResponse])
async def list_outreach_logs(
    pagination: PaginationParams = Depends(),
    lead_id: Optional[str] = None,
    channel: Optional[str] = None,
    status: Optional[str] = None,
    campaign_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List outreach logs."""
    query = select(OutreachLog).options(selectinload(OutreachLog.lead))
    
    if lead_id:
        query = query.where(OutreachLog.lead_id == lead_id)
    if channel:
        query = query.where(OutreachLog.channel == channel)
    if status:
        query = query.where(OutreachLog.status == status)
    if campaign_id:
        query = query.where(OutreachLog.campaign_id == campaign_id)
    
    query = query.order_by(OutreachLog.created_at.desc())
    
    total = await db.scalar(select(func.count(OutreachLog.id)))
    
    offset = (pagination.page - 1) * pagination.page_size
    query = query.offset(offset).limit(pagination.page_size)
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return PaginatedResponse.create(
        items=[OutreachLogResponse.model_validate(l) for l in logs],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/stats", response_model=OutreachStatsResponse)
async def get_outreach_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get outreach statistics."""
    from app.services.outreach_service import OutreachService
    
    service = OutreachService(db)
    stats = await service.get_stats()
    return stats


# Campaigns
@router.get("/campaigns", response_model=PaginatedResponse[OutreachCampaignResponse])
async def list_campaigns(
    pagination: PaginationParams = Depends(),
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List outreach campaigns."""
    query = select(OutreachCampaign)
    
    if pagination.search:
        query = query.where(OutreachCampaign.name.ilike(f"%{pagination.search}%"))
    if status:
        query = query.where(OutreachCampaign.status == status)
    
    query = query.order_by(OutreachCampaign.created_at.desc())
    
    total = await db.scalar(select(func.count(OutreachCampaign.id)))
    
    offset = (pagination.page - 1) * pagination.page_size
    query = query.offset(offset).limit(pagination.page_size)
    
    result = await db.execute(query)
    campaigns = result.scalars().all()
    
    return PaginatedResponse.create(
        items=[OutreachCampaignResponse.model_validate(c) for c in campaigns],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.post("/campaigns", response_model=OutreachCampaignResponse, status_code=201)
async def create_campaign(
    campaign_data: OutreachCampaignCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create outreach campaign."""
    campaign = OutreachCampaign(
        **campaign_data.model_dump(),
        created_by=current_user.id,
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    
    return OutreachCampaignResponse.model_validate(campaign)


@router.post("/campaigns/{campaign_id}/start")
async def start_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Start a campaign."""
    from app.services.outreach_service import OutreachService
    
    service = OutreachService(db)
    result = await service.start_campaign(campaign_id)
    return result


@router.post("/campaigns/{campaign_id}/pause")
async def pause_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Pause a campaign."""
    result = await db.execute(select(OutreachCampaign).where(OutreachCampaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    campaign.status = "paused"
    await db.commit()
    
    return {"message": "Campaign paused"}


@router.post("/campaigns/{campaign_id}/resume")
async def resume_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Resume a paused campaign."""
    result = await db.execute(select(OutreachCampaign).where(OutreachCampaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    campaign.status = "running"
    await db.commit()
    
    return {"message": "Campaign resumed"}
