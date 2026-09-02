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
- Do not use category other when any named category is a reasonable fit. Use other only for messages unrelated to the business, unclear after reading subject and body, or outside these categories.
- category order_status: shipping, delivery, tracking, missing package, delayed order, order confirmation, address change before shipment, or "where is my order".
- category refund: refund, cancellation with money back, credit, compensation, charge reversal, overcharge refund, or money-back request.
- category return: return request, exchange request, return label, wrong size/color, unwanted item, or return policy question.
- category damaged_item: broken, defective, damaged, missing part, not working on arrival, or photo/evidence of damage.
- category billing: invoice, payment failed, duplicate charge, chargeback, receipt, tax, payment method, subscription/payment issue.
- category technical_issue: website/app checkout error, login page error not caused by forgotten credentials, integration failure, bug, or upload/download problem.
- category account_access: cannot sign in, password reset, locked account, email/account change, suspected account takeover.
- category product_question: sizing, compatibility, stock, features, ingredients/materials, warranty, or pre-purchase question.
- category complaint: angry service complaint, escalation, bad experience, repeated unresolved issue, or manager/legal escalation that is not better classified above.
- category spam: obvious ads, phishing, scams, unrelated solicitations, empty/nonsense mail, or malicious-looking content.
- priority critical: safety risk, fraud, legal threat, account takeover, severe outage, chargeback/legal escalation, or urgent high-impact complaint.
- priority high: refund/replacement/cancellation request, angry customer, damaged item, missing/delayed delivery with urgency, billing dispute, or time-sensitive issue.
- priority medium: normal support request requiring action, including ordinary order status, return, product, technical, or account help.
- priority low: simple informational question, thanks/follow-up with no action needed, or low urgency pre-purchase question.
- Avoid defaulting to medium. Choose high when money, access, damage, delivery failure, cancellation, or strong frustration is involved. Choose low when no action or only simple information is needed.
- sentiment angry: hostile, threatening, repeated frustration, all-caps anger, insults, legal threats, or explicit escalation.
- sentiment negative: dissatisfied, worried, disappointed, blocked, delayed, confused in a problematic way, or requesting correction.
- sentiment neutral: factual or routine with no clear emotion.
- sentiment positive: appreciative, happy, complimentary, or satisfied.

Examples:
- "Where is my order? Tracking has not moved for 5 days" -> category order_status, priority medium, sentiment negative.
- "I was charged twice, refund me now" -> category refund, priority high, sentiment angry or negative.
- "The item arrived broken" -> category damaged_item, priority high, sentiment negative.
- "I cannot log in to my account" -> category account_access, priority high if locked out/urgent, otherwise medium.
- "Do you have this in blue?" -> category product_question, priority low, sentiment neutral.
- "Your service is terrible and I want a manager" -> category complaint, priority high, sentiment angry.

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

