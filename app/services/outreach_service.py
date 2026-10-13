"""Outreach service - multi-channel outreach management."""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.outreach import (
    OutreachLog, OutreachChannel, OutreachStatus,
    OutreachTemplate, OutreachSequence, OutreachCampaign,
    SequenceStep, OutreachSequence as OutreachSequenceModel
)
from app.models.lead import Lead, LeadStatus
from app.models.deal import Deal, DealStage, DealActivity, ActivityType
from app.models.user import User
from app.schemas.outreach import OutreachSendRequest, OutreachStatsResponse
from app.core.security import create_access_token


class OutreachService:
    """Service for managing multi-channel outreach."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # ==================== Email ====================
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        from_email: str,
        from_name: str,
        lead_id: Optional[UUID] = None,
        template_id: Optional[UUID] = None,
        sequence_id: Optional[UUID] = None,
        campaign_id: Optional[UUID] = None,
        track_opens: bool = True,
        track_clicks: bool = True,
    ) -> OutreachLog:
        """Send email via SMTP."""
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from email.utils import formataddr
        import random
        
        from app.config import settings
        
        # Create outreach log
        log = OutreachLog(
            lead_id=lead_id,
            channel="email",
            sequence_id=sequence_id,
            campaign_id=campaign_id,
            recipient_email=to_email,
            subject=subject,
            body=body,
            template_id=None,
            status=OutreachStatus.PENDING,
            sent_by=None,
        )
        self.db.add(log)
        await self.db.flush()
        
        # Build email
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = formataddr((from_name, from_email))
        msg["To"] = to_email
        
        # Add tracking pixel if enabled
        if track_opens:
            tracking_pixel = f'<img src="https://api.yourdomain.com/track/open/{log.id}" width="1" height="1" />'
            body = body.replace("</body>", f"{tracking_pixel}</body>")
        
        # Add click tracking
        if track_clicks:
            # This would replace links with tracked versions
            pass
        
        html_part = MIMEText(body, "html", "utf-8")
        text_part = MIMEText(self._html_to_text(body), "plain", "utf-8")
        msg.attach(text_part)
        msg.attach(html_part)
        
        # Send
        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                if settings.SMTP_USE_TLS:
                    server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)
            
            log.status = OutreachStatus.SENT
            log.sent_at = datetime.utcnow()
            log.external_id = f"smtp_{uuid4().hex[:12]}"
            
        except Exception as e:
            log.status = OutreachStatus.FAILED
            log.error_message = str(e)
        
        await self.db.commit()
        await self.db.refresh(log)
        return log
    
    async def send_email_batch(
        self,
        request: Any,  # OutreachSendRequest
        sender: User,
    ) -> Dict[str, Any]:
        """Send batch of emails."""
        from app.config import settings
        
        results = {"sent": 0, "failed": 0, "skipped": 0, "errors": []}
        
        for lead_id in request.lead_ids:
            # Check daily limit
            today_sent = await self._count_sent_today(sender.id)
            if today_sent >= settings.OUTREACH_DAILY_LIMIT:
                results["skipped"] += 1
                results["errors"].append(f"Daily limit reached for lead {lead_id}")
                continue
            
            # Get lead
            from app.models.lead import Lead
            lead = await self.db.get(Lead, lead_id)
            if not lead or not lead.primary_email:
                results["failed"] += 1
                results["errors"].append(f"No email for lead {lead_id}")
                continue
            
            # Get template or use custom content
            if request.template_id:
                template = await self.db.get(OutreachTemplate, request.template_id)
                subject = template.subject
                body = self._personalize_body(template.body, lead, sender)
            else:
                subject = request.custom_subject or "ChaTask - Giải pháp quản lý công việc"
                body = request.custom_body or self._default_body(lead, sender)
            
            # Send
            log = await self.send_email(
                to_email=lead.primary_email,
                subject=subject,
                body=body,
                from_email=settings.SMTP_FROM,
                from_name=f"{sender.full_name} - {sender.email}",
                lead_id=lead.id,
                template_id=request.template_id,
                sequence_id=request.sequence_id,
                campaign_id=request.campaign_id,
            )
            
            if log.status == "sent":
                results["sent"] += 1
            else:
                results["failed"] += 1
                results["errors"].append(f"{lead_id}: {log.error_message}")
            
            # Delay between emails
            import asyncio
            await asyncio.sleep(random.uniform(8, 15))
        
        return results
    
    # ==================== Zalo ====================
    
    async def send_zalo(
        self,
        to_phone: str,
        message: str,
        lead_id: Optional[UUID] = None,
        sender: Optional[User] = None,
    ) -> OutreachLog:
        """Send Zalo message via Zalo OA API."""
        import aiohttp
        import json
        
        from app.config import settings
        
        log = OutreachLog(
            lead_id=lead_id,
            channel="zalo",
            recipient_phone=to_phone,
            body=message,
            status=OutreachStatus.PENDING,
        )
        self.db.add(log)
        await self.db.flush()
        
        # Get access token
        token = await self._get_zalo_access_token()
        if not token:
            log.status = OutreachStatus.FAILED
            log.error_message = "No Zalo access token"
            await self.db.commit()
            return log
        
        url = "https://openapi.zalo.me/v3.0/oa/message/cs"
        headers = {
            "access_token": token,
            "Content-Type": "application/json",
        }
        
        payload = {
            "recipient": {"phone": to_phone},
            "message": {"text": message},
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as resp:
                    result = await resp.json()
                    if result.get("error") == 0:
                        log.status = "sent"
                        log.sent_at = datetime.utcnow()
                        log.external_id = result.get("msg_id")
                    else:
                        log.status = "failed"
                        log.error_message = result.get("message", "Unknown error")
        except Exception as e:
            log.status = "failed"
            log.error_message = str(e)
        
        await self.db.commit()
        await self.db.refresh(log)
        return log
    
    async def _get_zalo_access_token(self) -> Optional[str]:
        """Get or refresh Zalo OA access token."""
        from app.config import settings
        
        # Check if we have a valid token cached
        # This would need to be implemented with proper token storage
        return settings.ZALO_OA_ACCESS_TOKEN
    
    # ==================== LinkedIn ====================
    
    async def send_linkedin(
        self,
        profile_url: str,
        message: str,
        lead_id: Optional[UUID] = None,
        sender: Optional[User] = None,
    ) -> OutreachLog:
        """Send LinkedIn connection request or message."""
        # This would integrate with LinkedIn API or automation
        # For now, create a log entry for manual tracking
        log = OutreachLog(
            lead_id=lead_id,
            channel="linkedin",
            recipient_linkedin=profile_url,
            body=message,
            status="pending",
        )
        self.db.add(log)
        await self.db.commit()
        return log
    
    # ==================== Sequences ====================
    
    async def enroll_in_sequence(
        self,
        lead_id: UUID,
        sequence_id: UUID,
        sender: User,
    ) -> OutreachLog:
        """Enroll a lead in an outreach sequence."""
        sequence = await self.db.get(OutreachSequenceModel, sequence_id)
        if not sequence or not sequence.is_active:
            raise ValueError("Invalid or inactive sequence")
        
        lead = await self.db.get(Lead, lead_id)
        if not lead:
            raise ValueError("Lead not found")
        
        # Get first step
        step = await self.db.execute(
            select(SequenceStep)
            .where(
                and_(
                    SequenceStep.sequence_id == sequence_id,
                    SequenceStep.step_number == 1,
                    SequenceStep.is_active == True,
                )
            )
        )
        step = step.scalar_one_or_none()
        if not step:
            raise ValueError("No active steps in sequence")
        
        # Create first outreach log
        log = OutreachLog(
            lead_id=lead_id,
            channel=step.channel,
            sequence_id=sequence_id,
            step_number=1,
            recipient_email=lead.primary_email,
            recipient_phone=lead.primary_phone,
            recipient_name=lead.primary_contact_name or lead.company_name,
            template_id=step.template_id,
            status="pending",
            scheduled_at=datetime.utcnow(),
        )
        
        self.db.add(log)
        await self.db.commit()
        return log
    
    async def process_sequences(self) -> Dict[str, int]:
        """Process all pending sequence steps (run via cron)."""
        results = {"processed": 0, "sent": 0, "failed": 0, "scheduled": 0}
        
        # Get pending sequence logs
        result = await self.db.execute(
            select(OutreachLog).where(
                and_(
                    OutreachLog.sequence_id.isnot(None),
                    OutreachLog.status.in_(["pending", "scheduled"]),
                    or_(
                        OutreachLog.scheduled_at.is_(None),
                        OutreachLog.scheduled_at <= datetime.utcnow(),
                    ),
                )
            ).options(selectinload(OutreachLog.sequence).selectinload(OutreachSequenceModel.steps))
        )
        pending_logs = result.scalars().all()
        
        for log in pending_logs:
            try:
                if log.status == "pending":
                    # Send now
                    await self._send_sequence_step(log)
                    results["sent"] += 1
                else:
                    # Scheduled for future
                    results["scheduled"] += 1
            except Exception as e:
                results["failed"] += 1
        
        await self.db.commit()
        return results
    
    async def _send_sequence_step(self, log: OutreachLog):
        """Send a single sequence step."""
        if not log.sequence:
            return
        
        # Find the step
        step = next(
            (s for s in log.sequence.steps if s.step_number == log.step_number),
            None,
        )
        if not step or not step.is_active:
            log.status = "failed"
            log.error_message = "Step not found or inactive"
            return
        
        # Get template
        template = await self.db.get(OutreachTemplate, step.template_id) if step.template_id else None
        
        # Prepare content
        subject = step.custom_subject or template.subject if template else None
        body = step.custom_body or template.body if template else None
        
        if not body:
            log.status = "failed"
            log.error_message = "No content for step"
            return
        
        # Get lead
        lead = await self.db.get(Lead, log.lead_id)
        if not lead:
            log.status = "failed"
            log.error_message = "Lead not found"
            return
        
        # Personalize
        body = self._personalize_body(body, lead)
        if subject:
            subject = self._personalize_body(subject, lead)
        
        # Send based on channel
        if step.channel == "email" and log.recipient_email:
            await self.send_email(
                to_email=log.recipient_email,
                subject=subject or "",
                body=body,
                from_email="noreply@yourdomain.com",
                from_name="Sales Team",
                lead_id=log.lead_id,
                template_id=step.template_id,
                sequence_id=log.sequence_id,
            )
        elif step.channel == "zalo" and log.recipient_phone:
            await self.send_zalo(
                to_phone=log.recipient_phone,
                message=body,
                lead_id=log.lead_id,
            )
        elif step.channel == "linkedin" and log.recipient_linkedin:
            await self.send_linkedin(
                profile_url=log.recipient_linkedin,
                message=body,
                lead_id=log.lead_id,
            )
        
        # Schedule next step
        if log.step_number < log.sequence.max_steps:
            next_step = log.step_number + 1
            next_delay = log.sequence.step_delays[next_step - 1] if next_step <= len(log.sequence.step_delays) else 3
            scheduled_at = datetime.utcnow() + timedelta(days=next_delay)
            
            next_log = OutreachLog(
                lead_id=log.lead_id,
                channel=step.channel,  # Will be updated when next step processed
                sequence_id=log.sequence_id,
                step_number=next_step,
                status="scheduled",
                scheduled_at=scheduled_at,
            )
            self.db.add(next_log)
    
    # ==================== Campaigns ====================
    
    async def start_campaign(self, campaign_id: UUID) -> Dict[str, Any]:
        """Start an outreach campaign."""
        from app.models.outreach import OutreachCampaign
        
        result = await self.db.execute(
            select(OutreachCampaign).where(OutreachCampaign.id == campaign_id)
        )
        campaign = result.scalar_one_or_none()
        
        if not campaign:
            raise ValueError("Campaign not found")
        
        if campaign.status not in ("draft", "scheduled"):
            raise ValueError(f"Cannot start campaign in status: {campaign.status}")
        
        campaign.status = "running"
        campaign.started_at = datetime.utcnow()
        await self.db.commit()
        
        # This would trigger the campaign processor (run via cron)
        return {"message": "Campaign started", "campaign_id": str(campaign_id)}
    
    async def process_campaigns(self) -> Dict[str, int]:
        """Process all running campaigns (run via cron)."""
        results = {"enrolled": 0, "sent": 0, "completed": 0}
        
        result = await self.db.execute(
            select(OutreachCampaign).where(OutreachCampaign.status == "running")
        )
        campaigns = result.scalars().all()
        
        for campaign in campaigns:
            if campaign.end_at and campaign.end_at < datetime.utcnow():
                campaign.status = "completed"
                campaign.completed_at = datetime.utcnow()
                results["completed"] += 1
                continue
            
            # Check daily limit
            today_sent = await self._count_campaign_sent_today(campaign.id)
            if today_sent >= campaign.daily_limit:
                continue
            
            # Get leads to enroll
            remaining_today = campaign.daily_limit - today_sent
            leads = await self._get_campaign_leads(campaign, remaining_today)
            
            for lead in leads:
                if campaign.sequence_id:
                    await self.enroll_in_sequence(lead.id, campaign.sequence_id, User())
                    results["enrolled"] += 1
                else:
                    # Direct send
                    pass
        
        await self.db.commit()
        return results
    
    # ==================== Helpers ====================
    
    def _personalize_body(self, body: str, lead: Lead, sender: Optional[User] = None) -> str:
        """Personalize template with lead and sender data."""
        replacements = {
            "{company_name}": lead.company_name or "anh/chị",
            "{contact_name}": lead.primary_contact_name or "anh/chị",
            "{contact_title}": lead.primary_contact_title or "",
            "{company_website}": lead.website or "",
            "{sender_name}": "Phạm Anh Vũ",
            "{sender_title}": "Business Development",
            "{sender_company}": "Công ty Cổ phần TCOM",
            "{sender_phone}": "0948810774",
            "{sender_email}": "vuphamanh@tcom.vn",
            "{demo_url}": "https://www.youtube.com/watch?v=4YJL4CYIsFA",
            "{opt_out}": "Nếu không đúng người/nhu cầu, anh/chị cho em biết để em dừng liên hệ.",
        }
        
        result = body
        for key, value in replacements.items():
            result = result.replace(key, value)
        
        return result
    
    def _default_body(self, lead: Lead, sender: User) -> str:
        """Default email body."""
        return f"""
        <p>Chào {lead.primary_contact_name or 'anh/chị'},</p>
        
        <p>Em là Phạm Anh Vũ bên ChaTask (TCOM). Em xin phép liên hệ về giải pháp quản lý công việc cho {lead.company_name}.</p>
        
        <p><strong>ChaTask giúp:</strong></p>
        <ul>
            <li>Gom việc, trao đổi, tài liệu vào một chỗ</li>
            <li>Tự nhắc việc sắp đến hạn, quá hạn</li>
            <li>Báo cáo tiến độ tự động</li>
        </ul>
        
        <p>Em xin gửi anh/chị bản demo 3 phút: https://www.youtube.com/watch?v=4YJL4CYIsFA</p>
        
        <p>Nếu không đúng người/nhu cầu, anh/chị cho em biết để em dừng liên hệ.</p>
        
        <p>Trân trọng,<br>Phạm Anh Vũ — TCOM<br>0948810774</p>
        """
    
    async def _count_sent_today(self, user_id: UUID) -> int:
        """Count emails sent today by user."""
        today = datetime.utcnow().date()
        result = await self.db.execute(
            select(func.count(OutreachLog.id)).where(
                and_(
                    OutreachLog.sent_by == user_id,
                    OutreachLog.status == "sent",
                    func.date(OutreachLog.sent_at) == today,
                )
            )
        )
        return result.scalar() or 0
    
    async def _count_campaign_sent_today(self, campaign_id: UUID) -> int:
        today = datetime.utcnow().date()
        result = await self.db.execute(
            select(func.count(OutreachLog.id)).where(
                and_(
                    OutreachLog.campaign_id == campaign_id,
                    OutreachLog.status == "sent",
                    func.date(OutreachLog.sent_at) == today,
                )
            )
        )
        return result.scalar() or 0
    
    async def _get_campaign_leads(self, campaign: Any, limit: int) -> List[Lead]:
        """Get leads for campaign based on filters."""
        query = select(Lead)
        
        if campaign.lead_filters:
            filters = campaign.lead_filters
            if filters.get("source"):
                query = query.where(Lead.source.in_(filters["source"]))
            if filters.get("status"):
                query = query.where(Lead.status.in_(filters["status"]))
            if filters.get("industry"):
                query = query.where(Lead.industry.in_(filters["industry"]))
        
        # Exclude already enrolled
        enrolled_leads = select(OutreachLog.lead_id).where(
            OutreachLog.campaign_id == campaign.id
        )
        query = query.where(Lead.id.not_in(enrolled_leads))
        
        query = query.limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_stats(self) -> OutreachStatsResponse:
        """Get outreach statistics."""
        # Total sent
        total_sent = await self.db.scalar(
            select(func.count(OutreachLog.id)).where(OutreachLog.status == "sent")
        )
        
        total_delivered = await self.db.scalar(
            select(func.count(OutreachLog.id)).where(OutreachLog.status == "delivered")
        )
        total_opened = await self.db.scalar(
            select(func.count(OutreachLog.id)).where(OutreachLog.opened_at.isnot(None))
        )
        total_clicked = await self.db.scalar(
            select(func.count(OutreachLog.id)).where(OutreachLog.clicked_at.isnot(None))
        )
        total_replied = await self.db.scalar(
            select(func.count(OutreachLog.id)).where(OutreachLog.replied_at.isnot(None))
        )
        total_bounced = await self.db.scalar(
            select(func.count(OutreachLog.id)).where(OutreachLog.status == "bounced")
        )
        
        total = total_sent or 0
        
        # By channel
        by_channel = {}
        for channel in ["email", "zalo", "linkedin", "phone"]:
            sent = await self.db.scalar(
                select(func.count(OutreachLog.id)).where(
                    and_(OutreachLog.channel == channel, OutreachLog.status == "sent")
                )
            )
            opened = await self.db.scalar(
                select(func.count(OutreachLog.id)).where(
                    and_(OutreachLog.channel == channel, OutreachLog.opened_at.isnot(None))
                )
            )
            replied = await self.db.scalar(
                select(func.count(OutreachLog.id)).where(
                    and_(OutreachLog.channel == channel, OutreachLog.replied_at.isnot(None))
                )
            )
            by_channel[channel] = {
                "sent": sent or 0,
                "opened": opened or 0,
                "replied": replied or 0,
            }
        
        return OutreachStatsResponse(
            total_sent=total_sent or 0,
            total_delivered=total_delivered or 0,
            total_opened=total_opened or 0,
            total_clicked=0,
            total_replied=total_replied or 0,
            total_bounced=0,
            open_rate=0,
            click_rate=0,
            reply_rate=round((total_replied or 0) / (total_sent or 1) * 100, 2),
            bounce_rate=0,
            by_channel=by_channel,
        )