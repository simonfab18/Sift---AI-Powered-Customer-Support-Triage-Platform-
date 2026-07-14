# Project Plan

## Current Stage

The project is past the initial MVP foundation. The app now has a Next.js frontend, FastAPI backend, Supabase-backed PostgreSQL database, Supabase Auth, Gmail OAuth, Gmail import, AI triage with Gemini, reply approvals, Gmail draft creation, dashboard views, role-aware navigation, knowledge/routing/SLA backend services, analytics/admin surfaces, multiple-Gmail-inbox support in local implementation, and local development servers.

M7 staging and pilot release is verified for the core Cloud Run staging path. The repo has pilot controls, a mocked backend release smoke suite, and a Google Cloud Run/Pub/Sub task architecture that removes Redis/Celery from staging and production. Gemini is configured for free-only operation with an app-side daily triage cap; Google Cloud Error Reporting is enabled for the Cloud Run staging backend, and the Vercel production alias rollback/restore proof is complete.

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
- Added versioned Gmail token keyring support so previous encryption keys can remain readable during key rotation.
- Added redaction hardening for structured logs and operational errors.
- Documented secret rotation, reauthorization, data export/deletion direction, retention, backup/restore, and attachment policy.
### Production M7: Staging and Pilot Release

Local implementation added:

- Added global pilot rollout settings for organization allowlisting, Gmail sync, automatic triage queueing, and Gmail draft creation.
- Added workspace-level controls for sync, draft creation, and pilot feedback/support contact.
- Enforced pilot controls in OAuth start, Gmail import/sync/history queueing, watch registration/renewal, auto-triage queueing, and Gmail draft creation.
- Added a mocked backend release smoke test for the Gmail-to-draft path, including disconnect, reconnect, audit, resolve, and stale fallback detection.

Staging verification completed:

- Deployed Cloud Run API/task routes with Supabase database/auth, Vercel frontend configuration, Google OAuth, Pub/Sub push subscriptions, Gmail test inbox flow, and Cloud Scheduler jobs.
- Verified Cloud Run health, Supabase migrations, Gmail OAuth connect, Gmail sync/import, Gmail Pub/Sub webhook routing, and request-based Pub/Sub task subscriptions.
- Added scheduler jobs for fallback sync and watch-renewal scans using Google OIDC authentication.

Remaining M7 limitations before a real production pilot:

- Gemini is configured for free-only pilot usage. `AI_TRIAGE_DAILY_GEMINI_LIMIT` defaults to `20` per UTC day so the backend defers extra AI triage jobs before repeatedly hitting provider quota.
- Google Cloud Error Reporting is enabled on Cloud Run staging with `ERROR_TRACKING_PROVIDER=google-cloud`; the Error Reporting API is enabled, the runtime service account has `roles/errorreporting.writer`, Cloud Run traffic is on revision `sift-api-staging-00039-8dc`, and controlled event group `CJzzx9Gtis-cSg` verified delivery; the group count reached `2` after the 2026-07-13 recheck.
- Backup/restore drill passed on 2026-07-13. Cloud Run rollback/restore path passed on 2026-07-13; Vercel production alias rollback and restore path passed on 2026-07-13. Staging soak passed on 2026-07-13 for sync/import/watch health and approval-to-draft verification. Staging sensitive Cloud Run values now load from Google Secret Manager; encryption-key multi-key decrypt support is deployed; staging Gemini key rotation is complete; Google OAuth client secret version 2 is deployed to Secret Manager, Gmail reconnect succeeded, Secret Manager version 1 is disabled, and the old Google Console OAuth secret is disabled; Supabase backend secret rotation is complete; staging `ENCRYPTION_KEY` rotation is complete with old Gmail token version `1` retained in `ENCRYPTION_KEYRING`; staging Supabase database/pooler password rotation is complete; Cloud Run traffic is on `sift-api-staging-00039-8dc`; Scheduler/Pub/Sub/Error Reporting rechecks passed on 2026-07-13.
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
- Render may remain available as fallback, but the verified staging baseline now uses Cloud Run, Pub/Sub, Cloud Scheduler, Vercel, and Supabase.

### Production M11: Product Expansion - Multiple Gmail Inboxes

Local implementation added:

