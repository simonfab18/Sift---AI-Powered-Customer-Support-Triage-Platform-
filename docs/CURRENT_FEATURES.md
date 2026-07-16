# Current Features

This file reflects the latest local MVP state.

## Authentication

- Supabase Auth is used for user sign-up and sign-in.
- The frontend keeps the Supabase session.
- Backend requests are authenticated with bearer tokens.
- The backend resolves the current user through `/v1/me`.

## Organizations and Multi-Tenancy

- Users can create organizations.
- Users can belong to organizations as members.
- Core resources are scoped by `organization_id`.
- The app stores the selected organization on the frontend.
- Organization-specific resources include tickets, Gmail connections, imports, AI triage results, reply suggestions, Gmail drafts, audit logs, team members, and workspace settings.

## Roles

The system supports three roles:

- Owner
- Admin
- Agent

Owner/admin capabilities include workspace management, Gmail connection, and team administration. Agents focus on inbox, approvals, and ticket handling.

## Gmail Integration

- Owner/admin users can connect Gmail through OAuth 2.0.
- OAuth state is validated.
- Gmail refresh tokens are encrypted before storage.
- Gmail connection status can be viewed in the app.
- Gmail can be disconnected.
- Gmail import rules can be viewed and updated.
- Gmail watches can be registered after OAuth connection.
- Gmail watch renewal has a backend service and request-based Cloud Run task entrypoint.
- Gmail connection responses include watch and sync status fields.
- Authenticated Google Pub/Sub push notifications can be accepted at `/v1/webhooks/google/gmail` and queued to Google Pub/Sub-backed Cloud Run task handlers for Gmail history sync.
- Gmail history sync processes `messagesAdded` changes from stored checkpoints.
- Duplicate Gmail message IDs are skipped during live and manual import.
- Expired Gmail history checkpoints trigger bounded reconciliation and watch re-registration.
- Stale active connections can be discovered for fallback sync.
- Owner/admin users can view sync status and queue a manual history sync.

## Gmail Import

- Connected Gmail accounts can be manually imported.
- Imported Gmail messages are saved as tickets.
- Duplicate Gmail messages are skipped.
- Recent import jobs are shown in the UI.
- Import results include success, imported count, skipped count, and errors.

Current limitation:

- Live sync now queues Gmail history processing on the backend; UI polish for full sync health visibility remains part of a later operations/product pass.

## Tickets

- Tickets are created from imported Gmail messages.
- Tickets include subject, sender/customer, message text, Gmail message ID, Gmail thread ID, received time, status, category, priority, sentiment, and assigned user.
- Ticket statuses include:
  - new
  - open
  - pending
  - draft_created
  - resolved
  - spam
- Ticket priorities include:
  - critical
  - high
  - medium
  - low
- Tickets can be listed with pagination, searched, filtered, assigned, marked as spam, and resolved.
- Ticket status changes are validated through a centralized lifecycle helper.
- Ticket detail shows the original email, AI result, reply suggestion, and lifecycle actions.

## AI Triage

- Gemini is used to classify support tickets.
- AI output is structured and validated.
- Triage result fields include:
  - category
  - priority
  - sentiment
  - summary
  - suggested action
  - draft reply
  - confidence score
  - reasoning
  - human review requirement
- Running triage updates the ticket classification fields.
- New tickets can automatically queue AI triage jobs after ticket creation or Gmail import.
- Ticket responses expose triage queued, running, completed, and failed states.
- Failed triage can be retried through the backend.
- AI triage results store prompt/schema version and latency metadata.
- AI triage creates a reply suggestion for agent review.

## Reply Suggestions and Human Approval

- AI-generated replies are visible to agents.
- Agents can edit suggestions.
- Editing an approved reply invalidates approval and requires reapproval before draft creation.
- Reply suggestions and approvals track reply versions.
- Agents can approve suggestions.
- Agents can reject suggestions.
- Approved suggestions record the approving user and approval time.
- Rejected suggestions cannot be used for Gmail draft creation.
- Ticket events are written for important reply actions.

