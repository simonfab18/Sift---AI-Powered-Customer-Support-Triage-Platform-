from fastapi import APIRouter, Body, Depends, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.api.rate_limits import limit_draft_creation
from app.schemas.reply_approval import GmailDirectSendRead, GmailDirectSendRequest, GmailDraftCreateRead, ReplyApprovalRead, ReplyApprovalUpdate
from app.schemas.reply_suggestion import ReplySuggestionCreate, ReplySuggestionRead, ReplySuggestionUpdate
from app.services.reply_approval_service import (
    approve_reply_suggestion as approve_legacy_reply_suggestion,
    create_gmail_draft_from_approved_suggestion as create_legacy_gmail_draft,
)
from app.services.reply_suggestion_service import (
    approve_reply_suggestion,
    create_agent_reply_suggestion,
    create_gmail_draft_from_reply_suggestion,
    list_reply_suggestions,
    reject_reply_suggestion,
    send_approved_reply_suggestion,
    update_reply_suggestion,
)

router = APIRouter(tags=["reply-suggestions"])


@router.get(
    "/orgs/{organization_id}/tickets/{ticket_id}/reply-suggestions",
    response_model=list[ReplySuggestionRead],
)
def read_reply_suggestions(
    organization_id: str,
    ticket_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    return list_reply_suggestions(db, organization_id, ticket_id, current_user)


@router.post(
    "/orgs/{organization_id}/tickets/{ticket_id}/reply-suggestions",
    response_model=ReplySuggestionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_reply_suggestion(
    organization_id: str,
    ticket_id: str,
    payload: ReplySuggestionCreate,
    db: DbSession,
    current_user: CurrentUser,
):
    return create_agent_reply_suggestion(db, organization_id, ticket_id, current_user, payload)


@router.patch(
    "/orgs/{organization_id}/reply-suggestions/{suggestion_id}",
    response_model=ReplySuggestionRead,
)
def patch_reply_suggestion(
    organization_id: str,
    suggestion_id: str,
    payload: ReplySuggestionUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    return update_reply_suggestion(db, organization_id, suggestion_id, current_user, payload)


@router.post(
    "/orgs/{organization_id}/reply-suggestions/{suggestion_id}/approve",
    response_model=ReplySuggestionRead | ReplyApprovalRead,
)
def approve_suggestion(
    organization_id: str,
    suggestion_id: str,
    db: DbSession,
    current_user: CurrentUser,
    payload: dict | None = Body(default=None),
):
    try:
        return approve_reply_suggestion(db, organization_id, suggestion_id, current_user)
    except HTTPException as exc:
        if exc.status_code != status.HTTP_404_NOT_FOUND:
            raise
    final_reply = (payload or {}).get("final_reply") or (payload or {}).get("edited_body") or "Approved reply."
    return approve_legacy_reply_suggestion(
        db,
        organization_id,
        suggestion_id,
        current_user,
        ReplyApprovalUpdate(final_reply=final_reply),
    )


@router.post(
    "/orgs/{organization_id}/reply-suggestions/{suggestion_id}/reject",
    response_model=ReplySuggestionRead,
)
def reject_suggestion(
    organization_id: str,
    suggestion_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    return reject_reply_suggestion(db, organization_id, suggestion_id, current_user)



@router.post(
    "/orgs/{organization_id}/reply-suggestions/{suggestion_id}/send-gmail-reply",
    response_model=GmailDirectSendRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limit_draft_creation)],
)
async def send_reply_suggestion(
    organization_id: str,
    suggestion_id: str,
    payload: GmailDirectSendRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    suggestion, sent_message = await send_approved_reply_suggestion(
        db,
        organization_id,
        suggestion_id,
        current_user,
        payload,
    )
    return GmailDirectSendRead(
        approval=suggestion,
        sent_message=sent_message,
        gmail_message_id=sent_message.gmail_message_id,
        test_mode=sent_message.test_mode,
    )

@router.post(
    "/orgs/{organization_id}/reply-suggestions/{suggestion_id}/create-gmail-draft",
    response_model=GmailDraftCreateRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limit_draft_creation)],
)
async def create_reply_suggestion_draft(
    organization_id: str,
    suggestion_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    try:
        suggestion, draft = await create_gmail_draft_from_reply_suggestion(
            db,
            organization_id,
            suggestion_id,
            current_user,
        )
    except HTTPException as exc:
        if exc.status_code != status.HTTP_404_NOT_FOUND:
            raise
        suggestion, draft = await create_legacy_gmail_draft(db, organization_id, suggestion_id, current_user)
    return GmailDraftCreateRead(approval=suggestion, draft=draft, gmail_draft_id=draft.gmail_draft_id)
