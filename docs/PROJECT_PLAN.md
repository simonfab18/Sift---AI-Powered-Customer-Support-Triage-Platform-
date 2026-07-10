# Project Plan

## Current Stage

The project is past the initial MVP foundation. The app now has a Next.js frontend, FastAPI backend, Supabase-backed PostgreSQL database, Supabase Auth, Gmail OAuth, Gmail import, AI triage with Gemini, reply approvals, Gmail draft creation, dashboard views, role-aware navigation, and local development servers.

M7 staging and pilot release is partially complete locally. The repo has pilot controls, a mocked backend release smoke suite, and a new Google Cloud Run/Pub/Sub task architecture that removes Redis/Celery from staging and production. M7 remains partial until Cloud Run staging is deployed and verified end to end.

## Completed Milestones

### Milestone 1: Foundation

- Created monorepo structure.
- Added Next.js frontend with TypeScript.
- Added FastAPI backend.
- Added Docker Compose support for local API helpers; staging/production now target Cloud Run and Pub/Sub task handlers.
- Added environment templates.
- Added health check endpoint.
- Added basic CI workflow.

### Milestone 2: Database and Auth Foundation

- Connected the backend to Supabase PostgreSQL.
- Added Supabase Auth integration.
- Added authenticated user context.
- Added organization and membership models.
- Added owner, admin, and agent role concepts.

### Milestone 3: Organizations and Role Isolation

- Added organization creation and selection.
- Added member management.
- Added role-based access checks.
- Added multi-tenant organization scoping across core resources.

### Milestone 4: Gmail OAuth

- Added Gmail OAuth connect flow.
- Added encrypted refresh token storage.
- Added OAuth state validation.
- Added Gmail connection status in the UI.

### Milestone 5: Gmail Import

- Added Gmail import endpoint.
- Added import job tracking.
- Added ticket creation from Gmail messages.
- Added duplicate message protection by Gmail message ID.
- Added recent import status in the UI.

### Milestone 6: AI Triage

- Added Gemini-powered ticket triage.
- Added structured AI output validation.
- Added category, priority, sentiment, summary, suggested action, draft reply, confidence, reasoning, and human review flag.
- Added triage results to ticket detail.

### Milestone 7: Human Reply Review

- Added reply suggestions.
- Added agent editing.
- Added approve and reject actions.
- Added status lifecycle: suggested, edited, approved, rejected, draft_created.
- Added ticket events for approval actions.

### Milestone 8: Gmail Draft Creation

- Added approved-reply Gmail draft creation.
- Stored Gmail draft IDs.
- Prevented duplicate draft creation.
- Updated ticket state after draft creation.
- Exposed draft result in the UI.

### Milestone 9: Audit and Security Hardening

- Added audit logs for important actions.
- Added endpoint to view organization audit logs.
- Added safer error responses.
- Ensured sensitive Gmail token fields are not returned by API responses.
- Added organization authorization checks for key resources.


### Production M0: Release Baseline

- Added validated staging and production environment settings.
- Added migration upgrade/downgrade validation in CI.
- Added frontend lint, typecheck, production build, and container build checks.
- Documented release, rollback, environment separation, and ownership controls.

### Production M1: Live Gmail Sync Foundation

- Added Gmail watch registration after OAuth connection.
- Added Gmail watch renewal service and request-based task entrypoint.
- Added Gmail watch and sync state fields to Gmail connections.
- Added `gmail_sync_events` for watch registration, renewal, and Pub/Sub notification records.
- Added authenticated Pub/Sub webhook foundation at `POST /v1/webhooks/google/gmail`.
- Documented Google Cloud Pub/Sub project, topic, subscription, push endpoint, and service-account settings.
- Confirmed M1 stopped at authenticated notification receipt; history-based ticket ingestion was completed in M2.

### Production M2: Incremental Sync and Recovery

- Added Gmail history-list processing from stored checkpoints.
- Added duplicate-safe ticket creation for new `messagesAdded` notifications.
- Added per-connection sync locks to avoid concurrent duplicate processing.
- Added Pub/Sub webhook job enqueue, internal Pub/Sub task dispatch, and duplicate delivery handling.
- Added expired-checkpoint reconciliation with watch re-registration.
- Added stale-connection fallback sync discovery.
- Added owner/admin sync status and manual history-sync queue endpoints.



### Production M3: Automatic Triage Pipeline

- Added automatic AI triage job enqueue after manual ticket creation, manual Gmail import, and Gmail history sync ticket creation.
- Added ticket triage states for queued, running, succeeded, and failed triage.
- Added one-active-job idempotency for each ticket.
- Added prompt/schema version and latency metadata to AI triage results.
- Added request-based Cloud Run task execution for AI triage jobs.
- Added visible failure state and manual retry endpoint.
- Added workspace setting support for disabling automatic triage.
### Production M4: Core Workflow Polish

- Added centralized ticket lifecycle transition validation.
- Added `awaiting_approval` lifecycle state after successful triage.
- Added reply version tracking for approvals and suggestions.
- Editing approved replies now invalidates approval and requires reapproval.
- Draft creation now checks the latest approved reply version.
- Repeated Gmail draft creation is idempotent and returns the existing draft.
- Closed tickets cannot create Gmail drafts.
- Ticket list endpoints now support limit and offset pagination.

### Production M5: Operations and Observability

