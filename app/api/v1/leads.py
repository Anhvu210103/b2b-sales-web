"""Leads API routes."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, get_current_active_user, PaginationParams
from app.models.lead import Lead, LeadSource, LeadStatus
from app.models.user import User
from app.schemas.lead import (
    LeadCreate,
    LeadUpdate,
    LeadResponse,
    LeadListResponse,
    LeadEnrichRequest,
    LeadScoreRequest,
    LeadImportRow,
    LeadExportRequest,
    PaginatedResponse,
)
from app.schemas.common import FilterParams

router = APIRouter()


@router.get("", response_model=PaginatedResponse[LeadListResponse])
async def list_leads(
    pagination: PaginationParams = Depends(),
    source: Optional[str] = None,
    status: Optional[str] = None,
    industry: Optional[str] = None,
    company_size: Optional[str] = None,
    city: Optional[str] = None,
    assigned_to_me: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List leads with filters and pagination."""
    query = select(Lead)
    
    # Filters
    if source:
        query = query.where(Lead.source == LeadSource(source))
    if status:
        query = query.where(Lead.status == LeadStatus(status))
    if industry:
        query = query.where(Lead.industry.ilike(f"%{industry}%"))
    if company_size:
        query = query.where(Lead.company_size == company_size)
    if city:
        query = query.where(Lead.city.ilike(f"%{city}%"))
    if assigned_to_me:
        query = query.where(Lead.assigned_to == current_user.id)
    
    # Search
    if pagination.search:
        search_term = f"%{pagination.search}%"
        query = query.where(
            or_(
                Lead.company_name.ilike(search_term),
                Lead.domain.ilike(search_term),
                Lead.primary_email.ilike(search_term),
            )
        )
    
    # Role-based access
    if current_user.role.value not in ("admin", "manager"):
        query = query.where(
            or_(
                Lead.assigned_to == current_user.id,
                Lead.assigned_to.is_(None),
            )
        )
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)
    
    # Sorting
    if pagination.sort_by:
        sort_col = getattr(Lead, pagination.sort_by, Lead.created_at)
        if pagination.sort_order == "asc":
            query = query.order_by(sort_col.asc())
        else:
            query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(Lead.created_at.desc())
    
    # Pagination
    offset = (pagination.page - 1) * pagination.page_size
    query = query.offset(offset).limit(pagination.page_size)
    
    result = await db.execute(query)
    leads = result.scalars().all()
    
    return PaginatedResponse.create(
        items=[LeadListResponse.model_validate(lead) for lead in leads],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/stats")
async def get_lead_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get lead statistics."""
    base_query = select(Lead)
    
    if current_user.role.value not in ("admin", "manager"):
        base_query = base_query.where(
            or_(Lead.assigned_to == current_user.id, Lead.assigned_to.is_(None))
        )
    
    # Total
    total = await db.scalar(select(func.count()).select_from(base_query.subquery()))
    
    # By status
    status_stats = await db.execute(
        select(Lead.status, func.count(Lead.id))
        .where(base_query.whereclause)
        .group_by(Lead.status)
    )
    by_status = {str(s): c for s, c in status_stats.all()}
    
    # By source
    source_stats = await db.execute(
        select(Lead.source, func.count(Lead.id))
        .where(base_query.whereclause)
        .group_by(Lead.source)
    )
    by_source = {str(s): c for s, c in source_stats.all()}
    
    # By industry
    industry_stats = await db.execute(
        select(Lead.industry, func.count(Lead.id))
        .where(base_query.whereclause)
        .group_by(Lead.industry)
    )
    by_industry = {i: c for i, c in industry_stats.all() if i}
    
    return {
        "total": total,
        "by_status": by_status,
        "by_source": by_source,
        "by_industry": by_industry,
    }


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get single lead with full details."""
    result = await db.execute(
        select(Lead)
        .options(
            selectinload(Lead.assigned_user),
            selectinload(Lead.outreach_logs),
            selectinload(Lead.deals),
            selectinload(Lead.activities),
        )
        .where(Lead.id == lead_id)
    )
    lead = result.scalar_one_or_none()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Check access
    if current_user.role.value not in ("admin", "manager"):
        if lead.assigned_to != current_user.id and lead.assigned_to is not None:
            raise HTTPException(status_code=403, detail="Not authorized")
    
    return LeadResponse.model_validate(lead)


@router.post("", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(
    lead_data: LeadCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create new lead."""
    from app.core.security import get_password_hash
    
    lead = Lead(**lead_data.model_dump())
    lead.assigned_to = lead_data.assigned_to or current_user.id
    
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    
    # Audit log
    from app.models.audit import AuditLog
    from uuid import uuid4
    audit = AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        action="lead.created",
        resource_type="lead",
        resource_id=lead.id,
        new_values=lead_data.model_dump(),
    )
    db.add(audit)
    await db.commit()
    
    return LeadResponse.model_validate(lead)


@router.patch("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: str,
    lead_update: LeadUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update lead."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Check access
    if current_user.role.value not in ("admin", "manager"):
        if lead.assigned_to != current_user.id and lead.assigned_to is not None:
            raise HTTPException(status_code=403, detail="Not authorized")
    
    update_data = lead_update.model_dump(exclude_unset=True)
    old_values = {}
    
    for field, value in update_data.items():
        old_values[field] = getattr(lead, field)
        setattr(lead, field, value)
    
    await db.commit()
    await db.refresh(lead)
    
    # Audit log
    from app.models.audit import AuditLog
    audit = AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        action="lead.updated",
        resource_type="lead",
        resource_id=lead.id,
        old_values=old_values,
        new_values=update_data,
    )
    db.add(audit)
    await db.commit()
    
    return LeadResponse.model_validate(lead)


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Delete lead (admin only)."""
    if current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    await db.delete(lead)
    await db.commit()


@router.post("/{lead_id}/enrich")
async def enrich_lead(
    lead_id: str,
    request: LeadEnrichRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Enrich lead with external data."""
    from app.services.lead_service import LeadService
    
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    service = LeadService(db)
    enriched = await service.enrich_lead(lead, request.force_refresh, request.sources)
    
    return {"message": "Lead enriched successfully", "lead": LeadResponse.model_validate(enriched)}


@router.post("/{lead_id}/score")
async def score_lead(
    lead_id: str,
    request: LeadScoreRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Score lead for fit and intent."""
    from app.services.lead_service import LeadService
    
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    service = LeadService(db)
    scored = await service.score_lead(lead, request.force_refresh)
    
    return {
        "fit_score": scored.fit_score,
        "intent_score": scored.intent_score,
        "engagement_score": scored.engagement_score,
    }


@router.post("/bulk-import")
async def bulk_import_leads(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Import leads from CSV/Excel."""
    import csv
    import io
    
    content = await file.read()
    if file.filename.endswith('.csv'):
        decoded = content.decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(decoded))
        rows = list(reader)
    else:
        raise HTTPException(status_code=400, detail="Only CSV supported for now")
    
    created = 0
    errors = []
    
    for i, row in enumerate(rows, 1):
        try:
            # Map CSV columns to LeadCreate
            lead_data = LeadCreate(
                company_name=row.get("company_name", ""),
                domain=row.get("domain"),
                website=row.get("website"),
                industry=row.get("industry"),
                company_size=row.get("company_size"),
                employee_count=row.get("employee_count"),
                city=row.get("city"),
                address=row.get("address"),
                primary_email=row.get("primary_email"),
                primary_phone=row.get("primary_phone"),
                primary_contact_name=row.get("primary_contact_name"),
                primary_contact_title=row.get("primary_contact_title"),
                source=row.get("source", "manual"),
                tags=row.get("tags", "").split(",") if row.get("tags") else None,
                notes=row.get("notes"),
            )
            
            lead = Lead(**lead_data.model_dump(), assigned_to=current_user.id)
            db.add(lead)
            created += 1
            
        except Exception as e:
            errors.append({"row": i, "error": str(e)})
    
    await db.commit()
    
    return {
        "created": created,
        "errors": errors,
        "total_rows": len(rows),
    }


@router.post("/export")
async def export_leads(
    request: LeadExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Export leads to CSV/Excel."""
    from app.services.lead_service import LeadService
    
    service = LeadService(db)
    file_path = await service.export_leads(
        ids=request.ids,
        filters=request.filters,
        fields=request.fields,
        format=request.format,
    )
    
    from fastapi.responses import FileResponse
    return FileResponse(
        path=file_path,
        filename=f"leads_export.{request.format}",
        media_type="application/octet-stream",
    )