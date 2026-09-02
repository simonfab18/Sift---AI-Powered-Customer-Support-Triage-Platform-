from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUser, DbSession
from app.api.rate_limits import limit_draft_creation
from app.schemas.reply_approval import GmailDraftCreateRead, GmailDraftRead, ReplyApprovalRead, ReplyApprovalUpdate
from app.services.reply_approval_service import (
    approve_reply_and_create_draft,
    approve_reply_suggestion,
    create_gmail_draft_from_approved_suggestion,
    get_gmail_draft_for_ticket,
    list_reply_approvals,
    update_reply_approval,
)

router = APIRouter(tags=["reply-approvals"])


@router.get(
    "/orgs/{organization_id}/tickets/{ticket_id}/reply-approvals",
    response_model=list[ReplyApprovalRead],
)
def read_reply_approvals(
    organization_id: str,
    ticket_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    return list_reply_approvals(db, organization_id, ticket_id, current_user)


@router.patch(
    "/orgs/{organization_id}/tickets/{ticket_id}/reply-approvals/{approval_id}",
    response_model=ReplyApprovalRead,
)
def patch_reply_approval(
    organization_id: str,
    ticket_id: str,
    approval_id: str,
    payload: ReplyApprovalUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    return update_reply_approval(db, organization_id, ticket_id, approval_id, current_user, payload)


@router.post(
    "/orgs/{organization_id}/tickets/{ticket_id}/reply-approvals/{approval_id}/create-gmail-draft",
    response_model=GmailDraftCreateRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limit_draft_creation)],
)
async def create_reply_draft_compat(
    organization_id: str,
    ticket_id: str,
    approval_id: str,
    payload: ReplyApprovalUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    approval, draft = await approve_reply_and_create_draft(
        db,
        organization_id,
        ticket_id,
        approval_id,
        current_user,
        payload,
    )
    return GmailDraftCreateRead(approval=approval, draft=draft, gmail_draft_id=draft.gmail_draft_id)


@router.post(
    "/orgs/{organization_id}/reply-suggestions/{suggestion_id}/approve",
    response_model=ReplyApprovalRead,
)
def approve_suggestion(
    organization_id: str,
    suggestion_id: str,
    payload: ReplyApprovalUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    return approve_reply_suggestion(db, organization_id, suggestion_id, current_user, payload)


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
    approval, draft = await create_gmail_draft_from_approved_suggestion(
        db,
        organization_id,
        suggestion_id,
        current_user,
    )
    return GmailDraftCreateRead(approval=approval, draft=draft, gmail_draft_id=draft.gmail_draft_id)


@router.get(
    "/orgs/{organization_id}/tickets/{ticket_id}/gmail-draft",
    response_model=GmailDraftRead,
)
def read_ticket_gmail_draft(
    organization_id: str,
    ticket_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    return get_gmail_draft_for_ticket(db, organization_id, ticket_id, current_user)
