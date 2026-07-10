from app.models.ticket import TicketCategory, TicketPriority, TicketSentiment

TRIAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {
            "type": "string",
            "enum": [category.value for category in TicketCategory],
        },
        "priority": {
            "type": "string",
            "enum": [priority.value for priority in TicketPriority],
        },
        "sentiment": {
            "type": "string",
            "enum": [sentiment.value for sentiment in TicketSentiment],
        },
        "summary": {"type": "string"},
        "suggested_action": {"type": "string"},
        "draft_reply": {"type": "string"},
        "confidence_score": {"type": "integer", "minimum": 0, "maximum": 100},
        "reasoning": {"type": "string"},
        "requires_human_review": {"type": "boolean"},
    },
    "required": [
        "category",
        "priority",
        "sentiment",
        "summary",
        "suggested_action",
        "draft_reply",
        "confidence_score",
        "reasoning",
        "requires_human_review",
    ],
}


def build_triage_prompt(
    customer_name: str | None,
    customer_email: str,
    subject: str,
    message: str,
    knowledge_sources: list[dict] | None = None,
) -> str:
    display_name = customer_name or customer_email
    knowledge_block = ""
    if knowledge_sources:
        formatted_sources = []
        for index, source in enumerate(knowledge_sources, start=1):
            formatted_sources.append(
                f"[{index}] {source['title']} ({source['source_type']}): {source['excerpt']}"
            )
        knowledge_block = "\\nWorkspace knowledge sources. Use only these sources for company-specific facts; if none apply, say what information is missing internally.\\n" + "\\n".join(formatted_sources) + "\\n"
    return f"""You are an AI customer support triage assistant for an e-commerce company.

Analyze the customer email and return only JSON matching the provided schema.

Customer: {display_name} <{customer_email}>
Subject: {subject}
Message:
{message}
{knowledge_block}
Classification rules:
- category must be one of: order_status, refund, return, damaged_item, billing, technical_issue, account_access, product_question, complaint, spam, other.
- priority critical: safety risk, fraud, legal threat, account takeover, severe outage, or urgent high-impact complaint.
- priority high: refund/replacement/cancellation request, angry customer, damaged item, chargeback, delivery failure, or time-sensitive issue.
- priority medium: normal support request requiring action.
- priority low: simple informational question or low urgency.
- sentiment angry: hostile, threatening, or extremely frustrated.
- sentiment negative: dissatisfied or concerned.
- sentiment neutral: factual or routine.
- sentiment positive: appreciative or happy.

Human review must be true when:
- priority is critical or high.
- the email asks for refund, replacement, cancellation, credit, compensation, or billing changes.
- the email involves legal, safety, fraud, privacy, chargeback, or account access concerns.
- there is not enough information to safely answer.

Reply rules:
- draft_reply should be a helpful suggested response for a support agent to approve later.
- confidence_score must be an integer from 0 to 100 that reflects confidence in the classification and reply.
- reasoning should briefly explain the main signals used for category, priority, sentiment, and review decision.
- Do not claim that a refund, cancellation, or account change has already been completed.
- Ask for missing order/account details when needed.
- End with "Best regards,\nCustomer Support Team".
"""

