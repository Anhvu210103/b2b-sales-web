"""Analytics API routes."""

from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, case
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, get_current_active_user
from app.models.lead import Lead, LeadSource, LeadStatus
from app.models.deal import Deal, DealStage, DealActivity, ActivityType
from app.models.outreach import OutreachLog, OutreachChannel, OutreachStatus
from app.models.user import User
from app.schemas.common import PaginatedResponse

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get dashboard overview."""
    since = datetime.utcnow() - timedelta(days=days)
    
    # Base queries with role filtering
    def apply_role_filter(query, model):
        if current_user.role.value not in ("admin", "manager"):
            return query.where(
                or_(
                    model.assigned_to == current_user.id,
                    model.assigned_to.is_(None),
                )
            )
        return query
    
    # Leads stats
    leads_query = apply_role_filter(select(Lead), Lead)
    total_leads = await db.scalar(select(func.count(Lead.id)))
    new_leads = await db.scalar(
        select(func.count(Lead.id)).where(Lead.created_at >= since)
    )
    
    # Deals stats
    deals_query = apply_role_filter(select(Deal), Deal)
    total_deals = await db.scalar(select(func.count(Deal.id)))
    deal_value = await db.scalar(select(func.sum(Deal.value)))
    
    won_deals = await db.scalar(
        select(func.count(Deal.id)).where(
            and_(Deal.stage == "won", Deal.actual_close_date >= since)
        )
    )
    won_value = await db.scalar(
        select(func.sum(Deal.value)).where(
            and_(Deal.stage == "won", Deal.actual_close_date >= since)
        )
    )
    
    # Outreach stats
    outreach_query = select(OutreachLog).where(OutreachLog.created_at >= since)
    if current_user.role.value not in ("admin", "manager"):
        outreach_query = outreach_query.where(
            or_(
                OutreachLog.sent_by == current_user.id,
                OutreachLog.campaign_id.in_(
                    select(OutreachCampaign.id).where(
                        OutreachCampaign.created_by == current_user.id
                    )
                )
            )
        )
    
    total_sent = await db.scalar(
        select(func.count(OutreachLog.id)).where(
            and_(OutreachLog.created_at >= since, OutreachLog.status == "sent")
        )
    )
    total_replied = await db.scalar(
        select(func.count(OutreachLog.id)).where(
            and_(OutreachLog.created_at >= since, OutreachLog.status == "replied")
        )
    )
    
    return {
        "period_days": days,
        "leads": {
            "total": total_leads or 0,
            "new_this_period": new_leads or 0,
        },
        "deals": {
            "total": total_deals or 0,
            "total_value": float(deal_value or 0),
            "won": won_deals or 0,
            "won_value": float(won_value or 0),
            "win_rate": (won_deals / (total_deals or 1) * 100) if total_deals else 0,
        },
        "outreach": {
            "sent": total_sent or 0,
            "replied": total_replied or 0,
            "reply_rate": (total_replied / total_sent * 100) if total_sent else 0,
        },
    }


@router.get("/leads/funnel")
async def get_leads_funnel(
    days: int = 90,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get leads conversion funnel."""
    since = datetime.utcnow() - timedelta(days=days)
    
    query = select(Lead).where(Lead.created_at >= since)
    if current_user.role.value not in ("admin", "manager"):
        query = query.where(
            or_(Lead.assigned_to == current_user.id, Lead.assigned_to.is_(None))
        )
    
    result = await db.execute(query)
    leads = result.scalars().all()
    
    funnel = {
        "new": 0,
        "enriched": 0,
        "contacted": 0,
        "replied": 0,
        "interested": 0,
        "demo_scheduled": 0,
        "demo_completed": 0,
        "proposal_sent": 0,
        "won": 0,
        "lost": 0,
    }
    
    for lead in leads:
        if lead.status in funnel:
            funnel[lead.status.value] += 1
    
    # Calculate conversion rates
    total = sum(funnel.values())
    conversion = {}
    for stage, count in funnel.items():
        conversion[stage] = {
            "count": count,
            "rate": (count / total * 100) if total else 0,
        }
    
    return {
        "funnel": funnel,
        "conversion": conversion,
        "total": total,
    }


