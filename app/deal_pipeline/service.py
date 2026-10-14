"""Deal pipeline service - business logic for pipeline management."""

from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.deal import Deal, DealStage, DealActivity, ActivityType, LeadList
from app.models.lead import Lead
from app.models.user import User
from app.deal_pipeline.kanban import KanbanBoard, DealPipelineMetrics, PipelineForecaster, health_check


class DealPipelineService:
    """Service for deal pipeline operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.kanban = KanbanBoard()
    
    # ==================== Deals ====================
    
    async def get_deal(self, deal_id: UUID) -> Optional[Dict]:
        """Get deal with all relations."""
        result = await self.db.execute(
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
        return deal
    
    async def list_deals(
        self,
        stage: Optional[str] = None,
        assigned_to: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Dict]:
        """List deals with filters."""
        query = select(Deal).options(
            selectinload(Deal.lead),
            selectinload(Deal.assigned_user),
        )
        
        if stage:
            query = query.where(Deal.stage == DealStage(stage))
        if assigned_to:
            query = query.where(Deal.assigned_to == assigned_to)
        
        query = query.order_by(Deal.created_at.desc()).offset(0).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def create_deal(self, data: Dict, current_user_id: UUID) -> Any:
        """Create new deal."""
        deal = Deal(**data)
        self.db.add(deal)
        await self.db.commit()
        await self.db.refresh(deal)
        return deal
    
    async def move_deal(
        self,
        deal_id: UUID,
        new_stage: str,
        reason: Optional[str] = None,
        current_user_id: Optional[UUID] = None,
    ) -> Optional[Dict]:
        """Move deal to new stage with validation."""
        from app.deal_pipeline.stages import is_valid_transition, DealStage
        
        deal = await self.get_deal(deal_id)
        if not deal:
            return None
        
        # Validate transition
        if not is_valid_transition(DealStage(deal.stage), DealStage(new_stage)):
            raise ValueError(f"Invalid transition from {deal.stage} to {new_stage}")
        
        old_stage = deal.stage
        deal.stage = DealStage(new_stage)
        deal.stage_changed_at = datetime.utcnow()
        
        if new_stage == "lost":
            # Handle loss reason
            pass
        elif new_stage == "won":
            deal.actual_close_date = datetime.utcnow()
            deal.probability = 100
        
        await self.db.commit()
        await self.db.refresh(deal)
        
        # Log activity
        await self.log_activity(
            deal_id=deal.id,
            activity_type="status_changed",
            subject=f"Stage: {old_stage} → {new_stage}",
            description=f"Deal stage changed from {old_stage} to {new_stage}",
            metadata={"old_stage": old_stage, "new_stage": new_stage},
            created_by=deal_id,  # Would need current_user_id
        )
        
        return deal
    
    async def update_deal(self, deal_id: UUID, updates: Dict) -> Optional[Dict]:
        """Update deal fields."""
        deal = await self.get_deal(deal_id)
        if not deal:
            return None
        
        for key, value in updates.items():
            if hasattr(deal, key):
                setattr(deal, key, value)
        
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
        """Get kanban pipeline view."""
        query = select(Deal).options(selectinload(Deal.lead))
        result = await self.db.execute(query)
        deals = result.scalars().all()
        
        pipeline = {}
        for stage in [
            "lead", "qualified", "demo_scheduled", "demo_completed",
            "proposal", "negotiation", "contract", "won", "lost", "on_hold"
        ]:
            stage_deals = [d for d in deals if d.stage.value == stage]
            pipeline[stage] = {
                "deals": [
                    {
                        "id": str(d.id),
                        "name": d.name,
                        "lead_name": d.lead.company_name if d.lead else None,
                        "value": float(d.value or 0),
                        "probability": d.probability,
                        "expected_close": d.expected_close_date.isoformat() if d.expected_close_date else None,
                        "days_in_stage": (datetime.utcnow() - d.stage_changed_at).days if d.stage_changed_at else 0,
                    }
                    for d in stage_deals
                ],
                "count": len(stage_deals),
                "total_value": sum(d.value or 0 for d in stage_deals),
            }
        
        # Summary
        total_value = sum(d.value or 0 for d in deals)
        won_value = sum(d.value or 0 for d in deals if d.stage.value == "won")
        
        return {
            "pipeline": pipeline,
            "summary": {
                "total_deals": len(deals),
                "total_value": float(sum(d.value or 0 for d in deals)),
                "won_value": float(sum(d.value or 0 for d in deals if d.stage.value == "won")),
                "weighted_value": sum(
                    float(d.value or 0) * (d.probability / 100) for d in deals
                ),
            }
        }
    
    async def get_kanban_board(self) -> Dict[str, Any]:
        """Get full kanban board state."""
        query = select(Deal).options(selectinload(Deal.lead))
        result = await self.db.execute(query)
        deals = result.scalars().all()
        
        board = {}
        for stage in [
            "lead", "qualified", "demo_scheduled", "demo_completed",
            "proposal", "negotiation", "contract", "won", "lost", "on_hold"
        ]:
            stage_deals = [d for d in deals if d.stage.value == stage]
            board[stage] = {
                "deals": [
                    {
                        "id": str(d.id),
                        "name": d.name,
                        "lead_name": d.lead.company_name if d.lead else None,
                        "value": float(d.value or 0),
                        "probability": d.probability,
                        "expected_close": d.expected_close_date.isoformat() if d.expected_close_date else None,
                        "days_in_stage": (datetime.utcnow() - d.stage_changed_at).days if d.stage_changed_at else 0,
                        "lead_id": str(d.lead_id) if d.lead_id else None,
                    }
                    for d in stage_deals
                ],
                "count": len(stage_deals),
                "total_value": sum(d.value or 0 for d in stage_deals),
                "limit": self.kanban.get_column_limit(stage),
            }
        
        return {
            "columns": board,
            "metadata": {
                "total_deals": len(deals),
                "total_value": sum(d.value or 0 for d in deals),
            }
        }
    
    async def move_deal_kanban(
        self,
        deal_id: UUID,
        new_stage: str,
        current_user_id: UUID,
    ) -> Optional[Dict]:
        """Move deal on kanban board."""
        deal = await self.get_deal(deal_id)
        if not deal:
            raise ValueError("Deal not found")
        
        # Validate
        from app.deal_pipeline.stages import is_valid_transition, DealStage
        if not is_valid_transition(DealStage(deal.stage), DealStage(new_stage)):
            raise ValueError(f"Invalid move from {deal.stage} to {new_stage}")
        
        old_stage = deal.stage
        deal.stage = new_stage
        deal.stage_changed_at = datetime.utcnow()
        
        if new_stage == "won":
            deal.actual_close_date = datetime.utcnow()
            deal.probability = 100
        elif new_stage == "lost":
            deal.probability = 0
        
        await self.db.commit()
        await self.db.refresh(deal)
        
        # Log activity
        await self.log_activity(
            deal_id=deal_id,
            type="status_changed",
            subject=f"Di chuyển: {old_stage} → {new_stage}",
            description=f"Deal chuyển từ {old_stage} sang {new_stage}",
            metadata={"old_stage": old_stage, "new_stage": new_stage},
            created_by=current_user_id,
        )
        
        return {"success": True, "deal_id": str(deal_id), "new_stage": new_stage}
    
    # ==================== Activities ====================
    
    async def log_activity(
        self,
        deal_id: UUID,
        activity_type: str,
        subject: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict] = None,
        created_by: Optional[UUID] = None,
        due_at: Optional[datetime] = None,
    ) -> Any:
        """Log deal activity."""
        from app.models.deal import DealActivity, ActivityType
        
        activity = DealActivity(
            deal_id=deal_id,
            type=ActivityType(activity_type),
            subject=subject,
            description=description,
            metadata_=metadata or {},
            created_by=created_by,
            due_at=due_at,
        )
        self.db.add(activity)
        await self.db.commit()
        await self.db.refresh(activity)
        return activity
    
    async def get_activities(
        self,
        deal_id: UUID,
        limit: int = 50,
    ) -> List[Dict]:
        """Get deal activities."""
        from app.models.deal import DealActivity
        
        result = await self.db.execute(
            select(DealActivity)
            .where(DealActivity.deal_id == deal_id)
            .order_by(DealActivity.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    # ==================== Metrics & Analytics ====================
    
    async def get_pipeline_metrics(self) -> Dict[str, Any]:
        """Get pipeline metrics."""
        deals = await self.list_deals(limit=10000)
        metrics = DealPipelineMetrics(deals)
        return {
            "summary": metrics.get_pipeline_summary(),
            "conversion_rates": metrics.get_conversion_rates(),
            "velocity": metrics.get_velocity(),
            "bottlenecks": metrics.get_bottlenecks(),
            "health": health_check(deals),
        }
    
    async def get_forecast(self, months: int = 3) -> Dict[str, Any]:
        """Get revenue forecast."""
        deals = await self.list_deals(limit=10000)
        forecaster = PipelineForecaster(deals)
        return forecaster.forecast(months)
    
    async def get_team_performance(self, team_ids: List[UUID]) -> List[Dict]:
        """Get performance for team members."""
        results = []
        for user_id in team_ids:
            deals = await self.list_deals(assigned_to=user_id, limit=10000)
            won = [d for d in deals if d.stage.value == "won"]
            total_value = sum(d.value or 0 for d in deals if d.stage.value == "won")
            
            results.append({
                "user_id": str(user_id),
                "total_deals": len(deals),
                "won": len([d for d in deals if d.stage.value == "won"]),
                "total_value": sum(d.value or 0 for d in deals if d.stage.value == "won"),
                "avg_deal_size": sum(d.value or 0 for d in deals if d.stage.value == "won") / max(len([d for d in deals if d.stage.value == "won"]), 1),
            })
        
        return results
    
    async def get_stage_distribution(self) -> Dict[str, int]:
        """Get deal count by stage."""
        result = await self.db.execute(
            select(Deal.stage, func.count(Deal.id))
            .group_by(Deal.stage)
        )
        return {str(stage): count for stage, count in result.all()}
    
    async def get_monthly_trends(self, months: int = 12) -> List[Dict]:
        """Get monthly deal trends."""
        from datetime import datetime, timedelta
        
        trends = []
        for i in range(months):
            month_start = datetime.utcnow().replace(day=1) - timedelta(days=30*i)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            result = await self.db.execute(
                select(
                    func.count(Deal.id),
                    func.sum(Deal.value)
                ).where(
                    and_(
                        Deal.created_at >= month_start,
                        Deal.created_at <= month_end,
                    )
                )
            )
            count, value = result.one()
            
            trends.append({
                "month": month_start.strftime("%Y-%m"),
                "deals_created": count or 0,
                "total_value": float(value or 0),
            })
        
        return list(reversed(trends))