## Gmail Draft Creation

- Gmail drafts are created only from approved reply suggestions.
- Drafts are created in the related Gmail thread when possible.
- Gmail draft IDs are stored.
- Duplicate draft creation is idempotent and returns the existing draft.
- Ticket status becomes `draft_created` after draft creation.
- The UI shows draft creation state/result.

## Dashboard and App UI

The app includes these main screens:

- Landing page
- Login page
- Overview dashboard
- Inbox
- Approvals
- Customers
- Analytics
- Gmail integrations/import
- Workspace settings
- Team and roles
- Settings

The public landing page remains at `/`, while authenticated product flows now use the `/dashboard` app surface. Legacy `/app/...` URLs redirect into the matching dashboard pages for compatibility.
Phase 8 GA-preparation implementation is complete in the codebase. The dashboard now includes a connected onboarding checklist that reads real workspace state for workspace selection, workspace defaults, Gmail connection health, imports, draft review, and team invitation. The Gmail settings page includes recovery guidance for degraded or reconnect-needed inboxes. Public pilot documentation pages now exist for support, status, privacy, terms, and data processing; these are product-readiness pages and still require legal review before a public commercial launch. Settings now include a Readiness page for workspace feature flags, pilot support contact, lifecycle communication templates, daily free-tier AI usage, downloadable organization export, deletion request intake, and controlled migration checks.

The UI uses a modern SaaS layout with:

- Sidebar navigation
- Top page context/actions
- Urgency-based ticket visuals
- Minimalist spacing
- Responsive page structure

## Metrics

The backend exposes organization metrics through:

- `GET /v1/orgs/{organization_id}/metrics/overview`

Metrics are used by the overview and analytics UI.

## Audit Logs

- Important organization actions can be written to audit logs.
- Audit logs include actor, action, resource type, resource ID, IP address, user agent, metadata, and timestamp.
- Audit logs are available through:
  - `GET /v1/orgs/{organization_id}/audit-logs`

## Workspace and Team

- Workspace settings can be viewed and updated.
- Owner/admin users can manage workspace-level release controls from Settings -> Readiness, including Gmail sync, automatic AI triage, Gmail draft creation, approval requirement, pilot support contact, and daily free-tier AI usage visibility.
- Owner/admin users can download a JSON organization export from Settings -> Readiness. Owners can submit a deletion request, which records an audit event and pauses Gmail sync, AI triage, and draft creation without hard-deleting records.
- Team members can be listed.
- Owner/admin users can invite members.
- Owner/admin users can update member roles.
- Owner/admin users can remove members.


## Security and Tenant Hardening

- Owner/admin-only surfaces are protected for workspace settings, Gmail controls, history sync, team management, audit logs, and operations pages.
- Cross-organization resource IDs fail closed.
- Disabled members immediately lose organization access.
- Sensitive actions have route-level rate limits with `429` and `Retry-After` responses.
- API responses include standard security headers and reject oversized request bodies.
- Gmail connections expose token key-version metadata without exposing refresh tokens.
- Gmail token decryption can use a backend-only versioned keyring so existing inboxes keep working during an `ENCRYPTION_KEY` rotation.
- Revoked Gmail refresh tokens move the connection into a recoverable `reauthorization_required` state.
- Audit logs and structured logs redact token, secret, password, and authorization values.
- Error-tracking event redaction is implemented for sensitive token, key, prompt, and email-body fields before provider delivery.
- Data-control procedures are documented in `docs/SECURITY_AND_DATA_CONTROLS.md`.

## M7 Pilot Release Controls

