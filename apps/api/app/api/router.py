from fastapi import APIRouter

from app.api.routes.ai_triage import router as ai_triage_router
from app.api.routes.audit_logs import router as audit_logs_router
from app.api.routes.collaboration_locks import router as collaboration_locks_router
from app.api.routes.gmail import router as gmail_router
from app.api.routes.health import router as health_router
from app.api.routes.imports import router as imports_router
from app.api.routes.knowledge import router as knowledge_router
from app.api.routes.internal_notes import router as internal_notes_router
from app.api.routes.me import router as me_router
from app.api.routes.members import router as members_router
from app.api.routes.metrics import router as metrics_router
from app.api.routes.operations import router as operations_router
from app.api.routes.organizations import router as organizations_router
from app.api.routes.reply_approvals import router as reply_approvals_router
from app.api.routes.reply_suggestions import router as reply_suggestions_router
from app.api.routes.response_templates import router as response_templates_router
from app.api.routes.routing_rules import router as routing_rules_router
from app.api.routes.saved_views import router as saved_views_router
from app.api.routes.status import router as status_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.tickets import router as tickets_router
from app.api.routes.webhooks import router as webhooks_router
from app.api.routes.workspace_settings import router as workspace_settings_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(status_router, prefix="/v1")
api_router.include_router(tasks_router, prefix="/v1")
api_router.include_router(me_router, prefix="/v1")
api_router.include_router(organizations_router, prefix="/v1")
api_router.include_router(members_router, prefix="/v1")
api_router.include_router(metrics_router, prefix="/v1")
api_router.include_router(operations_router, prefix="/v1")
api_router.include_router(tickets_router, prefix="/v1")
api_router.include_router(saved_views_router, prefix="/v1")
api_router.include_router(response_templates_router, prefix="/v1")
api_router.include_router(knowledge_router, prefix="/v1")
api_router.include_router(routing_rules_router, prefix="/v1")
api_router.include_router(internal_notes_router, prefix="/v1")
api_router.include_router(collaboration_locks_router, prefix="/v1")
api_router.include_router(workspace_settings_router, prefix="/v1")
api_router.include_router(gmail_router, prefix="/v1")
api_router.include_router(imports_router, prefix="/v1")
api_router.include_router(ai_triage_router, prefix="/v1")
api_router.include_router(audit_logs_router, prefix="/v1")
api_router.include_router(reply_suggestions_router, prefix="/v1")
api_router.include_router(reply_approvals_router, prefix="/v1")
api_router.include_router(webhooks_router, prefix="/v1")

