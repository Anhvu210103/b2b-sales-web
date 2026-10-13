"""Deal service - pipeline and activity management."""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.deal import Deal, DealStage, DealActivity, ActivityType, DealStage as DealStageEnum
from app.models.lead import Lead
from app.models.user import User
from app.schemas.deal import DealCreate, DealUpdate, DealStageUpdate, DealActivityCreate


class DealService:
    """Service for deal pipeline management."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # ==================== Deals ====================
    
    async def get_deal(self, deal_id: UUID) -> Optional[Any]:
        """Get deal with relationships."""
        from app.models.deal import Deal
        result = await self.db.execute(
            select(Deal)
            .options(
                selectinload(Deal.lead),
                selectinload(Deal.assigned_user),
                selectinload(Deal.activities).selectinload(DealActivity.creator),
            )
            .where(Deal.id == deal_id)
        )
        return result.scalar_one_or_none()
    
    async def get_deals(
        self,
        skip: int = 0,
        limit: int = 20,
        filters: Optional[dict] = None,
        assigned_to: Optional[UUID] = None,
    ) -> List[Any]:
        """Get deals with filters."""
        from app.models.deal import Deal
        query = select(Deal).options(
            selectinload(Deal.lead),
            selectinload(Deal.assigned_user),
        )
        
        if assigned_to:
            query = query.where(Deal.assigned_to == assigned_to)
        
        if filters:
            if filters.get("stage"):
                query = query.where(Deal.stage == filters["stage"])
            if filters.get("min_value"):
                query = query.where(Deal.value >= filters["min_value"])
            if filters.get("max_value"):
                query = query.where(Deal.value <= filters["max_value"])
        
        query = query.order_by(Deal.created_at.desc()).offset(0).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def create_deal(self, deal_data: DealCreate, current_user: Any) -> Any:
        """Create new deal."""
        from app.models.deal import Deal
        deal = Deal(
            **deal_data.model_dump(exclude={"assigned_to"}),
            assigned_to=deal_data.assigned_to or deal_data.lead_id,  # Will be resolved
        )
        
        # Resolve lead
        from app.models.lead import Lead
        lead = await self.db.get(Lead, deal_data.lead_id)
        if not lead:
            raise ValueError("Lead not found")
        
        deal.lead_id = lead.id
        deal.assigned_to = deal_data.assigned_to or lead.assigned_to
        
        self.db.add(deal)
        await self.db.commit()
        await self.db.refresh(deal)
        
        # Create initial activity
        await self.create_activity(DealActivityCreate(
            deal_id=deal.id,
            type="note",
            subject="Deal created",
            description=f"Deal '{deal.name}' created from lead {deal.lead.company_name}",
        ), current_user=User())
        
        return deal
    
    async def update_deal(self, deal_id: UUID, update_data: DealUpdate, current_user: Any) -> Optional[Any]:
        """Update deal."""
        deal = await self.get_deal(deal_id)
        if not deal:
            return None
        
        old_stage = deal.stage
        old_values = {}
        
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            old_values[field] = getattr(deal, field)
            setattr(deal, field, value)
        
        if "stage" in old_values:
            deal.stage_changed_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(deal)
        
        # Log stage change
        if "stage" in old_values:
            from app.models.deal import DealActivity, ActivityType
            activity = DealActivity(
                deal_id=deal.id,
                type=ActivityType.STATUS_CHANGED,
                subject=f"Stage: {old_values['stage']} → {deal.stage}",
                description=f"Stage changed from {old_values['stage']} to {deal.stage}",
                metadata={"old_stage": old_values['stage'], "new_stage": deal.stage.value},
                created_by=current_user.id if hasattr(current_user, 'id') else None,
            )
            self.db.add(DealActivity(**activity.__dict__))
            await self.db.commit()
        
        return deal
    
    async def update_stage(self, deal_id: UUID, new_stage: str, loss_reason: Optional[str] = None) -> Optional[Any]:
        """Update deal stage."""
        deal = await self.get_deal(deal_id)
        if not deal:
            return None
        
        old_stage = deal.stage
        deal.stage = DealStage(new_stage)
        deal.stage_changed_at = datetime.utcnow()
        
        if new_stage == "lost" and loss_reason:
            deal.loss_reason = loss_reason
        
        if new_stage == "won":
            deal.actual_close_date = datetime.utcnow()
            deal.probability = 100
        
        await self.db.commit()
        await self.db.refresh(deal)
        
        return deal
    
    async def delete_deal(self, deal_id: UUID) -> bool:
        deal = await self.get_deal(deal_id)
        if not deal:
            return False
        await self.db.delete(deal)
        await self.db.commit()
        return True
    
    # ==================== Pipeline View ====================
    
    async def get_pipeline(self, user_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Get pipeline view grouped by stage."""
        from app.models.deal import Deal, DealStage
        
        query = select(Deal).options(selectinload(Deal.lead))
        
        result = await self.db.execute(query)
        deals = result.scalars().all()
        
        stages = {}
        totals = {}
        values = {}
        
        for stage in DealStage:
            stage_deals = [d for d in deals if d.stage == stage]
            stages[stage.value] = [
                {
                    "id": str(d.id),
                    "name": d.name,
                    "lead_name": d.lead.company_name if d.lead else None,
                    "value": float(d.value or 0),
                    "probability": d.probability,
                    "expected_close": d.expected_close_date.isoformat() if d.expected_close_date else None,
                }
                for d in stage_deals
            ]
            totals[stage.value] = len(stage_deals)
            values[stage.value] = sum(d.value or 0 for d in stage_deals)
        
        return {
            "stages": stages,
            "totals": totals,
            "values": values,
        }
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get deal statistics."""
        from app.models.deal import Deal, DealStage
        
        total = await self.db.scalar(select(func.count(Deal.id)))
        
        stage_stats = await self.db.execute(
            select(Deal.stage, func.count(Deal.id), func.sum(Deal.value))
            .group_by(Deal.stage)
        )
        by_stage = {str(s): {"count": c, "value": float(v or 0)} for s, c, v in stage_stats.all()}
        
        won = await self.db.scalar(
            select(func.count(Deal.id)).where(Deal.stage == DealStage.WON)
        )
        lost = await self.db.scalar(
            select(func.count(Deal.id)).where(Deal.stage == DealStage.LOST)
        )
        
        total_value = await self.db.scalar(select(func.sum(Deal.value)))
        
        return {
            "total_deals": total or 0,
            "total_value": float(total_value or 0),
            "by_stage": by_stage,
            "won": won or 0,
            "lost": lost or 0,
            "win_rate": (won / (won + lost) * 100) if (won and lost) else 0,
        }
    
    # ==================== Activities ====================
    
    async def create_activity(
        self,
        activity_data: DealActivityCreate,
        current_user: Any,
    ) -> Any:
        """Create deal activity."""
        from app.models.deal import DealActivity
        
        activity = DealActivity(
            **activity_data.model_dump(exclude={"created_by"}),
            created_by=current_user.id if hasattr(current_user, 'id') else None,
        )
        
        self.db.add(DealActivity(**activity.__dict__))
        await self.db.commit()
        await self.db.refresh(activity)
        return activity
    
    async def get_activities(
        self,
        deal_id: UUID,
        limit: int = 50,
    ) -> List[Any]:
        from app.models.deal import DealActivity
        result = await self.db.execute(
            select(DealActivity)
            .options(
                selectinload(DealActivity.creator),
                selectinload(DealActivity.assignee),
            )
            .where(DealActivity.deal_id == deal_id)
            .order_by(DealActivity.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    async def update_activity(
        self,
        activity_id: UUID,
        update_data: DealActivityUpdate,
    ) -> Optional[Any]:
        from app.models.deal import DealActivity
        result = await self.db.execute(select(DealActivity).where(DealActivity.id == activity_id))
        activity = result.scalar_one_or_none()
        
        if not activity:
            return None
        
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(activity, field, value)
        
        if "completed_at" in update_data.model_dump(exclude_unset=True):
            activity.completed_at = update_data.completed_at
        
        await self.db.commit()
        await self.db.refresh(activity)
        return activity
    
    # ==================== Forecasting ====================
    
    async def get_forecast(self, months: int = 3) -> Dict[str, Any]:
        """Get revenue forecast."""
        from app.models.deal import Deal, DealStage
        
        future_date = datetime.utcnow() + timedelta(days=30 * months)
        
        # Expected closes
        deals = await self.db.execute(
            select(Deal).where(
                and_(
                    Deal.expected_close_date <= datetime.utcnow() + timedelta(days=30 * months),
                    Deal.stage.not_in([DealStage.WON, DealStage.LOST]),
                )
            )
        )
        deals = result.scalars().all()
        
        forecast = {}
        for deal in deals:
            if deal.expected_close_date:
                month_key = deal.expected_close_date.strftime("%Y-%m")
                if month_key not in forecast:
                    forecast[month_key] = {"weighted": 0, "best_case": 0, "count": 0}
                weight = deal.probability / 100
                forecast[month_key]["weighted"] += float(deal.value or 0) * weight
                forecast[month_key]["best_case"] += float(deal.value or 0)
                forecast[month_key]["count"] += 1
        
        return {
            "months": months,
            "forecast": forecast,
            "total_weighted": sum(v["weighted"] for v in forecast.values()),
            "total_best_case": sum(v["best_case"] for v in forecast.values()),
        }
    
    async def get_velocity(self) -> Dict[str, Any]:
        """Get deal velocity metrics."""
        from app.models.deal import Deal, DealStage, DealActivity
        
        # Average days to close
        closed = await self.db.execute(
            select(Deal).where(
                and_(
                    Deal.stage.in_([DealStage.WON, DealStage.LOST]),
                    Deal.actual_close_date.isnot(None),
                )
            )
        )
        closed_deals = result.scalars().all()
        
        if closed_deals:
            avg_days = sum(
                (d.actual_close_date - d.created_at).days for d in closed_deals
            ) / len(closed_deals)
        else:
            avg_days = 0
        
        # Time in each stage
        stage_times = {}
        all_deals = await self.db.execute(select(Deal))
        for deal in result.scalars().all():
            if deal.stage_changed_at:
                days = (datetime.utcnow() - deal.stage_changed_at).days
                if deal.stage.value not in stage_times:
                    stage_times[deal.stage.value] = []
                stage_times[deal.stage.value].append(days)
        
        avg_stage = {
            stage: round(sum(d) / len(d), 1)
            for stage, d in stage_times.items()
        }
        
        return {
            "avg_days_to_close": round(avg_days, 1),
            "avg_time_in_stage": avg_stage,
        }