- Workspace settings now include pilot controls for Gmail sync, Gmail draft creation, and a pilot feedback/support contact.
- Staging/production configuration supports an optional pilot organization allowlist.
- Global kill switches can disable Gmail sync, automatic triage queueing, and Gmail draft creation without deleting organization data.
- Gmail sync/import/history queue paths respect the sync switch.
- Automatic triage queueing respects the auto-triage switch and leaves tickets in `not_queued` when disabled.
- Gmail draft creation respects the draft-creation switch while preserving approved suggestions for later recovery.
- A mocked backend release smoke test covers Gmail history sync, ticket creation, triage, approval, draft creation, resolve, audit, disconnect, reconnect, and fallback stale-connection detection.

Staging verification status:

- Cloud Run staging is deployed and serving the API.
- Supabase staging migrations have been applied through the current Alembic head.
- Vercel points at the Cloud Run API.
- Gmail OAuth connect and Gmail sync/import have been verified with a connected Gmail inbox.
- Gmail Pub/Sub notifications and task push subscriptions target Cloud Run with Google OIDC authentication.
- Cloud Scheduler is enabled with fallback sync and watch-renewal jobs.

Current limitations:

- Gemini runs in free-only mode. The backend has an app-wide daily Gemini triage cap (`AI_TRIAGE_DAILY_GEMINI_LIMIT`, default `20`; staging currently uses `100`) plus a per-workspace daily cap (`AI_TRIAGE_DAILY_GEMINI_ORG_LIMIT`, default `20`) so staging/pilot use stops before repeated free-tier overages; quota-limit jobs are marked `quota_exceeded`, get a provider-aware `next_retry_at`, remain visible/retryable, and are acknowledged by the Cloud Run task route to avoid Pub/Sub redelivery loops. Owner/admin users can view today's AI usage and per-inbox counts from Settings -> Readiness, including a clear "AI paused for today" state when the cap is exhausted.
- Google Cloud Error Reporting is enabled and verified for Cloud Run staging with `ERROR_TRACKING_PROVIDER=google-cloud`; unhandled API exceptions and failed request-based task exceptions are captured with redacted request/job context. Controlled event group `CJzzx9Gtis-cSg` verified delivery and reached count `2` after the 2026-07-13 recheck. No external DSN is required for the Google Cloud provider.
- The frontend Gmail success banner and dashboard route consolidation have been redeployed to the Vercel production alias.


## Google Cloud Run Task Architecture


- Staging and production backend execution has moved from Render plus Redis/Celery assumptions to Google Cloud Run plus Google Pub/Sub task push handlers.
- The public API remains reachable for Vercel, Gmail OAuth callbacks, and Gmail webhook delivery. Normal app routes continue to use Supabase JWT authentication and organization/role authorization.
- Internal task routes under `/v1/tasks/...` require Google service-account OIDC tokens with expected issuer, audience, and service-account email validation.
- Gmail import, Gmail history sync, AI triage, Gmail watch renewal, fallback sync, and watch-renewal scheduler behavior reuse existing business services through request-based task runner functions.
- Render can remain available as a temporary fallback, but the verified staging baseline now uses Cloud Run, Pub/Sub, Cloud Scheduler, Vercel, and Supabase.


## M9 Knowledge, Routing, and SLA

- Owner/admin users can manage organization-scoped knowledge sources with title, body, source type, owner, effective dates, active/archive state, and metadata.
- Knowledge retrieval uses only active, effective sources from the same organization; archived sources are not used for new AI generation.
- AI triage prompts can include matched workspace knowledge, and triage results store the source references used.
- Knowledge usage is recorded with ticket, prompt version, matched terms, and score metadata.
- Owner/admin users can manage routing rules with ordered conditions and actions.
- Routing rules can be tested against a sample or existing ticket before activation.
- Active routing rules run when tickets are created manually or imported from Gmail, and executions are recorded.
- Routing actions currently support assignment to active members, priority floor, approval requirement, and record-only tag/notification metadata.
- Workspace settings include business timezone, business hours, first-review target, and resolution target.
- Tickets store SLA due dates and SLA status, and ticket list responses can filter by SLA status.
- The dashboard settings UI includes knowledge source management, routing rule management, and workspace SLA/business-hours settings.
- The ticket queue shows SLA status and supports SLA filtering in saved working views.
- Ticket detail shows SLA due dates, AI knowledge source references, and routing execution history.