- Added display labels for connected Gmail inboxes.
- Added per-inbox import-rule routing direction metadata.
- Added Google Groups/shared mailbox source metadata for connected Gmail inboxes, including source type, required shared/group address guardrails, notes, audit coverage, and Gmail settings UI controls.
- Added owner/admin APIs to update inbox labels and import-rule routing settings.
- Extended ticket list responses and filters with source Gmail connection metadata.
- Updated the Gmail settings UI for multiple inboxes, per-inbox sync/watch status, per-inbox import controls, and import-rule editing.
- Updated the ticket queue UI to show and filter by source inbox and source type, including saved-view preservation. Backend saved-view sanitization now preserves `gmail_connection_id`, `gmail_inbox_type`, and `sla_status` filters.
- Added M11 backend coverage for multiple inbox labels, import-rule routing updates, role restrictions, ticket source labels, shared-source guardrails, inbox filtering, and saved-view inbox-filter preservation.

Staging rollout status:

- Applied the `0015_multiple_gmail_inboxes` migration to staging Supabase.
- Deployed the M11 backend to Cloud Run staging.
- Deployed the M11 frontend to a Vercel preview.
- Staging verification confirms two active Gmail inboxes in one organization, active sync/watch status for both inboxes, future watch expirations, ticket source records for both inboxes, import rules for both inboxes, Cloud Run health/status, and the Vercel ticket route. Saved-view inbox-filter preservation is deployed and covered by backend tests; a signed-in browser smoke for creating a saved view from the UI remains optional.
- Attachment metadata and secure private file storage are deployed. Direct send now has a guarded deployed foundation with global/workspace kill switches and test mode; live direct send, additional support channels, and paid billing remain deferred until Gmail product workflows are stable and explicitly approved.

## Current Production Milestone: M11 Product Expansion - Multiple Gmail Inboxes

### Goal

Owners and admins should be able to run one workspace with multiple Gmail inboxes while agents can see and filter the source inbox for each ticket.

### M7 Follow-Up Items

- Google Cloud Error Reporting is enabled for staging and verified with controlled group `CJzzx9Gtis-cSg` from `operations.error_reporting_test`.
- Gemini paid quota expansion is intentionally deferred. Backend quota handling classifies Gemini quota failures as `quota_exceeded`, records provider-aware retry timing, acknowledges task delivery to avoid Pub/Sub retry noise, and now adds a free-only daily app cap before calling Gemini.
- Vercel production alias rollback proof is complete: production was temporarily rolled back to `dpl_2DGbXGEcaeqk1MprVt8petkZBRuJ`, verified, and restored to `dpl_2pdPBd87Hd8bzu91YdNTkTkEKb9p`. Staging Secret Manager migration, backup/restore, Cloud Run rollback, Vercel rollback, Scheduler/Pub/Sub, and Error Reporting recheck details are logged in `docs/STAGING_DRILL_LOG.md`. Staging Gemini, Google OAuth, Supabase backend secret, Supabase database/pooler password, and encryption-key rotations are complete.

### M9 Staging Status

- M9 backend/frontend changes were deployed to Cloud Run and Vercel staging.
- The `0014_knowledge_routing_sla` migration was applied to staging Supabase.
- Authenticated staging smoke verification passed for knowledge, routing, ticket assignment, approval status, and SLA filtering.

### M10 Backend Work

- Added owner/admin support performance, AI quality, and Gmail sync analytics at `GET /v1/orgs/{organization_id}/metrics/admin`.
- Kept the existing overview metrics endpoint intact for dashboard summary usage.
- Extended audit-log listing with action, resource type, actor, search, limit, and offset filters while preserving metadata redaction and owner/admin-only access.
- Added M10 backend test coverage for analytics calculations, role restrictions, and filtered/redacted audit logs.

### M10 Frontend Work

- Added `/dashboard/analytics` for support, AI quality, Gmail sync, SLA, and workload analytics.
- Added `/dashboard/settings/audit` for audit-log filtering, metadata inspection, and CSV export.
- Linked analytics from the owner/admin dashboard navigation and audit logs from settings navigation.
- Frontend typecheck and production build pass locally.

### M10 Staging Verification

- M10 has been deployed to Cloud Run/Vercel staging and verified with Cloud Run health/readiness checks, authenticated admin analytics smoke testing, audit-log filter checks, Vercel page checks, and bundle verification that the frontend points to Cloud Run.

### M11 Local Verification

- M11 multiple-inbox backend tests and related Gmail/ticket tests pass locally, including saved-view inbox-filter preservation and shared-source guardrails.
- Frontend production build passes locally.
- Alembic/staging Supabase now report `0019_direct_send_controls` as the current migration head.
- Staging database migration, Cloud Run backend deploy, and Vercel deploy are complete for M11 multiple inboxes. Staging now has two active Gmail inbox connections in one organization, active sync/watch for both inboxes, future watch expirations, tickets linked to both source inboxes, active import rules for both inboxes, and Cloud Run/Vercel route verification. Saved-view inbox-filter preservation is deployed and signed-in UI smoke passed. Gmail sync-status UI smoke passed with both inboxes showing health details. Shared-source guardrails and attachment AI opt-in persistence passed signed-in smoke on the stable Vercel app. Cloud Run traffic is on revision `sift-api-staging-00062-cll`, and the stable Vercel alias points to deployment `dpl_APyHgUQ5jpAGgowEbt4NG7Pve1FE`.

