"""Personalization engine - AI-driven content generation."""

from typing import Optional, Dict, Any, List
from uuid import UUID
from enum import Enum
import asyncio

from openai import AsyncOpenAI
from anthropic import AsyncAnthropic

from app.config import settings
from app.personalization.context_builder import ContextBuilder
from app.personalization.prompts import (
    get_prompt_for_channel,
    format_context_for_prompt,
    EMAIL_PROMPTS,
    ZALO_PROMPTS,
    LINKEDIN_PROMPTS,
    FOLLOWUP_PROMPTS,
)


class ContentChannel(str, Enum):
    EMAIL = "email"
    ZALO = "zalo"
    LINKEDIN = "linkedin"


class PersonalizationEngine:
    """AI-powered content generation for outreach."""

    def __init__(self, db):
        self.db = db
        self.context_builder = ContextBuilder(db)

        # Initialize AI clients
        self.openai_client = None
        self.anthropic_client = None

        if settings.OPENAI_API_KEY:
            self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        if settings.ANTHROPIC_API_KEY:
            self.anthropic_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def generate_content(
        self,
        lead_id: UUID,
        channel: str,
        stage: str = "initial",
        custom_context: Optional[Dict[str, Any]] = None,
        template_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """Generate personalized content for a lead and channel."""

        # Build context
        context = await self.context_builder.build_outreach_context(lead_id, channel)

        # Merge custom context
        if custom_context:
            context = {**context, **custom_context}

        # Get prompt
        prompt_template = get_prompt_for_channel(channel, stage)
        context_str = format_context_for_prompt(context)

        # Format prompt
        prompt = prompt_template.format(
            context=context_str,
            previous_subject=custom_context.get("previous_subject", "") if custom_context else "",
            previous_body=custom_context.get("previous_body", "") if custom_context else "",
            previous_message=custom_context.get("previous_message", "") if custom_context else "",
            first_subject=custom_context.get("first_subject", "") if custom_context else "",
            second_subject=custom_context.get("second_subject", "") if custom_context else "",
            demo_notes=custom_context.get("demo_notes", "") if custom_context else "",
            proposal_details=custom_context.get("proposal_details", "") if custom_context else "",
            objection=custom_context.get("objection", "") if custom_context else "",
        )

        # Generate with AI
        content = await self._call_ai(prompt, channel)

        # Parse output
        parsed = self._parse_output(content, channel)

        return {
            "subject": parsed.get("subject", ""),
            "body": parsed.get("body", content),
            "channel": channel,
            "stage": stage,
            "raw_prompt": prompt,
            "raw_response": content,
        }

    async def generate_batch(
        self,
        lead_ids: List[UUID],
        channel: str,
        stage: str = "initial",
    ) -> List[Dict[str, Any]]:
        """Generate content for multiple leads."""
        results = []

        for lead_id in lead_ids:
            try:
                content = await self.generate_content(lead_id, channel, stage)
                content["lead_id"] = str(lead_id)
                results.append(content)

                # Rate limiting
                await asyncio.sleep(0.5)

            except Exception as e:
                results.append({
                    "lead_id": str(lead_id),
                    "error": str(e),
                    "subject": "",
                    "body": "",
                })

        return results

    async def generate_sequence_content(
        self,
        lead_id: UUID,
        sequence_id: UUID,
    ) -> List[Dict[str, Any]]:
        """Generate content for all steps in a sequence."""
        from app.models.outreach import OutreachSequence as OutreachSequenceModel, SequenceStep

        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        result = await self.db.execute(
            select(OutreachSequenceModel)
            .options(selectinload(OutreachSequenceModel.steps))
            .where(OutreachSequenceModel.id == sequence_id)
        )
        sequence = result.scalar_one_or_none()

        if not sequence:
            return []

        results = []
        for step in sorted(sequence.steps, key=lambda s: s.step_number):
            if not step.is_active:
                continue

            stage = "followup_1" if step.step_number == 2 else "followup_2" if step.step_number >= 3 else "initial"

            content = await self.generate_content(
                lead_id=lead_id,
                channel=step.channel.value,
                stage=stage,
                custom_context={
                    "sequence_id": str(sequence.id),
                    "step_number": step.step_number,
                    "step_delay": step.delay_days,
                },
            )
            content["step_number"] = step.step_number
            content["channel"] = step.channel.value
            content["delay_days"] = step.delay_days
            results.append(content)

        return results

    async def generate_ab_test_variants(
        self,
        lead_id: UUID,
        channel: str,
        stage: str = "initial",
        variants: int = 3,
    ) -> List[Dict[str, Any]]:
        """Generate A/B test variants."""
        results = []

        for i in range(variants):
            try:
                content = await self.generate_content(
                    lead_id=lead_id,
                    channel=channel,
                    stage=stage,
                    custom_context={"variant": i + 1},
                )
                content["variant"] = i + 1
                results.append(content)

                await asyncio.sleep(0.3)

            except Exception as e:
                results.append({
                    "variant": i + 1,
                    "error": str(e),
                })

        return results

    async def _call_ai(self, prompt: str, channel: str) -> str:
        """Call AI model to generate content."""

        # Try OpenAI first
        if self.openai_client:
            try:
                response = await self.openai_client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": "You are a B2B sales expert writing personalized outreach for Vietnamese companies. Write in Vietnamese."},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=settings.OPENAI_MAX_TOKENS,
                    temperature=settings.OPENAI_TEMPERATURE,
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                print(f"OpenAI error: {e}")

        # Fallback to Anthropic
        if self.anthropic_client:
            try:
                response = await self.anthropic_client.messages.create(
                    model=settings.ANTHROPIC_MODEL,
                    max_tokens=settings.OPENAI_MAX_TOKENS,
                    temperature=settings.OPENAI_TEMPERATURE,
                    system="You are a B2B sales expert writing personalized outreach for Vietnamese companies. Write in Vietnamese.",
                    messages=[{"role": "user", "content": prompt}],
                )
                return response.content[0].text.strip()
            except Exception as e:
                print(f"Anthropic error: {e}")

        # Fallback template
        return self._fallback_template()

    def _fallback_template(self) -> str:
        """Fallback template when AI is unavailable."""
        return """Subject: ChaTask - Giải pháp quản lý việc cho doanh nghiệp

Chào anh/chị,

Em là Phạm Anh Vũ bên ChaTask (TCOM). Em xin phép liên hệ về giải pháp quản lý công việc cho doanh nghiệp.

ChaTask giúp gom việc, trao đổi, tài liệu vào một chỗ, tự nhắc khi sắp đến hạn.

Anh/chị xem thử bản demo 3 phút: https://www.youtube.com/watch?v=4YJL4CYIsFA

Nếu không đúng người/nhu cầu, anh/chị cho em biết để em dừng liên hệ.

Trân trọng,
Phạm Anh Vũ — TCOM
0948810774"""

    def _parse_output(self, content: str, channel: str) -> Dict[str, str]:
        """Parse AI output into subject/body."""
        lines = content.strip().split("\n")
        subject = ""
        body_lines = []
        subject_found = False

        for line in lines:
            if line.lower().startswith("subject:"):
                subject = line.split(":", 1)[1].strip()
                subject_found = True
            elif line.lower().startswith("body:"):
                body_found = True
            elif subject_found and not body_found:
                body_lines.append(line)
            elif subject_found or body_found:
                body_lines.append(line)

        body = "\n".join(body_lines).strip() if body_lines else content

        return {
            "subject": subject,
            "body": body,
        }

    async def improve_content(
        self,
        original_content: str,
        feedback: str,
        channel: str,
    ) -> str:
        """Improve content based on feedback."""
        prompt = f"""
        Improve this {channel} outreach content based on the feedback.

        ORIGINAL:
        {original_content}

        FEEDBACK:
        {feedback}

        Provide the improved version only, in Vietnamese.
        """

        return await self._call_ai(prompt, channel)

    async def optimize_subject_line(
        self,
        subject: str,
        channel: str,
        context: Dict[str, Any],
    ) -> List[str]:
        """Generate optimized subject line variants."""
        context_str = format_context_for_prompt(context)

        prompt = f"""
        Generate 5 optimized subject lines for a {channel} outreach.

        CURRENT SUBJECT: {subject}
        CONTEXT: {context_str}

        Requirements:
        - Under 50 characters
        - High open rate potential
        - Vietnamese language
        - Not clickbait, but compelling
        - Different angles (curiosity, value, urgency, personal, question)

        Output: 5 lines, one per subject line.
        """

        response = await self._call_ai(prompt, "email")
        return [s.strip() for s in response.strip().split("\n") if s.strip()]