Staging status:

- M9 has been deployed to Cloud Run/Vercel staging, the `0014_knowledge_routing_sla` migration has been applied, and the authenticated staging smoke flow verified knowledge, routing, ticket assignment, approval status, and SLA filtering.

## M10 Analytics and Administration

- Owner/admin users can view combined operations analytics through:
  - `GET /v1/orgs/{organization_id}/metrics/admin`
- Support performance analytics include ticket volume, category and priority distribution, first-review time, resolution time, approval wait time, SLA attainment, agent workload, and reopen-rate signals.
- AI quality analytics include triage completion rate, confidence distribution, agent category/priority corrections, reply approval rate, reply change level, rejected suggestion reasons, provider latency, and provider failure rate.
- AI quality analytics avoid presenting AI accuracy because no labeled evaluation set exists yet.
- Gmail sync analytics include Pub/Sub notifications received, incremental sync successes, fallback recoveries, reconciliation count, duplicate skips, sync latency, watch-renewal success, and reauthorization count.
- Audit logs now support action, resource type, actor, search, limit, and offset filters.
- The dashboard includes an owner/admin analytics page at `/dashboard/analytics`.
- The dashboard settings area includes an audit-log administration page at `/dashboard/settings/audit` with filters, metadata inspection, and CSV export.

Staging status:

- M10 has been deployed to Cloud Run/Vercel staging and verified with Cloud Run health/readiness checks, authenticated admin analytics smoke testing, audit-log filter checks, Vercel page checks, and bundle verification that the frontend points to Cloud Run.

Current limitations:

- M10 analytics are computed from existing operational records. Exact edit-distance scoring and labeled AI evaluation are intentionally deferred until the product has a labeled review dataset.

## M11 Product Expansion: Multiple Gmail Inboxes

