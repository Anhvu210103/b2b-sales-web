"""Kanban board logic for deal pipeline."""

from typing import Dict, List, Optional, Any
from uuid import UUID
from datetime import datetime, timedelta
from collections import defaultdict

from app.deal_pipeline.stages import (
    DealStage,
    STAGE_CONFIG,
    VALID_TRANSITIONS,
    KANBAN_COLUMNS,
    get_valid_transitions,
    is_valid_transition,
    get_stage_config,
    get_stage_probability,
    get_next_actions,
    LOSS_REASONS,
    WIN_REASONS,
)


class KanbanBoard:
    """Kanban board manager for deal pipeline."""

    def __init__(self):
        self.columns = {col["stage"]: col for col in KANBAN_COLUMNS}
    
    def get_columns(self) -> List[Dict]:
        """Get all columns with metadata."""
        return KANBAN_COLUMNS
    
    def get_column(self, stage: DealStage) -> Dict:
        """Get column configuration for a stage."""
        return self.columns.get(stage, {})
    
    def get_column_limit(self, stage: DealStage) -> Optional[int]:
        """Get WIP limit for a column."""
        return self.columns.get(stage, {}).get("limit")
    
    def can_move(self, from_stage: DealStage, to_stage: DealStage) -> bool:
        """Check if move is valid."""
        return is_valid_transition(DealStage(from_stage), DealStage(to_stage))
    
    def get_valid_moves(self, from_stage: DealStage) -> List[str]:
        """Get valid next stages from current stage."""
        return [s.value for s in get_valid_transitions(DealStage(from_stage))]
    
    def get_stage_info(self, stage: DealStage) -> Dict:
        """Get full stage info including config and valid moves."""
        config = STAGE_CONFIG.get(DealStage(stage), {})
        return {
            "stage": stage,
            "config": config,
            "valid_moves": self.get_valid_moves(stage),
            "probability": config.get("probability", 0),
            "actions": config.get("actions", []),
        }
    
    def validate_move(self, from_stage: DealStage, to_stage: DealStage) -> Dict[str, Any]:
        """Validate a move and return info."""
        valid = self.can_move(DealStage(from_stage), DealStage(to_stage))
        return {
            "valid": valid,
            "from_stage": from_stage,
            "to_stage": to_stage,
            "requires_reason": any(
                t.from_stage == DealStage(from_stage) 
                and t.to_stage == DealStage(to_stage) 
                and t.requires_reason 
                for t in VALID_TRANSITIONS
            ),
            "auto_actions": [],
        }


class DealPipelineMetrics:
    """Calculate pipeline metrics and analytics."""
    
    def __init__(self, deals: List[Dict]):
        self.deals = deals
    
    def get_pipeline_summary(self) -> Dict[str, Any]:
        """Get overall pipeline summary."""
        total_deals = len(self.deals)
        total_value = sum(d.get("value", 0) or 0 for d in self.deals)
        weighted_value = sum(
            (d.get("value", 0) or 0) * (d.get("probability", 0) / 100) 
            for d in self.deals
        )
        
        by_stage = defaultdict(lambda: {"count": 0, "value": 0, "weighted": 0})
        for deal in self.deals:
            stage = deal.get("stage", "unknown")
            value = deal.get("value", 0) or 0
            prob = deal.get("probability", 0) / 100
            by_stage[deal["stage"]]["count"] += 1
            by_stage[deal["stage"]]["value"] += value
            by_stage[deal["stage"]]["weighted"] += value * prob
        
        won = [d for d in self.deals if d.get("stage") == "won"]
        lost = [d for d in self.deals if d.get("stage") == "lost"]
        
        return {
            "total_deals": len(self.deals),
            "total_value": sum(d.get("value", 0) or 0 for d in self.deals),
            "weighted_value": weighted_value,
            "by_stage": dict(by_stage),
            "won_count": len(won),
            "lost_count": len(lost),
            "win_rate": len(won) / max(len(won) + len(lost), 1) * 100,
        }
    
    def get_conversion_rates(self) -> Dict[str, float]:
        """Calculate stage-to-stage conversion rates."""
        stage_counts = defaultdict(int)
        for deal in self.deals:
            stage_counts[deal.get("stage", "unknown")] += 1
        
        stages_order = [
            "lead", "qualified", "demo_scheduled", "demo_completed",
            "proposal", "negotiation", "contract", "won", "lost"
        ]
        
        rates = {}
        for i in range(len(stages_order) - 1):
            from_stage = stages_order[i]
            to_stage = stages_order[i + 1]
            from_count = stage_counts.get(from_stage, 0)
            to_count = stage_counts.get(to_stage, 0)
            if from_count > 0:
                rates[f"{from_stage}→{to_stage}"] = round(to_count / from_count * 100, 1)
            else:
                rates[f"{from_stage}→{to_stage}"] = 0
        
        return rates
    
    def get_velocity(self) -> Dict[str, Any]:
        """Calculate pipeline velocity metrics."""
        from datetime import datetime, timedelta
        
        now = datetime.utcnow()
        thirty_days_ago = now - timedelta(days=30)
        ninety_days_ago = now - timedelta(days=90)
        
        # Deals closed in last 30/90 days
        recent_won = []
        for deal in self.deals:
            if deal.get("stage") == "won" and deal.get("actual_close_date"):
                try:
                    close_date = datetime.fromisoformat(deal["actual_close_date"].replace("Z", "+00:00"))
                    if close_date >= thirty_days_ago:
                        recent_won.append(deal)
                except:
                    pass
        
        # Average deal size
        won_deals = [d for d in self.deals if d.get("stage") == "won" and d.get("value")]
        avg_deal_size = sum(d.get("value", 0) for d in self.deals if d.get("stage") == "won") / max(len([d for d in self.deals if d.get("stage") == "won"]), 1)
        
        # Time in pipeline
        stage_times = defaultdict(list)
        for deal in self.deals:
            if deal.get("stage_changed_at"):
                try:
                    changed = datetime.fromisoformat(deal["stage_changed_at"].replace("Z", "+00:00"))
                    days = (now - changed).days
                    stage_times[deal["stage"]].append(days)
                except:
                    pass
        
        avg_stage_time = {
            stage: round(sum(days) / len(days), 1)
            for stage, days in stage_times.items()
        }
        
        return {
            "deals_won_30d": len(recent_won),
            "revenue_30d": sum(d.get("value", 0) for d in recent_won),
            "avg_deal_size": round(avg_deal_size, 2),
            "avg_time_in_stage": {
                stage: round(sum(days) / len(days), 1)
                for stage, days in stage_times.items()
            },
        }
    
    def get_bottlenecks(self) -> List[Dict]:
        """Identify pipeline bottlenecks."""
        bottlenecks = []
        
        # Deals stuck too long in stage
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        
        for deal in self.deals:
            if deal.get("stage_changed_at"):
                try:
                    changed = datetime.fromisoformat(deal["stage_changed_at"].replace("Z", "+00:00"))
                    days_stuck = (datetime.utcnow() - changed).days
                    
                    # Thresholds per stage
                    thresholds = {
                        "lead": 7,
                        "qualified": 14,
                        "demo_scheduled": 7,
                        "demo_completed": 7,
                        "proposal": 14,
                        "negotiation": 14,
                        "contract": 7,
                    }
                    
                    threshold = thresholds.get(deal.get("stage"), 14)
                    if days_stuck > threshold:
                        bottlenecks.append({
                            "deal_id": deal.get("id"),
                            "deal_name": deal.get("name"),
                            "stage": deal.get("stage"),
                            "days_stuck": days_stuck,
                            "threshold": threshold,
                            "value": deal.get("value", 0),
                        })
                except:
                    pass
        
        # Sort by value descending
        bottlenecks.sort(key=lambda x: x["value"], reverse=True)
        return bottlenecks[:20]


