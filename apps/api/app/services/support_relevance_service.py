from __future__ import annotations

from dataclasses import dataclass

from app.models.ticket import Ticket, TicketCategory, TicketStatus

SUPPORT_SIGNALS = {
    "account", "access", "billing", "broken", "bug", "cancel", "charged", "charge", "complaint",
    "damaged", "defect", "delivery", "double charged", "error", "failed", "faulty", "help",
    "invoice", "issue", "locked", "login", "missing", "not working", "order", "payment", "problem",
    "question", "refund", "replace", "return", "shipping", "status", "support", "unable", "warranty",
}

SPAM_SIGNALS = {
    "act now", "adult", "buy followers", "casino", "click here", "crypto giveaway", "free money",
    "limited time offer", "make money fast", "miracle", "seo backlinks", "unsubscribe", "viagra",
    "winner", "you have been selected", "you have won",
}

NON_SUPPORT_SIGNALS = {
    "newsletter", "digest", "marketing", "promotion", "webinar", "event invite", "sale ends",
    "product update", "press release", "weekly update",
}

SPAM_GMAIL_LABELS = {"SPAM"}
PROMOTIONAL_GMAIL_LABELS = {"CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL", "CATEGORY_UPDATES", "CATEGORY_FORUMS"}
NO_REPLY_MARKERS = {"no-reply@", "noreply@", "donotreply@", "do-not-reply@"}


@dataclass(frozen=True)
class SupportRelevanceDecision:
    should_auto_triage: bool
    reason: str
    is_spam: bool = False


def _contains_any(text: str, signals: set[str]) -> bool:
    return any(signal in text for signal in signals)


def decide_ticket_auto_triage(ticket: Ticket, gmail_label_ids: list[str] | None = None) -> SupportRelevanceDecision:
    labels = set(gmail_label_ids or [])
    sender = (ticket.customer.email if ticket.customer else "").lower()
    text = f"{ticket.subject} {ticket.message_text}".lower()

    if ticket.status == TicketStatus.SPAM.value or ticket.category == TicketCategory.SPAM.value:
        return SupportRelevanceDecision(False, "Ticket is already marked as spam.", is_spam=True)
    if labels & SPAM_GMAIL_LABELS:
        return SupportRelevanceDecision(False, "Gmail marked this message as spam.", is_spam=True)
    if _contains_any(text, SPAM_SIGNALS):
        return SupportRelevanceDecision(False, "Message matches obvious spam patterns.", is_spam=True)

    has_support_signal = _contains_any(text, SUPPORT_SIGNALS)
    if has_support_signal:
        return SupportRelevanceDecision(True, "Message looks like a customer support request.")

    if labels & PROMOTIONAL_GMAIL_LABELS:
        return SupportRelevanceDecision(False, "Gmail categorized this message as promotional or non-support mail.", is_spam=True)
    if any(marker in sender for marker in NO_REPLY_MARKERS):
        return SupportRelevanceDecision(False, "Sender looks like a no-reply address and no support request was detected.", is_spam=True)
    if _contains_any(text, NON_SUPPORT_SIGNALS):
        return SupportRelevanceDecision(False, "Message looks like newsletter, marketing, or operational noise.", is_spam=True)

    return SupportRelevanceDecision(False, "No clear customer-support signal was detected; message was treated as non-support noise.", is_spam=True)