- Expanded job-run tracking with queue, attempts, timing, related resources, correlation IDs, retry eligibility, error classification, alert owner, and runbook metadata.
- Added owner/admin operations endpoints for recent workspace failures, job detail, safe retry, and Gmail sync health.
- Added a token-protected internal operations endpoint for system-wide failed jobs.
- Added structured JSON request and task logging with safe request/job/resource context.
- Added sanitized error handling so tokens, authorization headers, email bodies, and prompts are not written to normal logs.
- Added `/health/live`, `/health/ready`, and richer `/v1/status` dependency reporting.
- Added tests for operations access, retry behavior, sync-health redaction, and health/status checks.
### Production M6: Security and Tenant Hardening

- Added authorization matrix coverage for owner/admin-only surfaces, agent workflow surfaces, disabled members, and cross-organization resource IDs.
- Tightened audit-log access to owner/admin users.
- Added rate limiting for OAuth, Gmail sync/watch, triage, retry, draft creation, and member invitation actions.
- Added request body-size protection and standard API security headers.
- Added Gmail token key-version metadata and recoverable `reauthorization_required` state for revoked refresh tokens.
- Added redaction hardening for structured logs and operational errors.
- Documented secret rotation, reauthorization, data export/deletion direction, retention, backup/restore, and attachment policy.
### Production M7: Staging and Pilot Release

Local implementation added:

- Added global pilot rollout settings for organization allowlisting, Gmail sync, automatic triage queueing, and Gmail draft creation.
- Added workspace-level controls for sync, draft creation, and pilot feedback/support contact.
- Enforced pilot controls in OAuth start, Gmail import/sync/history queueing, watch registration/renewal, auto-triage queueing, and Gmail draft creation.
- Added a mocked backend release smoke test for the Gmail-to-draft path, including disconnect, reconnect, audit, resolve, and stale fallback detection.

Deferred before M7 can be called complete:

- Deploy Cloud Run API/task routes, Cloud Scheduler, Supabase database/auth, Vercel frontend, Google OAuth, Pub/Sub, Gmail test inbox, Gemini, and error tracking with separated staging configuration.
- Run the complete release suite against deployed staging without local services.
- Verify Pub/Sub task delivery, Cloud Scheduler behavior, alerts, backup/restore, rollback, and a staging soak test.
### Production M8: Agent Productivity Features

Backend implementation added:

- Added user-scoped saved ticket views with graceful filter sanitization.
- Added ticket bulk actions for assign, status change, mark spam, resolve, and safe triage retry with per-item success/failure results.
- Added workspace-owned response templates with category tags, search, version metadata, owner/admin management, and insertion into editable reply suggestions.
- Added internal notes with mention tracking, edit history, audit behavior, and separation from customer-visible Gmail drafts.
- Added collaboration locks for reply edit conflict protection.

Frontend implementation added:

- Wired saved views, bulk action controls, response templates, internal notes, note edit history, tracked mentions, and edit-lock warnings into the frontend ticket queue/detail UI.

Still required for full acceptance:

- Verify M8 workflows in staging with deployed backend credentials and representative multi-user sessions.
### Product UI Pass

- Added modern SaaS-style landing page.
- Added app shell with sidebar navigation.
- Added pages for overview, inbox, approvals, customers, analytics, integrations, workspace, team, and settings.
- Added responsive layout direction.
- Added reusable product UI components for badges, cards, queue rows, and app navigation.

### Production Architecture Migration: Google Cloud Run Tasks

- Replaced deployed Redis/Celery assumptions with Google Pub/Sub task dispatch and request-based Cloud Run task handlers.
- Added OIDC-protected task endpoints for Gmail import, Gmail history sync, AI triage, Gmail watch renewal, fallback sync, and watch-renewal scheduling.
- Kept Supabase database/auth and Vercel frontend unchanged.
- Render remains a fallback until Cloud Run staging is verified.

## Current Production Milestone: M8 Agent Productivity Features

### Goal

Agent queue handling should become faster and safer through saved views, bulk actions, templates, internal collaboration, and edit-conflict protection.

### Current M7 Deferred Items

- Redis/Celery worker verification is replaced by Cloud Run/Pub/Sub task verification.
- Full M7 acceptance still requires production-like staging with Cloud Run API/task routes, Cloud Scheduler, Supabase database/auth, Vercel frontend, Google OAuth, Pub/Sub, Gmail test inbox, Gemini, and error tracking.

### Backend Work

- Complete M8 backend APIs and database models for saved views, bulk actions, response templates, internal notes, mentions, and collaboration locks.
- Keep M7 Cloud Run/Pub/Sub/Scheduler verification deferred until the new staging deployment is live.

### Frontend Work

- Complete ticket queue saved-view controls.
- Complete multi-select and confirmation flows for bulk actions.
- Complete response template search/insert UI on ticket detail.
- Complete internal notes plus visible edit-history and mention surfaces.
- Complete edit-lock warnings for reply editing.
- Staging validation remains required for real multi-user lock behavior and deployed credential flows.
## Later Milestones

### Knowledge and Automation

- Add reusable response templates.
- Add company policy or knowledge base snippets.
- Allow AI replies to use workspace knowledge.
- Add routing or assignment rules.

### Analytics

- Response time trends.
- Triage volume by urgency.
- AI confidence distribution.
- Draft approval rate.
- Agent workload.

### Production Readiness

- Rotate all exposed development secrets.
- Confirm staging and production environment variables.
- Confirm deployed Google OAuth redirect URLs.
- Confirm deployed CORS origins.
- Confirm Cloud Run task routes, Pub/Sub push subscriptions, and Cloud Scheduler jobs are running; keep Render as fallback until verified.
- Run full end-to-end staging test.

