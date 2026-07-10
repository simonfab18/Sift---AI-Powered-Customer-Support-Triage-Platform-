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
- Revoked Gmail refresh tokens move the connection into a recoverable `reauthorization_required` state.
- Audit logs and structured logs redact token, secret, password, and authorization values.
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

- Gemini requests can hit free-tier quota during staging tests; failed triage attempts are visible and retryable.
- Error tracking is not configured because no DSN/provider has been supplied.
- The frontend Gmail success banner needs a Vercel redeploy to match the deployed backend redirect behavior.


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

Current limitations:

- M9 has been verified locally with backend tests, frontend typecheck, frontend production build, and a local migration run, but has not yet been deployed or verified in staging.
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