- Owner/admin users can edit labels for each connected Gmail inbox.
- Owner/admin users can manage each inbox import rule with support label, unread-only behavior, active state, and routing direction.
- Owner/admin users can mark a connected Gmail source as an individual inbox, Google Group, or shared mailbox, including a shared/group address and notes. Google Group/shared mailbox sources require a shared address, and switching back to an individual inbox clears the shared address. This keeps Google Groups/shared-mailbox patterns inside the verified Gmail sync path without adding a new channel provider yet.
- The Gmail settings UI shows multiple connected inboxes with independent sync/watch health, saved-source labels, plain-English health guidance, last successful sync, last sync start, watch expiry, last notification, Gmail history checkpoint, failure count, active import lock state, manual import, manual history queueing, recent import context, and a per-inbox next-step troubleshooting hint.
- The ticket queue shows the source inbox for Gmail-created tickets.
- The ticket queue can filter by source Gmail inbox and Gmail source type, and saved views can preserve those filters; backend sanitization preserves `gmail_connection_id`, `gmail_inbox_type`, and `sla_status` filters.
- Backend audit logs record Gmail connection label updates and import-rule routing updates.
- Gmail watch registration is active for both verified staging inboxes after granting Gmail publisher access to the notification Pub/Sub topic.
- Gmail-imported tickets capture attachment metadata: filename, MIME type, size, Gmail attachment ID, inline flag, policy status, storage status, scan status, and stored timestamp when available.
- Allowed attachments can be explicitly stored from Gmail into a private Google Cloud Storage bucket and opened through short-lived signed URLs after organization/ticket authorization checks.
- Attachment storage and signed URL creation write audit logs. Blocked MIME/size/malware attachments remain visible as metadata but cannot be stored.
- Workspace owners/admins can explicitly opt in to future AI processing of stored attachment contents from Settings -> Readiness. The flag is default-off, staging Supabase has migration `0021_attachment_ai_optin`, signed-in Vercel smoke confirms save/refresh persistence, and current Gemini flows still do not read attachment files.
- Attachment storage includes a basic malware gate that blocks EICAR test-signature content before upload and records `blocked_malware` / `infected`; this backend change remains in the current Cloud Run staging line through revision `sift-api-staging-00025-4dp`. Full antivirus scanning remains a later production hardening item.
- Gemini quota/backoff handling is deployed, and free-only mode now includes an app-side daily cap (`AI_TRIAGE_DAILY_GEMINI_LIMIT`, default `20`; staging currently uses `100`) so the system defers extra triage work instead of repeatedly calling Gemini after the free allowance is reached. A repeatable direct Gemini smoke runner exists at `apps/api/scripts/gemini_triage_smoke.py`; after updating staging to Secret Manager Gemini key version `4` and `GEMINI_MODEL=gemini-3.1-flash-lite`, the 2026-07-15 pilot-hardening classification checkpoint passed 4/4 synthetic pilot classifications.
- Current product focus is now pilot hardening for the verified Gmail-first workflow. Outlook, chat channels, paid billing, and live direct send remain deferred unless explicitly approved.
- The dashboard now includes a pilot operations panel for owner/admin users that surfaces Gmail sync-health posture, degraded inboxes, recent failed import/AI jobs, retryability, next retry timing, safe retry actions, and manual dismissal for understood failed jobs using the existing operations endpoints. The 2026-07-15 pilot-hardening operations smoke passed focused backend operations/security tests plus Cloud Run and Vercel route checks; an optional signed-in visual check remains useful when degraded or failed-job data exists.
- Settings -> Readiness now includes a pilot launch checklist that summarizes workspace safety posture for Gmail sync, AI triage, approval/draft controls, direct-send posture, pilot contact, attachment AI, and data controls. Pilot support contact is validated as an email in both the frontend and backend before the checklist marks it ready. The same page now includes a manual pilot smoke-test checklist for Gmail health, ticket import, approval-to-draft, attachment download, operations posture, and rollback notes. The 2026-07-15 pilot readiness final checklist review and signed-in pilot owner/admin visual confirmation are complete for technical staging readiness; external legal review remains required before public/commercial launch. `docs/PILOT_RUNBOOK.md` now captures the Gmail-first pilot operating checklist, daily monitoring, rollback notes, and known deferred items.

Local verification status:

- M11 backend tests, related Gmail/ticket tests, saved-view inbox-filter tests, attachment metadata/storage tests, workspace attachment AI opt-in tests, frontend production build, Ruff, and Alembic head inspection pass locally.

Current limitations:

- The `0015_multiple_gmail_inboxes` migration has been applied to staging Supabase.
- M11 multiple-inbox backend and frontend are deployed to staging/production-facing services, and the stable Vercel app now uses the `/dashboard` app surface. Staging verification confirms two active Gmail inboxes in one organization, active sync/watch state for both, future watch expirations, tickets linked to both source inboxes, active import rules for both, Cloud Run/Vercel route health, signed-in saved-view inbox-filter preservation, signed-in Gmail sync-status health cards for both inboxes, shared-source guardrails for Google Group/shared mailbox address handling, and signed-in attachment AI opt-in persistence.
- The `0016_ticket_attachment_metadata` migration has been applied to staging Supabase, and the attachment metadata backend changes are deployed to Cloud Run staging revision sift-api-staging-00014-rgm.
- The `0017_attachment_file_storage` migration is applied to staging, the private staging GCS bucket exists, object read/write IAM is configured, and Cloud Run attachment storage env vars are set. Attachment storage and signed download-link generation are deployed to Cloud Run staging revision `sift-api-staging-00023-sbq`; the runtime service account has `roles/iam.serviceAccountTokenCreator`, health checks pass, the frontend download action is deployed on Vercel deployment `dpl_2pdPBd87Hd8bzu91YdNTkTkEKb9p`, and a real staging PDF attachment download smoke test returned `200` from Cloud Run and downloaded successfully.
- Full antivirus scanning beyond the current basic malware gate, direct send, additional channels, and paid Gemini billing/quota expansion remain intentionally deferred before a real production pilot; the current product direction is free-only Gemini use with an app-side daily cap. Staging Gemini, Google OAuth, Supabase backend secret, Supabase database/pooler password, and encryption-key rotations are complete. Existing Gmail token version `1` remains readable through `ENCRYPTION_KEYRING`, while new tokens use version `2`. Sync/import/watch and approval-to-draft staging soak passed on 2026-07-13. Backup/restore, Cloud Run rollback, Vercel rollback, staging Secret Manager migration, Scheduler/Pub/Sub recheck, and Error Reporting recheck passed on 2026-07-13 and are logged in `docs/STAGING_DRILL_LOG.md`.