class PipelineForecaster:
    """Forecast pipeline revenue."""
    
    def __init__(self, deals: List[Dict]):
        self.deals = deals
    
    def forecast(self, months: int = 3) -> Dict[str, Any]:
        """Forecast revenue for next N months."""
        from datetime import datetime, timedelta
        from collections import defaultdict
        
        now = datetime.utcnow()
        future = now + timedelta(days=30 * months)
        
        # Active deals with expected close dates
        active_deals = [
            d for d in self.deals 
            if d.get("expected_close_date") 
            and d.get("stage") not in ("won", "lost")
        ]
        
        forecast = defaultdict(lambda: {"weighted": 0, "best_case": 0, "count": 0})
        
        for deal in active_deals:
            try:
                close_date = datetime.fromisoformat(deal["expected_close_date"].replace("Z", "+00:00"))
                if deal["expected_close_date"] <= future.isoformat():
                    month_key = close_date.strftime("%Y-%m")
                    value = deal.get("value", 0) or 0
                    prob = deal.get("probability", 0) / 100
                    
                    forecast[month_key]["weighted"] += value * (prob / 100)
                    forecast[month_key]["best_case"] += value
                    forecast[month_key]["count"] += 1
            except:
                pass
        
        return {
            "forecast": dict(forecast),
            "total_weighted": sum(v["weighted"] for v in forecast.values()),
            "total_best_case": sum(v["best_case"] for v in forecast.values()),
            "deals_in_pipeline": sum(v["count"] for v in forecast.values()),
        }
    
    def get_quarterly_forecast(self) -> Dict[str, Any]:
        """Get quarterly forecast."""
        return self.forecast(months=3)
    
    def get_annual_forecast(self) -> Dict[str, Any]:
        """Get annual forecast."""
        return self.forecast(months=12)


# Pipeline health checks
def health_check(deals: List[Dict]) -> Dict[str, Any]:
    """Perform pipeline health check."""
    issues = []
    warnings = []
    
    # Check for stale deals
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    
    for deal in deals:
        if deal.get("stage_changed_at"):
            try:
                changed = datetime.fromisoformat(deal["stage_changed_at"].replace("Z", "+00:00"))
                days = (datetime.utcnow() - changed).days
                
                if deal.get("stage") == "lead" and days > 14:
                    warnings.append(f"Lead {deal.get('name')} stuck >14 days")
                elif deal.get("stage") == "qualified" and days > 30:
                    warnings.append(f"Qualified deal {deal.get('name')} stuck >30 days")
                elif deal.get("stage") == "proposal" and days > 21:
                    warnings.append(f"Proposal {deal.get('name')} stuck >21 days")
                elif deal.get("stage") == "negotiation" and days > 30:
                    warnings.append(f"Negotiation {deal.get('name')} stuck >30 days")
            except:
                pass
    
    # Check for missing values
    no_value = [d for d in deals if d.get("stage") in ("proposal", "negotiation", "contract") and not d.get("value")]
    if no_value:
        warnings.append(f"{len(no_value)} deals in advanced stages missing value")
    
    # Check for missing close dates
    no_close = [d for d in deals if d.get("stage") in ("proposal", "negotiation", "contract") and not d.get("expected_close_date")]
    if no_close:
        warnings.append(f"{len(no_close)} advanced deals missing expected close date")
    
    return {
        "healthy": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "total_deals": len(deals),
    }