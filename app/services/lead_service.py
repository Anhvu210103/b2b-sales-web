"""Lead service - business logic for leads."""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.lead import Lead, LeadSource, LeadStatus
from app.models.outreach import OutreachLog, OutreachStatus


class LeadService:
    """Service for lead management."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_lead(self, lead_id: UUID) -> Optional[Lead]:
        """Get lead by ID."""
        result = await self.db.execute(
            select(Lead).where(Lead.id == lead_id)
        )
        return result.scalar_one_or_none()
    
    async def get_leads(
        self,
        skip: int = 0,
        limit: int = 20,
        filters: Optional[dict] = None,
        assigned_to: Optional[UUID] = None,
    ) -> List[Lead]:
        """Get leads with filters."""
        query = select(Lead)
        
        if assigned_to:
            query = query.where(Lead.assigned_to == assigned_to)
        
        if filters:
            if filters.get("source"):
                query = query.where(Lead.source == filters["source"])
            if filters.get("status"):
                query = query.where(Lead.status == filters["status"])
            if filters.get("industry"):
                query = query.where(Lead.industry.ilike(f"%{filters['industry']}%"))
            if filters.get("city"):
                query = query.where(Lead.city.ilike(f"%{filters['city']}%"))
            if filters.get("company_size"):
                query = query.where(Lead.company_size == filters["company_size"])
        
        query = query.order_by(Lead.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def create_lead(self, lead_data: dict, assigned_to: Optional[UUID] = None) -> Lead:
        """Create new lead."""
        lead = Lead(**lead_data, assigned_to=assigned_to)
        self.db.add(lead)
        await self.db.commit()
        await self.db.refresh(lead)
        return lead
    
    async def update_lead(self, lead_id: UUID, update_data: dict) -> Optional[Lead]:
        """Update lead."""
        lead = await self.get_lead(lead_id)
        if not lead:
            return None
        
        for field, value in update_data.items():
            setattr(lead, field, value)
        
        await self.db.commit()
        await self.db.refresh(lead)
        return lead
    
    async def delete_lead(self, lead_id: UUID) -> bool:
        """Delete lead."""
        lead = await self.get_lead(lead_id)
        if not lead:
            return False
        
        await self.db.delete(lead)
        await self.db.commit()
        return True
    
    async def enrich_lead(
        self,
        lead: Lead,
        force_refresh: bool = False,
        sources: Optional[List[str]] = None,
    ) -> Lead:
        """Enrich lead with external data."""
        from app.scrapers.yellowpages import YellowPagesScraper
        from app.scrapers.vietnamworks import VietnamWorksScraper
        from app.scrapers.apollo import ApolloScraper
        
        # Check if already enriched recently
        if not force_refresh and lead.enrichment_data and lead.updated_at:
            from datetime import datetime, timedelta
            if datetime.utcnow() - lead.updated_at < timedelta(days=7):
                return lead
        
        enrichment = lead.enrichment_data or {}
        
        # Scrape from available sources
        if not sources or "yellowpages" in sources:
            try:
                scraper = YellowPagesScraper()
                yp_data = await scraper.search_company(lead.company_name)
                if yp_data:
                    enrichment["yellowpages"] = yp_data
            except Exception as e:
                enrichment["yellowpages_error"] = str(e)
        
        if not sources or "vietnamworks" in sources:
            try:
                scraper = VietnamWorksScraper()
                vw_data = await scraper.search_company(lead.company_name)
                if vw_data:
                    enrichment["vietnamworks"] = vw_data
            except Exception as e:
                enrichment["vietnamworks_error"] = str(e)
        
        if not sources or "apollo" in sources:
            try:
                scraper = ApolloScraper()
                apollo_data = await scraper.search_company(lead.company_name)
                if apollo_data:
                    enrichment["apollo"] = apollo_data
            except Exception as e:
                enrichment["apollo_error"] = str(e)
        
        # Update lead
        lead.enrichment_data = enrichment
        lead.contacts = self._extract_contacts(enrichment)
        
        if enrichment.get("yellowpages"):
            yp = enrichment["yellowpages"]
            if yp.get("email"):
                lead.primary_email = yp["email"]
            if yp.get("phone"):
                lead.primary_phone = yp["phone"]
            if yp.get("website"):
                lead.website = yp["website"]
            if yp.get("address"):
                lead.address = yp["address"]
        
        await self.db.commit()
        await self.db.refresh(lead)
        return lead
    
    def _extract_contacts(self, enrichment: dict) -> List[dict]:
        """Extract all contacts from enrichment data."""
        contacts = []
        
        for source in ["yellowpages", "vietnamworks", "apollo"]:
            data = enrichment.get(source, {})
            if data.get("contacts"):
                for contact in data["contacts"]:
                    contacts.append({
                        "source": source,
                        "name": contact.get("name"),
                        "title": contact.get("title"),
                        "email": contact.get("email"),
                        "phone": contact.get("phone"),
                        "linkedin": contact.get("linkedin"),
                    })
        
        return contacts
    
    async def score_lead(self, lead: Lead, force_refresh: bool = False) -> Lead:
        """Score lead for fit and intent."""
        # Fit score: based on company characteristics
        fit_score = 0.0
        
        # Company size fit
        if lead.company_size:
            size_scores = {
                "11-50": 80,
                "51-200": 100,
                "201-500": 90,
                "500+": 70,
                "1-10": 50,
            }
            fit_score += size_scores.get(str(lead.company_size), 50)
        
        # Industry fit (assuming we target specific industries)
        target_industries = [
            "technology", "software", "saas", "fintech", "ecommerce",
            "marketing", "advertising", "consulting", "agency",
        ]
        if lead.industry and any(t in lead.industry.lower() for t in target_industries):
            fit_score += 30
        
        # Has website
        if lead.website:
            fit_score += 10
        
        # Has contact info
        if lead.primary_email or lead.primary_phone:
            fit_score += 20
        
        # Has contacts
        if lead.contacts and len(lead.contacts) > 0:
            fit_score += min(len(lead.contacts) * 5, 30)
        
        lead.fit_score = min(fit_score, 100.0)
        
        # Intent score: based on signals
        intent_score = 0.0
        
        signals = lead.signals or []
        for signal in signals:
            signal_type = signal.get("type", "")
            if signal_type in ["funding", "hiring", "expansion", "new_product"]:
                intent_score += 25
            elif signal_type in ["news", "event", "award"]:
                intent_score += 10
        
        # Outreach engagement
        result = await self.db.execute(
            select(func.count(OutreachLog.id)).where(
                and_(
                    OutreachLog.lead_id == lead.id,
                    OutreachLog.status.in_([OutreachStatus.OPENED, OutreachStatus.CLICKED, OutreachStatus.REPLIED])
                )
            )
        )
        engagement = result.scalar() or 0
        intent_score += min(engagement * 10, 50)
        
        lead.intent_score = min(intent_score, 100.0)
        
        # Engagement score
        result = await self.db.execute(
            select(func.count(OutreachLog.id)).where(
                and_(
                    OutreachLog.lead_id == lead.id,
                    OutreachLog.status == OutreachStatus.SENT
                )
            )
        )
        total_sent = result.scalar() or 0
        
        result = await self.db.execute(
            select(func.count(OutreachLog.id)).where(
                and_(
                    OutreachLog.lead_id == lead.id,
                    OutreachLog.status.in_([OutreachStatus.OPENED, OutreachStatus.CLICKED, OutreachStatus.REPLIED])
                )
            )
        )
        engaged = result.scalar() or 0
        
        lead.engagement_score = (engaged / total_sent * 100) if total_sent else 0.0
        
        await self.db.commit()
        await self.db.refresh(lead)
        
        return lead
    
    async def export_leads(
        self,
        ids: Optional[List[UUID]] = None,
        filters: Optional[dict] = None,
        fields: Optional[List[str]] = None,
        format: str = "csv",
    ) -> str:
        """Export leads to file."""
        import csv
        import io
        from pathlib import Path
        
        query = select(Lead)
        
        if ids:
            query = query.where(Lead.id.in_(ids))
        if filters:
            if filters.get("source"):
                query = query.where(Lead.source == filters["source"])
            if filters.get("status"):
                query = query.where(Lead.status == filters["status"])
        
        result = await self.db.execute(query)
        leads = result.scalars().all()
        
        # Default fields
        if not fields:
            fields = [
                "id", "company_name", "domain", "website", "industry",
                "company_size", "employee_count", "city", "address",
                "source", "status", "primary_email", "primary_phone",
                "primary_contact_name", "primary_contact_title",
                "fit_score", "intent_score", "engagement_score",
                "created_at", "updated_at",
            ]
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        
        for lead in leads:
            row = {}
            for field in fields:
                value = getattr(lead, field, None)
                if hasattr(value, 'isoformat'):
                    value = value.isoformat()
                elif value is None:
                    value = ""
                row[field] = value
            writer.writerow(row)
        
        # Save to file
        filename = f"leads_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.{format}"
        filepath = Path("./exports") / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8-sig') as f:
            f.write(output.getvalue())
        
        return str(filepath)