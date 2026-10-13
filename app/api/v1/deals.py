"""Deals API routes."""

from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, get_current_active_user, PaginationParams
from app.models.deal import Deal, DealStage, DealActivity, ActivityType
from app.models.lead import Lead
from app.models.user import User
from app.schemas.deal import (
    DealCreate, DealUpdate, DealResponse, DealStageUpdate,
    DealActivityCreate, DealActivityUpdate, DealActivityResponse,
    DealPipelineResponse, LeadListCreate, LeadListResponse,
)
from app.schemas.common import PaginatedResponse, PaginationParams

router = APIRouter()


@router.get("", response_model=PaginatedResponse[DealResponse])
async def list_deals(
    pagination: PaginationParams = Depends(),
    stage: Optional[str] = None,
    assigned_to_me: bool = False,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List deals with filters."""
    query = select(Deal).options(
        selectinload(Deal.lead),
        selectinload(Deal.assigned_user),
    )
    
    if pagination.search:
        search_term = f"%{pagination.search}%"
        query = query.where(
            or_(
                Deal.name.ilike(f"%{pagination.search}%"),
                Deal.lead.has(Lead.company_name.ilike(f"%{pagination.search}%")),
            )
        )
    
    if stage:
        query = query.where(Deal.stage == DealStage(stage))
    if assigned_to_me:
        query = query.where(Deal.assigned_to == current_user.id)
    if min_value is not None:
        query = query.where(Deal.value >= min_value)
    if max_value is not None:
        query = query.where(Deal.value <= max_value)
    
    # Role-based access
    if current_user.role.value not in ("admin", "manager"):
        query = query.where(
            or_(Deal.assigned_to == current_user.id, Deal.assigned_to.is_(None))
        )
    
    query = query.options(
        selectinload(Deal.lead),
        selectinload(Deal.assigned_user),
        selectinload(Deal.activities),
    ).order_by(Deal.created_at.desc())
    
    total = await db.scalar(select(func.count(Deal.id)))
    
    offset = (pagination.page - 1) * pagination.page_size
    query = query.offset(offset).limit(pagination.page_size)
    
    result = await db.execute(query)
    deals = result.scalars().all()
    
    return PaginatedResponse.create(
        items=[DealResponse.model_validate(d) for d in deals],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/pipeline", response_model=DealPipelineResponse)
async def get_pipeline(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get pipeline view with deals grouped by stage."""
    query = select(Deal).options(selectinload(Deal.lead))
    
    if current_user.role.value not in ("admin", "manager"):
        query = query.where(
            or_(Deal.assigned_to == current_user.id, Deal.assigned_to.is_(None))
        )
    
    result = await db.execute(query)
    deals = result.scalars().all()
    
    stages = {}
    totals = {}
    values = {}
    
    for stage in DealStage:
        stage_deals = [d for d in deals if d.stage == stage]
        stages[stage.value] = [DealResponse.model_validate(d) for d in stage_deals]
        totals[stage.value] = len(stage_deals)
        values[stage.value] = sum(d.value or 0 for d in stage_deals)
    
    return DealPipelineResponse(
        stages=stages,
        totals=totals,
        values=values,
    )


@router.get("/stats")
async def get_deal_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get deal statistics."""
    query = select(Deal)
    
    if current_user.role.value not in ("admin", "manager"):
        query = query.where(
            or_(Deal.assigned_to == current_user.id, Deal.assigned_to.is_(None))
        )
    
    total = await db.scalar(select(func.count(Deal.id)).select_from(query.subquery()))
    
    # By stage
    stage_stats = await db.execute(
        select(Deal.stage, func.count(Deal.id), func.sum(Deal.value))
        .select_from(query.subquery())
        .group_by(Deal.stage)
    )
    by_stage = {str(s): {"count": c, "value": float(v or 0)} for s, c, v in stage_stats.all()}
    
    # Won/Lost
    won = await db.scalar(
        select(func.count(Deal.id))
        .where(and_(Deal.stage == DealStage.WON, query.whereclause))
    )
    lost = await db.scalar(
        select(func.count(Deal.id))
        .where(and_(Deal.stage == DealStage.LOST, query.whereclause))
    )
    
    total_value = await db.scalar(
        select(func.sum(Deal.value)).select_from(query.subquery())
    )
    
    return {
        "total_deals": total,
        "total_value": float(total_value or 0),
        "by_stage": by_stage,
        "won": won or 0,
        "lost": lost or 0,
        "win_rate": (won / (won + lost) * 100) if (won and lost) else 0,
    }


@router.get("/{deal_id}", response_model=DealResponse)
async def get_deal(
    deal_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get single deal with activities."""
    result = await db.execute(
        select(Deal)
        .options(
            selectinload(Deal.lead),
            selectinload(Deal.assigned_user),
            selectinload(Deal.activities).selectinload(DealActivity.creator),
            selectinload(Deal.activities).selectinload(DealActivity.assignee),
        )
        .where(Deal.id == deal_id)
    )
    deal = result.scalar_one_or_none()
    
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    
    if current_user.role.value not in ("admin", "manager"):
        if deal.assigned_to != current_user.id and deal.assigned_to is not None:
            raise HTTPException(status_code=403, detail="Not authorized")
    
    return DealResponse.model_validate(deal)


@router.post("", response_model=DealResponse, status_code=201)
async def create_deal(
    deal_data: DealCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create new deal."""
    deal = Deal(
        **deal_data.model_dump(exclude={"assigned_to"}),
        assigned_to=deal_data.assigned_to or current_user.id,
    )
    
    db.add(deal)
    await db.commit()
    await db.refresh(deal)
    
    # Audit
    from app.models.audit import AuditLog
    audit = AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        action="deal.created",
        resource_type="deal",
        resource_id=deal.id,
        new_values=deal_data.model_dump(),
    )
    db.add(audit)
    await db.commit()
    
    return DealResponse.model_validate(deal)


@router.patch("/{deal_id}", response_model=DealResponse)
async def update_deal(
    deal_id: str,
    deal_update: DealUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update deal."""
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    
    if current_user.role.value not in ("admin", "manager"):
        if deal.assigned_to != current_user.id and deal.assigned_to is not None:
            raise HTTPException(status_code=403, detail="Not authorized")
    
    update_data = deal_update.model_dump(exclude_unset=True)
    old_values = {}
    
    for field, value in update_data.items():
        old_values[field] = getattr(deal, field)
        setattr(deal, field, value)
    
    if "stage" in update_data:
        deal.stage_changed_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(deal)
    
    # Audit
    from app.models.audit import AuditLog
    audit = AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        action="deal.updated",
        resource_type="deal",
        resource_id=deal.id,
        old_values=old_values,
        new_values=update_data,
    )
    db.add(audit)
    await db.commit()
    
    return DealResponse.model_validate(deal)


@router.patch("/{deal_id}/stage")
async def update_deal_stage(
    deal_id: str,
    stage_update: DealStageUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update deal stage."""
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    
    if current_user.role.value not in ("admin", "manager"):
        if deal.assigned_to != current_user.id and deal.assigned_to is not None:
            raise HTTPException(status_code=403, detail="Not authorized")
    
    old_stage = deal.stage
    deal.stage = stage_update.stage
    deal.stage_changed_at = datetime.utcnow()
    
    if stage_update.loss_reason and deal.stage == DealStage.LOST:
        deal.loss_reason = stage_update.loss_reason
    
    await db.commit()
    await db.refresh(deal)
    
    # Activity log
    activity = DealActivity(
        deal_id=deal.id,
        lead_id=deal.lead_id,
        type=ActivityType.STATUS_CHANGED,
        subject=f"Stage changed: {old_stage.value} → {deal.stage.value}",
        description=f"Deal stage changed from {old_stage.value} to {deal.stage.value}",
        metadata={"old_stage": old_stage.value, "new_stage": deal.stage.value},
        created_by=current_user.id,
    )
    db.add(activity)
    await db.commit()
    
    return DealResponse.model_validate(deal)


@router.delete("/{deal_id}", status_code=204)
async def delete_deal(
    deal_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Delete deal (admin only)."""
    if current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    
    await db.delete(deal)
    await db.commit()


# Activities
@router.get("/{deal_id}/activities", response_model=list[DealActivityResponse])
async def get_deal_activities(
    deal_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get deal activities."""
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    
    result = await db.execute(
        select(DealActivity)
        .options(
            selectinload(DealActivity.creator),
            selectinload(DealActivity.assignee),
            selectinload(DealActivity.outreach_log),
        )
        .where(DealActivity.deal_id == deal_id)
        .order_by(DealActivity.created_at.desc())
    )
    activities = result.scalars().all()
    
    return [DealActivityResponse.model_validate(a) for a in activities]


@router.post("/{deal_id}/activities", response_model=DealActivityResponse, status_code=201)
async def create_activity(
    deal_id: str,
    activity_data: DealActivityCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Add activity to deal."""
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    
    activity = DealActivity(
        **activity_data.model_dump(exclude={"created_by", "deal_id"}),
        deal_id=deal_id,
        lead_id=deal.lead_id,
        created_by=current_user.id,
    )
    
    db.add(activity)
    await db.commit()
    await db.refresh(activity)
    
    return DealActivityResponse.model_validate(activity)


@router.patch("/activities/{activity_id}", response_model=DealActivityResponse)
async def update_activity(
    activity_id: str,
    activity_update: DealActivityUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update activity."""
    result = await db.execute(select(DealActivity).where(DealActivity.id == activity_id))
    activity = result.scalar_one_or_none()
    
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    update_data = activity_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(activity, field, value)
    
    if "completed_at" in update_data and update_data["completed_at"]:
        activity.completed_at = update_data["completed_at"]
    
    await db.commit()
    await db.refresh(activity)
    
    return DealActivityResponse.model_validate(activity)


# Lead Lists
@router.get("/lists", response_model=list[LeadListResponse])
async def list_lead_lists(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get all lead lists."""
    result = await db.execute(select(LeadList).order_by(LeadList.created_at.desc()))
    lists = result.scalars().all()
    return [LeadListResponse.model_validate(l) for l in lists]


@router.post("/lists", response_model=LeadListResponse, status_code=201)
async def create_lead_list(
    list_data: LeadListCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create lead list."""
    lead_list = LeadList(
        **list_data.model_dump(),
        created_by=current_user.id,
    )
    db.add(lead_list)
    await db.commit()
    await db.refresh(lead_list)
    
    return LeadListResponse.model_validate(lead_list)


@router.get("/lists/{list_id}", response_model=LeadListResponse)
async def get_lead_list(
    list_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get lead list."""
    result = await db.execute(select(LeadList).where(LeadList.id == list_id))
    lead_list = result.scalar_one_or_none()
    
    if not lead_list:
        raise HTTPException(status_code=404, detail="Lead list not found")
    
    return LeadListResponse.model_validate(lead_list)


@router.post("/lists/{list_id}/leads")
async def add_leads_to_list(
    list_id: str,
    lead_ids: list[str],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Add leads to list."""
    result = await db.execute(select(LeadList).where(LeadList.id == list_id))
    lead_list = result.scalar_one_or_none()
    
    if not lead_list:
        raise HTTPException(status_code=404, detail="Lead list not found")
    
    if lead_list.is_dynamic:
        raise HTTPException(status_code=400, detail="Cannot add leads to dynamic list")
    
    current_ids = set(lead_list.lead_ids or [])
    new_ids = set(lead_ids) - current_ids
    
    lead_list.lead_ids = list(current_ids | new_ids)
    lead_list.total_count = len(lead_list.lead_ids)
    
    await db.commit()
    
    return {"added": len(new_ids), "total": lead_list.total_count}


@router.delete("/lists/{list_id}/leads/{lead_id}")
async def remove_lead_from_list(
    list_id: str,
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Remove lead from list."""
    result = await db.execute(select(LeadList).where(LeadList.id == list_id))
    lead_list = result.scalar_one_or_none()
    
    if not lead_list:
        raise HTTPException(status_code=404, detail="Lead list not found")
    
    if lead_list.is_dynamic:
        raise HTTPException(status_code=400, detail="Cannot remove leads from dynamic list")
    
    if lead_list.lead_ids and lead_id in lead_list.lead_ids:
        lead_list.lead_ids.remove(lead_id)
        lead_list.total_count = len(lead_list.lead_ids)
        await db.commit()
    
    return {"removed": True}