### M11 Current Limitations

- Attachment metadata capture has been implemented and deployed through Cloud Run staging revision `sift-api-staging-00014-rgm` with the `0016_ticket_attachment_metadata` migration applied to staging.
- Attachment file storage and signed URL access are implemented behind `ATTACHMENT_STORAGE_BACKEND=gcs`. The `0017_attachment_file_storage` migration is applied to staging, the private bucket exists, object read/write IAM is configured, and Cloud Run env vars are set. Backend signed download-link generation now supports Cloud Run IAM signing and is deployed on revision `sift-api-staging-00023-sbq`; frontend download handling is deployed on Vercel deployment `dpl_2pdPBd87Hd8bzu91YdNTkTkEKb9p`, and a real staging PDF attachment download smoke test returned `200` from Cloud Run and downloaded successfully.
- A basic attachment malware gate now blocks EICAR test-signature content before upload and records infected attachments; this remains deployed in the current Cloud Run staging line and was included before revision `sift-api-staging-00025-4dp`. Workspace owners/admins now have a default-off Settings -> Readiness opt-in for any future AI processing of stored attachment contents; staging Supabase has migration `0021_attachment_ai_optin`, and no current Gemini flow reads attachment files. Full antivirus scanning beyond this pilot gate, live direct send, additional support channels, and paid billing remain deferred; guarded direct-send controls are deployed for P2 validation with global sending disabled. Direct-send test-mode staging smoke passed on 2026-07-14 and verified sent-message, ticket event, audit event, and resolved-ticket behavior without sending real Gmail.
- Gemini quota/backoff handling is deployed, focused backend tests pass, and free-only mode now adds `AI_TRIAGE_DAILY_GEMINI_LIMIT` before provider calls. This reduces retry noise but does not increase Gemini quota. A 2026-07-14 triage-v2 provider smoke attempt was blocked because Gemini reported depleted credits/prepayment, so the real multi-email AI classification smoke remains pending until provider quota/credits are available.
- Gmail settings shared-source editing received a follow-up UI pass that separates saved source display from unsaved edits, lowercases saved shared addresses, keeps validation space stable, and keeps backend guardrails for missing/invalid shared-source addresses. Signed-in smoke now confirms the Google Group/shared mailbox admin workflow behaves correctly in the stable Vercel app.
### M11 Closure Status

- M11 Gmail-first product expansion is ready to move into pilot hardening. Completed staging checks cover multiple connected Gmail inboxes, source filters and saved views, import lock messaging, draft-created visibility, sync/watch guidance, attachment metadata/storage/download, shared-source Gmail settings, and the default-off attachment AI processing opt-in.
- Real multi-email Gemini classification smoke remains blocked by provider credits/quota. The app-side free-only cap and quota failure handling are deployed; paid quota expansion remains deferred.

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
- Cloud Run task routes, Pub/Sub push subscriptions, Cloud Scheduler jobs, and Error Reporting were rechecked after the latest staging deploy; repeat this after each future staging deploy.
- Gmail sync status UI polish is implemented and deployed: the Gmail settings page now shows health guidance, last sync/watch timestamps, last notification, failure count, active import lock state, and recent import errors. Signed-in smoke passed with both connected inboxes showing health.
- Phase 8 implementation is complete in the codebase with a connected dashboard onboarding checklist, Gmail troubleshooting guidance, public pilot documentation pages for support/status/privacy/terms/data processing, and a Settings -> Readiness page for feature flags, lifecycle communication templates, daily free-tier AI usage visibility, downloadable organization export, deletion request intake, and controlled migration checks. Legal review is documented but still pending external approval, and future operator-reviewed hard deletion is documented but intentionally deferred until product/legal approval.
- Next focus: pilot hardening for the Gmail-first workflow. Keep Outlook, chat channels, paid billing, and live direct send deferred unless explicitly approved.
- Pilot hardening started with dashboard operations visibility: owner/admin users can see sync-health posture, degraded inboxes, failed jobs, retryability, next retry timing, and safe retry controls from the main dashboard.
- Settings -> Readiness now includes a pilot launch checklist that summarizes whether the workspace is configured safely for a free Gmail pilot before a real support inbox is connected.
