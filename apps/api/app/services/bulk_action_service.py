from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedUser
from app.schemas.bulk_action import TicketBulkActionItemResult, TicketBulkActionRequest, TicketBulkActionResponse
from app.schemas.ticket import TicketAssign
from app.services.audit_log_service import create_audit_log
from app.services.job_queue_service import enqueue_ticket_triage
from app.services.rbac_service import require_membership
from app.services.ticket_service import assign_ticket, get_ticket_or_404, mark_ticket_spam, resolve_ticket, update_ticket
from app.schemas.ticket import TicketUpdate

DESTRUCTIVE_ACTIONS = {"mark_spam", "resolve"}


def run_ticket_bulk_action(
    db: Session,
    organization_id: str,
    actor: AuthenticatedUser,
    payload: TicketBulkActionRequest,
) -> TicketBulkActionResponse:
    require_membership(db, organization_id, actor)
    action = payload.action
    if action in DESTRUCTIVE_ACTIONS and not payload.confirm:
        raise HTTPException(status_code=400, detail="Bulk destructive action requires confirmation")

    results: list[TicketBulkActionItemResult] = []
    for ticket_id in payload.ticket_ids:
        try:
            if action == "assign":
                ticket = assign_ticket(db, organization_id, ticket_id, actor, TicketAssign(assigned_to_user_id=payload.assigned_to_user_id))
            elif action == "change_status":
                if payload.status is None:
                    raise HTTPException(status_code=400, detail="Status is required")
                ticket = update_ticket(db, organization_id, ticket_id, actor, TicketUpdate(status=payload.status))
            elif action == "mark_spam":
                ticket = mark_ticket_spam(db, organization_id, ticket_id, actor)
            elif action == "resolve":
                ticket = resolve_ticket(db, organization_id, ticket_id, actor)
            elif action == "rerun_triage":
                ticket = get_ticket_or_404(db, organization_id, ticket_id, actor)
                enqueue_ticket_triage(db, organization_id, ticket_id, actor, force=True, raise_on_enqueue_error=False)
                ticket = get_ticket_or_404(db, organization_id, ticket_id, actor)
            else:
                raise HTTPException(status_code=400, detail="Unsupported bulk action")
            create_audit_log(
                db,
                organization_id,
                actor.id,
                "ticket.bulk_action_item_succeeded",
                "ticket",
                ticket_id,
                metadata={"action": action},
            )
            db.commit()
            results.append(TicketBulkActionItemResult(ticket_id=ticket_id, success=True, ticket=ticket))
        except HTTPException as exc:
            db.rollback()
            results.append(TicketBulkActionItemResult(ticket_id=ticket_id, success=False, error=str(exc.detail)))
        except Exception as exc:
            db.rollback()
            results.append(TicketBulkActionItemResult(ticket_id=ticket_id, success=False, error=str(exc)))
    return TicketBulkActionResponse(action=action, results=results)