## M8 Agent Productivity Features

- Agents can save organization-scoped ticket views with user-scoped filters.
- Saved view filters are sanitized so deleted, unsupported, or changed filters fail gracefully instead of breaking queue loading.
- Ticket bulk actions support assign, status change, mark spam, resolve, and safe triage retry with per-ticket success or failure results.
- Destructive bulk actions require explicit confirmation and write audit entries for successful items.
- Workspace response templates support category tags, search, version metadata, owner/admin editing, and insertion into normal editable reply suggestions.
- Template insertion does not approve a reply or bypass the existing approval and Gmail draft workflow.
- Internal notes are stored separately from customer-visible reply suggestions, include edit history, support active-member email mentions, and write ticket/audit events.
- Collaboration locks can warn/block concurrent reply edits so one agent cannot silently overwrite another active editor.
- The ticket queue UI supports saved views, multi-select, and bulk action flows for status updates, assignment, spam marking, resolving, and safe triage retry.
- The ticket detail UI supports response template search/insertion, internal notes, note edit history, tracked mentions, and visible reply edit-lock warnings.

Current limitation:

- Real multi-agent lock behavior and end-to-end saved-view/bulk-action workflows still need staging verification with deployed credentials and representative users.
## Local Development

Current local links:

- Frontend: `http://localhost:3002`
- Backend health: `http://localhost:8001/health`

Current local mode uses manual server processes. Staging/production async work now targets Google Pub/Sub and request-based Cloud Run task handlers instead of Redis/Celery workers.

- Legal-review readiness is tracked in `docs/LEGAL_REVIEW_CHECKLIST.md`; external legal approval is still required before public commercial launch. Future hard deletion is documented in `docs/HARD_DELETION_POLICY.md` and remains an operator-reviewed future implementation, not an automatic self-serve delete today.

## P2 Direct Send Controls

- Direct Gmail send controls are implemented and deployed in guarded test-mode posture for approved reply suggestions. Ticket detail also surfaces approved-reply readiness, draft-created state, Gmail draft id when available, and the exact direct-send confirmation snapshot.
- Direct send is disabled by default globally and per workspace. It requires `DIRECT_SEND_ENABLED=true`, workspace `direct_send_enabled=true`, and an explicit final confirmation from the ticket UI.
- The send request must confirm the exact approved reply version, recipient email, subject, body, and `SEND` confirmation text before the backend records or sends anything. The ticket UI now shows this exact send snapshot before the final confirmation input is enabled.
- `DIRECT_SEND_TEST_MODE=true` records a test sent-message event without calling Gmail. Cloud Run staging is deployed with `DIRECT_SEND_ENABLED=false` and `DIRECT_SEND_TEST_MODE=true`; real Gmail sends remain off until explicit product approval.
- Sent replies create `gmail_sent_messages` records, write `ticket.reply_sent` timeline events, write `gmail.message.sent` audit logs, and resolve the ticket.
- Staging test-mode smoke passed on 2026-07-14 with a resolved smoke ticket, `test-send-*` message record, ticket timeline event, audit metadata, and audit `resource_id` verification. The staging global direct-send switch was restored to `DIRECT_SEND_ENABLED=false` afterward.
