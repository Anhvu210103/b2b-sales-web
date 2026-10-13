"""Personalization prompts for different channels and scenarios."""

EMAIL_PROMPTS = {
    "initial": """You are a B2B sales representative writing a cold email to a decision maker at a Vietnamese company.

CONTEXT:
{context}

INSTRUCTIONS:
- Write a personalized, concise cold email in Vietnamese
- Maximum 150 words
- Subject line: compelling, under 50 characters
- Focus on the prospect's specific pain points based on their industry/role
- Mention 1-2 specific ChaTask features relevant to their situation
- Include a soft CTA (demo link, 15 min call)
- Tone: professional, respectful, not pushy
- DO NOT use generic templates - be specific to their company/role
- Include the opt-out line: "Nếu không đúng người/nhu cầu, anh/chị cho em biết để em dừng liên hệ."

OUTPUT FORMAT:
Subject: [subject line]

Body:
[email body]""",
    
    "followup_1": """You are following up on a previous email that wasn't opened/replied to.

CONTEXT:
{context}

PREVIOUS EMAIL:
Subject: {previous_subject}
Body: {previous_body}

INSTRUCTIONS:
- Write a brief follow-up email (under 100 words)
- Reference the previous email briefly
- Add ONE new piece of value (case study, specific feature, insight)
- Soft CTA
- Tone: polite, not pushy
- Vietnamese language

OUTPUT FORMAT:
Subject: Re: [previous subject]

Body:
[followup body]""",
    
    "followup_2": """You are sending the final follow-up email (breakup email).

CONTEXT:
{context}

PREVIOUS EMAILS:
1. {first_subject}
2. {second_subject}

INSTRUCTIONS:
- Final polite email (under 80 words)
- Acknowledge they may not be interested
- Leave the door open for future
- No hard CTA - just offer to stay in touch
- Professional, respectful tone
- Vietnamese language

OUTPUT FORMAT:
Subject: Re: [original subject]

Body:
[final followup body]""",
    
    "referral": """You are asking for a referral to the right person.

CONTEXT:
{context}

INSTRUCTIONS:
- Brief email asking if they're the right person or can forward
- Mention you don't want to waste their time
- Professional, not pushy
- Vietnamese language

OUTPUT FORMAT:
Subject: [subject]

Body:
[body]""",
}

ZALO_PROMPTS = {
    "initial": """You are writing a Zalo message to a Vietnamese business decision maker.

CONTEXT:
{context}

INSTRUCTIONS:
- Write a SHORT Zalo message (max 160 characters for first message)
- Friendly, conversational tone (like a real person)
- Mention you know their company
- Ask ONE simple question to start conversation
- NO marketing language - sound human
- Vietnamese language, casual but respectful

OUTPUT FORMAT:
[Zalo message text only]""",
    
    "followup": """You are following up on Zalo after no reply.

CONTEXT:
{context}

PREVIOUS MESSAGE: {previous_message}

INSTRUCTIONS:
- Short follow-up (max 160 chars)
- Casual, not pushy
- Add ONE new piece of value
- Vietnamese, conversational

OUTPUT FORMAT:
[Zalo message]""",
    
    "nudge": """You are sending a gentle nudge after they showed interest (opened/clicked but didn't reply).

CONTEXT: {context}

INSTRUCTIONS:
- Very short (max 160 chars)
- Reference their interest
- Low pressure
- Vietnamese

OUTPUT FORMAT:
[Zalo message]""",
}

LINKEDIN_PROMPTS = {
    "connection": """You are sending a LinkedIn connection request note (max 300 chars).

CONTEXT:
{context}

INSTRUCTIONS:
- Professional but warm
- Mention specific reason for connecting
- NO sales pitch in connection request
- Vietnamese language
- Under 300 characters

OUTPUT FORMAT:
[Connection note]""",
    
    "message": """You are sending a LinkedIn message after connection accepted.

CONTEXT:
{context}

INSTRUCTIONS:
- Professional but conversational
- Reference their profile/company
- Soft value proposition
- Ask for brief call/demo
- Vietnamese language

OUTPUT FORMAT:
[LinkedIn message]""",
}