@router.get("/outreach/performance")
async def get_outreach_performance(
    days: int = 30,
    channel: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get outreach performance by channel/template/campaign."""
    since = datetime.utcnow() - timedelta(days=days)
    
    query = select(OutreachLog).where(OutreachLog.created_at >= since)
    
    if channel:
        from app.models.outreach import OutreachChannel
        query = query.where(OutreachLog.channel == OutreachChannel(channel))
    
    # Role filter
    if current_user.role.value not in ("admin", "manager"):
        query = query.where(
            or_(
                OutreachLog.sent_by == current_user.id,
                OutreachLog.campaign_id.in_(
                    select(OutreachCampaign.id).where(
                        OutreachCampaign.created_by == current_user.id
                    )
                )
            )
        )
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    # By channel
    by_channel = {}
    for log in logs:
        ch = log.channel.value
        if ch not in by_channel:
            by_channel[ch] = {"sent": 0, "delivered": 0, "opened": 0, "clicked": 0, "replied": 0, "bounced": 0}
        by_channel[ch]["sent"] += 1
        if log.status == "delivered":
            by_channel[ch]["delivered"] += 1
        if log.opened_at:
            by_channel[ch]["opened"] += 1
        if log.clicked_at:
            by_channel[ch]["clicked"] += 1
        if log.replied_at:
            by_channel[ch]["replied"] += 1
        if log.status == "bounced":
            by_channel[ch]["bounced"] += 1
    
    # Calculate rates
    for ch, stats in by_channel.items():
        if stats["sent"] > 0:
            stats["open_rate"] = round(stats["opened"] / stats["sent"] * 100, 2)
            stats["reply_rate"] = round(stats["replied"] / stats["sent"] * 100, 2)
            stats["bounce_rate"] = round(stats["bounced"] / stats["sent"] * 100, 2)
    
    return {
        "period_days": 30,
        "by_channel": by_channel,
        "total": {
            "sent": sum(s["sent"] for s in by_channel.values()),
            "replied": sum(s["replied"] for s in by_channel.values()),
        },
    }


@router.get("/deals/velocity")
async def get_deal_velocity(
    days: int = 90,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get deal velocity metrics."""
    since = datetime.utcnow() - timedelta(days=days)
    
    query = select(Deal).where(Deal.created_at >= since)
    if current_user.role.value not in ("admin", "manager"):
        query = query.where(
            or_(Deal.assigned_to == current_user.id, Deal.assigned_to.is_(None))
        )
    
    result = await db.execute(query)
    deals = result.scalars().all()
    
    # Time to close
    closed_deals = [d for d in deals if d.stage.value in ("won", "lost") and d.actual_close_date]
    if closed_deals:
        avg_days_to_close = sum(
            (d.actual_close_date - d.created_at).days for d in closed_deals
        ) / len(closed_deals)
    else:
        avg_days_to_close = 0
    
    # By stage time
    stage_times = {}
    for deal in deals:
        if deal.stage_changed_at:
            days_in_stage = (datetime.utcnow() - deal.stage_changed_at).days
            if deal.stage.value not in stage_times:
                stage_times[deal.stage.value] = []
            stage_times[deal.stage.value].append(days_in_stage)
    
    avg_stage_time = {
        stage: round(sum(days) / len(days), 1)
        for stage, days in stage_times.items()
    }
    
    return {
        "avg_days_to_close": round(avg_days_to_close, 1),
        "avg_time_in_stage": avg_stage_time,
        "deals_analyzed": len(deals),
    }


@router.get("/team/performance")
async def get_team_performance(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get team performance (admin/manager only)."""
    if current_user.role.value not in ("admin", "manager"):
        raise HTTPException(status_code=403, detail="Admin/manager only")
    
    since = datetime.utcnow() - timedelta(days=days)
    
    # Get all team members
    team_query = select(User).where(User.is_active == True)
    if current_user.role.value == "manager":
        team_query = team_query.where(
            or_(User.manager_id == current_user.id, User.id == current_user.id)
        )
    
    result = await db.execute(team_query)
    team = result.scalars().all()
    
    performance = []
    for user in team:
        # Leads
        leads_count = await db.scalar(
            select(func.count(Lead.id)).where(
                and_(Lead.assigned_to == user.id, Lead.created_at >= since)
            )
        )
        
        # Deals
        deals_count = await db.scalar(
            select(func.count(Deal.id)).where(
                and_(Deal.assigned_to == user.id, Deal.created_at >= since)
            )
        )
        deals_won = await db.scalar(
            select(func.count(Deal.id)).where(
                and_(
                    Deal.assigned_to == user.id,
                    Deal.stage == "won",
                    Deal.actual_close_date >= since
                )
            )
        )
        deals_value = await db.scalar(
            select(func.sum(Deal.value)).where(
                and_(
                    Deal.assigned_to == user.id,
                    Deal.stage == "won",
                    Deal.actual_close_date >= since
                )
            )
        )
        
        # Outreach
        sent = await db.scalar(
            select(func.count(OutreachLog.id)).where(
                and_(
                    OutreachLog.sent_by == user.id,
                    OutreachLog.created_at >= since,
                    OutreachLog.status == "sent"
                )
            )
        )
        replied = await db.scalar(
            select(func.count(OutreachLog.id)).where(
                and_(
                    OutreachLog.sent_by == user.id,
                    OutreachLog.replied_at >= since
                )
            )
        )
        
        # Activities
        activities = await db.scalar(
            select(func.count(DealActivity.id)).where(
                and_(DealActivity.created_by == user.id, DealActivity.created_at >= since)
            )
        )
        
        performance.append({
            "user_id": str(user.id),
            "name": user.full_name,
            "email": user.email,
            "role": user.role.value,
            "leads_created": leads_count or 0,
            "deals_created": deals_count or 0,
            "deals_won": deals_won or 0,
            "deals_value": float(deals_value or 0),
            "emails_sent": sent or 0,
            "replies_received": replied or 0,
            "reply_rate": round((replied or 0) / (sent or 1) * 100, 2),
            "activities": activities or 0,
        })
    
    # Sort by revenue
    performance.sort(key=lambda x: x["deals_value"], reverse=True)
    
    return {
        "period_days": 30,
        "team": performance,
        "summary": {
            "total_revenue": sum(p["deals_value"] for p in performance),
            "total_deals_won": sum(p["deals_won"] for p in performance),
            "total_leads": sum(p["leads_created"] for p in performance),
            "total_emails": sum(p["emails_sent"] for p in performance),
        },
    }