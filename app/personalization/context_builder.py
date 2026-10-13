"""Context builder for personalization - gathers all relevant lead info."""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.lead import Lead
from app.models.deal import Deal, DealStage
from app.models.outreach import OutreachLog, OutreachStatus
from app.models.deal import DealActivity, ActivityType


class ContextBuilder:
    """Builds comprehensive context for personalization."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def build_lead_context(self, lead_id: UUID) -> Dict[str, Any]:
        """Build complete context for a lead."""
        result = await self.db.execute(
            select(Lead)
            .options(
                selectinload(Lead.outreach_logs),
                selectinload(Lead.deals),
                selectinload(Lead.activities),
            )
            .where(Lead.id == lead_id)
        )
        lead = result.scalar_one_or_none()
        
        if not lead:
            return {}
        
        # Get recent outreach
        outreach_logs = sorted(
            [log for log in lead.outreach_logs if log.status in [
                "sent", "delivered", "opened", "clicked", "replied"
            ]],
            key=lambda x: x.created_at,
            reverse=True
        )[:5]
        
        # Get deals
        active_deals = [d for d in lead.deals if d.stage.value not in ("won", "lost")]
        won_deals = [d for d in lead.deals if d.stage.value == "won"]
        
        # Get recent activities
        recent_activities = sorted(
            lead.activities,
            key=lambda x: x.created_at,
            reverse=True
        )[:10]
        
        # Build context
        context = {
            # Company info
            "company": {
                "name": lead.company_name,
                "domain": lead.domain,
                "website": lead.website,
                "industry": lead.industry,
                "company_size": str(lead.company_size) if lead.company_size else None,
                "employee_count": lead.employee_count,
                "city": lead.city,
                "address": lead.address,
            },
            
            # Contact info
            "contact": {
                "name": lead.primary_contact_name,
                "title": lead.primary_contact_title,
                "email": lead.primary_email,
                "phone": lead.primary_phone,
                "linkedin": lead.linkedin_url,
                "facebook": lead.facebook_url,
            },
            
            # All contacts
            "all_contacts": lead.contacts or [],
            
            # Source & signals
            "source": lead.source.value if lead.source else "manual",
            "source_url": lead.source_url,
            "signals": lead.signals or [],
            "signal_score": lead.signal_score,
            
            # Scoring
            "scores": {
                "fit": lead.fit_score,
                "intent": lead.intent_score,
                "engagement": lead.engagement_score,
            },
            
            # Outreach history
            "outreach_history": [
                {
                    "channel": log.channel.value,
                    "subject": log.subject,
                    "status": log.status.value,
                    "sent_at": log.sent_at.isoformat() if log.sent_at else None,
                    "opened_at": log.opened_at.isoformat() if log.opened_at else None,
                    "clicked_at": log.clicked_at.isoformat() if log.clicked_at else None,
                    "replied_at": log.replied_at.isoformat() if log.replied_at else None,
                    "template_id": str(log.template_id) if log.template_id else None,
                }
                for log in outreach_logs
            ],
            
            # Deal info
            "deals": {
                "active": [
                    {
                        "id": str(d.id),
                        "name": d.name,
                        "stage": d.stage.value,
                        "value": float(d.value) if d.value else None,
                        "probability": d.probability,
                        "expected_close": d.expected_close_date.isoformat() if d.expected_close_date else None,
                    }
                    for d in active_deals
                ],
                "won": [
                    {
                        "id": str(d.id),
                        "name": d.name,
                        "value": float(d.value) if d.value else None,
                        "closed_at": d.actual_close_date.isoformat() if d.actual_close_date else None,
                    }
                    for d in won_deals
                ],
            },
            
            # Recent activities
            "recent_activities": [
                {
                    "type": a.type.value,
                    "subject": a.subject,
                    "description": a.description,
                    "outcome": a.outcome,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                    "created_by": str(a.created_by) if a.created_by else None,
                }
                for a in recent_activities
            ],
            
            # Status
            "status": lead.status.value if lead.status else "new",
            "status_reason": lead.status_reason,
            
            # Tags & notes
            "tags": lead.tags or [],
            "notes": lead.notes,
            
            # Metadata
            "created_at": lead.created_at.isoformat() if lead.created_at else None,
            "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
            "last_contacted_at": lead.last_contacted_at.isoformat() if lead.last_contacted_at else None,
            "next_followup_at": lead.next_followup_at.isoformat() if lead.next_followup_at else None,
        }
        
        return context
    
    async def build_outreach_context(
        self,
        lead_id: UUID,
        channel: str,
        sequence_step: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Build context specifically for outreach generation."""
        base_context = await self.build_lead_context(lead_id)
        
        # Add channel-specific info
        lead_result = await self.db.execute(
            select(Lead).where(Lead.id == lead_id)
        )
        lead = result.scalar_one_or_none()
        
        if not lead:
            return {}
        
        # Get previous outreach on this channel
        from app.models.outreach import OutreachLog
        channel_logs = await self.db.execute(
            select(OutreachLog).where(
                OutreachLog.lead_id == lead_id
            ).order_by(OutreachLog.created_at.desc())
        )
        channel_logs = [l for l in channel_logs.scalars().all() if l.channel.value == channel]
        
        # Get previous sequence steps if in sequence
        sequence_logs = []
        if sequence_step := lead.outreach_logs:
            sequence_logs = [l for l in lead.outreach_logs if l.sequence_id and l.step_number]
        
        outreach_context = {
            **base_context,
            "channel": channel,
            "sequence_step": sequence_step,
            "previous_on_channel": [
                {
                    "subject": log.subject,
                    "body": log.body,
                    "status": log.status.value,
                    "sent_at": log.sent_at.isoformat() if log.sent_at else None,
                    "replied_at": log.replied_at.isoformat() if log.replied_at else None,
                }
                for log in channel_logs[:3]
            ],
            "sequence_history": [
                {
                    "step": log.step_number,
                    "channel": log.channel.value,
                    "status": log.status.value,
                    "sent_at": log.sent_at.isoformat() if log.sent_at else None,
                }
                for log in sequence_logs[-3:]
            ],
        }
        
        return outreach_context
    
    async def build_deal_context(self, deal_id: UUID) -> Dict[str, Any]:
        """Build context for deal-related personalization."""
        from app.models.deal import Deal
        
        result = await self.db.execute(
            select(Deal)
            .options(
                selectinload(Deal.lead),
                selectinload(Deal.activities),
                selectinload(Deal.assigned_user),
            )
            .where(Deal.id == deal_id)
        )
        deal = result.scalar_one_or_none()
        
        if not deal:
            return {}
        
        lead = deal.lead
        
        return {
            "deal": {
                "id": str(deal.id),
                "name": deal.name,
                "stage": deal.stage.value,
                "value": float(deal.value) if deal.value else None,
                "currency": deal.currency,
                "probability": deal.probability,
                "expected_close": deal.expected_close_date.isoformat() if deal.expected_close_date else None,
                "stage_changed_at": deal.stage_changed_at.isoformat() if deal.stage_changed_at else None,
            },
            "company": {
                "name": lead.company_name if lead else "",
                "industry": lead.industry if lead else "",
                "size": str(lead.company_size) if lead and lead.company_size else None,
            },
            "contact": {
                "name": lead.primary_contact_name if lead else None,
                "title": lead.primary_contact_title if lead else None,
                "email": lead.primary_email if lead else None,
            },
            "activities": [
                {
                    "type": a.type.value,
                    "subject": a.subject,
                    "description": a.description,
                    "outcome": a.outcome,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in sorted(deal.activities, key=lambda x: x.created_at, reverse=True)[:5]
            ],
        }
    
    async def build_company_profile(self, lead_id: UUID) -> Dict[str, Any]:
        """Build detailed company profile for deep research."""
        context = await self.build_lead_context(lead_id)
        
        # Add enrichment data
        lead_result = await self.db.execute(select(Lead).where(Lead.id == lead_id))
        lead = result.scalar_one_or_none()
        
        enrichment = lead.enrichment_data or {}
        
        profile = {
            **context,
            "enrichment": {
                "yellowpages": enrichment.get("yellowpages"),
                "vietnamworks": enrichment.get("vietnamworks"),
                "apollo": enrichment.get("apollo"),
                "signals": enrichment.get("signals"),
            },
            "technologies": enrichment.get("apollo", {}).get("technologies", []),
            "funding": enrichment.get("apollo", {}).get("funding", {}),
            "hiring_roles": [
                r.get("job_title") for r in enrichment.get("vietnamworks", {}).get("open_roles", [])
            ],
        }
        
        return profile