FOLLOWUP_PROMPTS = {
    "nudge": """Write a gentle nudge email for someone who opened/clicked but didn't reply.

CONTEXT:
{context}

LAST EMAIL: {last_subject}

INSTRUCTIONS:
- Short, gentle nudge
- Reference their interest (opened/clicked)
- Add ONE new insight/value
- Soft CTA
- Vietnamese

OUTPUT FORMAT:
Subject: Re: [subject]

Body:
[body]""",
    
    "demo_followup": """Write a follow-up after a demo was completed.

CONTEXT:
{context}

DEMO NOTES: {demo_notes}

INSTRUCTIONS:
- Thank them for their time
- Summarize 2-3 key points from demo
- Address any objections raised
- Clear next steps
- Vietnamese

OUTPUT FORMAT:
Subject: [subject]

Body:
[body]""",
    
    "proposal_followup": """Write a follow-up after sending a proposal.

CONTEXT:
{context}

PROPOSAL DETAILS: {proposal_details}

INSTRUCTIONS:
- Check in on proposal review
- Offer to walk through / answer questions
- Create mild urgency if appropriate
- Vietnamese

OUTPUT FORMAT:
Subject: [subject]

Body:
[body]""",
    
    "objection_handling": """Write an email addressing a specific objection.

CONTEXT:
{context}

OBJECTION: {objection}

INSTRUCTIONS:
- Acknowledge the objection empathetically
- Provide clear, specific counter-point
- Share relevant proof point (case study, feature)
- Keep door open
- Vietnamese

OUTPUT FORMAT:
Subject: Re: [subject]

Body:
[body]""",
}


def get_prompt_for_channel(channel: str, stage: str = "initial") -> str:
    """Get the appropriate prompt template for a channel and stage."""
    if channel == "email":
        return EMAIL_PROMPTS.get(stage, EMAIL_PROMPTS["initial"])
    elif channel == "zalo":
        return ZALO_PROMPTS.get(stage, ZALO_PROMPTS["initial"])
    elif channel == "linkedin":
        return LINKEDIN_PROMPTS.get(stage, LINKEDIN_PROMPTS["connection"])
    elif stage.startswith("followup"):
        return FOLLOWUP_PROMPTS.get(stage, FOLLOWUP_PROMPTS["nudge"])
    return EMAIL_PROMPTS["initial"]


def format_context_for_prompt(context: Dict[str, Any]) -> str:
    """Format context dict into a readable string for prompt."""
    parts = []
    
    # Company info
    company = context.get("company", {})
    if company.get("name"):
        parts.append(f"Company: {company['name']}")
    if company.get("industry"):
        parts.append(f"Industry: {company['industry']}")
    if company.get("company_size"):
        parts.append(f"Size: {company['company_size']}")
    if company.get("city"):
        parts.append(f"Location: {company['city']}")
    
    # Contact
    contact = context.get("contact", {})
    if contact.get("name"):
        parts.append(f"Contact: {contact['name']}")
    if contact.get("title"):
        parts.append(f"Title: {contact['title']}")
    
    # Source & signals
    if context.get("source"):
        parts.append(f"Source: {context['source']}")
    if context.get("signals"):
        signals = [s.get("title", "") for s in context["signals"][:3] if s.get("title")]
        if signals:
            parts.append(f"Recent signals: {'; '.join(signals)}")
    
    # Scores
    scores = context.get("scores", {})
    if scores:
        parts.append(f"Fit: {scores.get('fit', 0):.0f}/100, Intent: {scores.get('intent', 0):.0f}/100")
    
    # Outreach history
    outreach = context.get("outreach_history", [])
    if outreach:
        parts.append(f"Previous outreach: {len(outreach)} touches")
        last = outreach[0]
        parts.append(f"Last: {last['channel']} - {last['status']} on {last.get('sent_at', '')[:10]}")
    
    return "\n".join(parts) if parts else "No additional context available."