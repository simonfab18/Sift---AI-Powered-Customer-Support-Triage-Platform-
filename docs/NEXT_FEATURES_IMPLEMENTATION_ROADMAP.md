# Next Features and Implementation Milestones

**Product:** AI Customer Support Triage and Response System  
**Working product name:** Sift  
**Generated:** 2026-07-08  
**Purpose:** Prioritized implementation backlog after the current MVP.

---

## 1. Prioritization Model

### P0 — Production blocker

Required before connecting a real pilot support inbox.

### P1 — Pilot quality

Strongly improves daily usability, control, and product value.

### P2 — Product expansion

Build after the core workflow is stable and pilot data validates the need.

### P3 — Later or optional

Useful ideas that should not distract from the initial product.

---

## 2. Recommended Delivery Sequence

| Milestone | Priority | Outcome |
|---|---:|---|
| M0. Release baseline | P0 | Completed - controlled environments, migrations, and CI |
| M1. Live Gmail sync foundation | P0 | Completed - authenticated Gmail push events reach the application |
| M2. Incremental sync and recovery | P0 | Completed locally - reliable, duplicate-safe ticket ingestion |
| M3. Automatic triage pipeline | P0 | Completed locally - new tickets are triaged without manual action |
| M4. Core workflow polish | P0 | Completed locally - ticket, approval, and draft lifecycle is consistent |
| M5. Operations and observability | P0 | Completed locally - failures are visible, retryable, and traceable |
| M6. Security and tenant hardening | P0 | Completed locally - backend boundaries, rate limits, and token lifecycle are hardened |
| M7. Staging and pilot release | P0 | Next - full workflow is proven in a production-like environment |
| M8. Agent productivity | P1 | Faster daily queue handling |
| M9. Knowledge and routing | P1 | More accurate replies and smarter ownership |
| M10. Analytics and administration | P1 | Teams can measure and manage operations |
| M11. Product expansion | P2 | Broader channels and commercial readiness |

---

# M0 — Release Baseline

## Features

### Environment separation

- Development
- Staging
- Production

### Database migrations

- Alembic setup
- Migration CI test
- Production migration command
- Rollback documentation

### CI/CD

Backend:

- Ruff or equivalent linting
- Type checks where configured
- Unit tests
- Migration test
- Container build

Frontend:

- ESLint
- TypeScript check
- Unit or component tests
- Next.js production build

### Release controls

- Protected main branch
- Pull-request checks
- Release tags
- Feature flags
- Rollback procedure

## Requirements

- Environment values are validated on startup.
- Staging never shares Gmail topic, subscription, credentials, database, or Redis with production.
- Secrets are not committed.
- Production deploys do not depend on a developer's local machine.

## Acceptance criteria

- A clean staging deployment can be created from the repository.
- A failed release can be rolled back.
- A schema migration is automatically validated before merge.

---

# M1 — Live Gmail Sync Foundation

Status: Completed locally in branch `codex/m1-live-gmail-sync-foundation` at commit `cce5a74`.

## Feature 1: Pub/Sub topic and subscription

### Requirements

- Gmail-specific topic
- Authenticated push subscription
- Separate staging and production resources
- Service account with least privilege
- Expected audience configured
- Dead-letter or retry policy considered at Pub/Sub level

### Acceptance criteria

- A valid Pub/Sub test message reaches staging.
- An unauthenticated request is rejected.
- A message from an unexpected audience or service account is rejected.

## Feature 2: Gmail watch registration

### Requirements

- Register after initial Gmail connection setup.
- Store `historyId` and expiration.
- Filter to `INBOX` or configured labels where appropriate.
- Record audit and sync events.
- Do not mark live sync active before successful registration.

### Acceptance criteria

- Connecting Gmail creates an active watch.
- Reconnecting replaces stale watch metadata safely.
- Disconnecting stops or invalidates future processing.

## Feature 3: Watch renewal

### Requirements

- Scheduled daily renewal
- Renewal runs only for active connections
- Retry transient failures
- Mark reauthorization when credentials are invalid
- Alert before a watch expires without renewal

### Acceptance criteria

- Watches remain active beyond seven days in a staging soak test.
- A failed renewal is visible to an owner/admin.
- Duplicate renewal execution does not create inconsistent state.

---

# M2 — Incremental Sync and Recovery

Status: Completed locally in branch `codex/m2-incremental-sync-recovery`.


## Feature 4: Pub/Sub webhook

### Requirements

- OIDC JWT validation
- Request-body validation
- Base64URL payload decoding
- Pub/Sub message deduplication
- Gmail account resolution
- Fast job enqueue and acknowledgment
- Sanitized logging

### Acceptance criteria

- Duplicate webhook delivery creates at most one effective sync execution.
- Webhook response remains fast while message processing happens in workers.
- Malformed payloads do not enqueue jobs.

## Feature 5: Gmail history sync worker

### Requirements

- Per-connection lock
- Start from stored checkpoint
- Complete pagination
- Process `messagesAdded`
- Fetch complete messages
- Apply import rules
- Upsert customer and ticket
- Commit checkpoint after successful work
- Record sync event
- Queue triage separately

### Acceptance criteria

- New Gmail messages create tickets.
- Existing Gmail message IDs are skipped.
- Multiple pages of history are processed.
- Concurrent notifications do not create duplicate tickets.
- Worker restart does not lose the ability to recover.

## Feature 6: Full reconciliation

### Requirements

- Trigger when history checkpoint is expired or invalid
- Use configurable date or message bounds
- Use existing deduplication keys
- Re-establish checkpoint and watch state
- Expose reconciliation progress

### Acceptance criteria

- A simulated `history.list` 404 recovers automatically.
- Existing tickets are not duplicated.
- Reconciliation failure becomes a visible degraded state.

## Feature 7: Fallback sync

### Requirements

- Scheduled stale-connection scan
- Configurable interval
- Random jitter
- Skip active jobs
- Manual sync remains available

### Acceptance criteria

- A mailbox update imported without a delivered push notification is recovered.
- The scheduler does not create a continuous duplicate-job loop.

## Feature 8: Sync health UI

### Requirements

Display:

- Connected account
- Live/degraded/disconnected state
- Last notification
- Last successful sync
- Watch expiration or renewal health
- Current job state
- Last error
- Sync now
- Reconnect

### Acceptance criteria

- Owners can understand and act on a sync failure without reading server logs.
- Agents see an appropriate limited status without receiving admin-only controls.

---

# M3 — Automatic Triage Pipeline

Status: Completed locally in branch `codex/m3-automatic-triage-pipeline`.


## Feature 9: Auto-triage on ticket creation

### Requirements

- Enqueue after ticket transaction commits.
- One active triage job per ticket and version.
- Explicit queue and state.
- Retries for transient errors.
- Manual retry.
- AI result versions.

### Acceptance criteria

- New tickets automatically receive a triage result.
- Duplicate imports do not create duplicate active triage jobs.
- Failed triage is visible and retryable.

## Feature 10: Prompt and schema versioning

### Requirements

Store:

- Provider
- Model
- Prompt version
- Schema version
- Generated time
- Latency
- Raw validation outcome
- Confidence
- Human-review flag

Do not store unrestricted raw model responses when they may expose unnecessary sensitive content. Store only what is required for debugging and audit.

### Acceptance criteria

- A changed prompt can be compared with prior results.
- Existing results remain readable after a schema update.

## Feature 11: AI fallback behavior

### Requirements

- Invalid output correction attempt
- Limited retries
- Safe fallback category and priority
- Always require human review on uncertain or failed output
- Provider timeout
- Provider rate-limit handling

### Acceptance criteria

- An invalid model response never crashes ticket creation.
- The UI clearly distinguishes completed, low-confidence, and failed triage.

---

# M4 — Core Workflow Polish

Status: Completed locally in branch `codex/m4-core-workflow-polish`.


## Feature 12: Ticket lifecycle state machine

### Requirements

- Define legal transitions.
- Separate support status from processing status.
- Reject invalid transitions in the backend.
- Write ticket events.
- Add transition tests.

### Acceptance criteria

- A resolved ticket cannot accidentally return to draft-created through a stale request.
- Every important state change records actor and time.

## Feature 13: Reply versioning and approval invalidation

### Requirements

- Version every meaningful reply edit.
- Approval refers to an exact version.
- Editing invalidates prior approval.
- Draft creation checks the latest approved version.
- Rejected versions cannot be drafted.

### Acceptance criteria

- A stale approved version cannot be used after an edit.
- Timeline shows who changed and approved the content.

## Feature 14: Draft creation resilience

### Requirements

- Idempotency key
- Store Gmail draft ID
- Retry transient Gmail failures
- Prevent duplicate draft
- Preserve thread association
- Return “Open in Gmail” destination when available
- Handle deleted Gmail thread gracefully

### Acceptance criteria

- Repeated create-draft requests create one Gmail draft.
- A failed request can be retried safely.
- The UI displays the real final state.

## Feature 15: Inbox production behavior

### Requirements

- Server pagination
- Stable sort
- Search
- Multi-filter
- Assignment
- Saved personal default view
- URL-backed filters
- Bulk actions
- Responsive behavior

### Acceptance criteria

- Filters persist through refresh or shareable URL state where appropriate.
- The inbox remains responsive with realistic ticket volume.
- Bulk actions show partial failure results.

## Feature 16: Approvals workspace

### Requirements

- Pending-only default
- Priority and age
- Side-by-side original email and draft
- Edit, approve, reject
- Assignment or reviewer ownership
- Clear next action
- Approval audit history

### Acceptance criteria

- An agent can complete the review without navigating through several unrelated pages.
- Rejected items leave the active queue but remain auditable.

---

# M5 — Operations and Observability

## Feature 17: Job-run model and operations page

### Requirements

- Job type
- Queue
- Organization
- Related resource
- Status
- Attempts
- Timing
- Error classification
- Retry eligibility
- Correlation ID

### Acceptance criteria

- An owner/admin can see recent workspace failures.
- Internal operators can see system-wide failures without exposing other organizations to customers.

### Local implementation status

Completed in M5 backend pass:

- Expanded `job_runs` with queue, attempts, related resource, correlation ID, error class/code, retry eligibility, duration, alert owner, and runbook URL fields.
- Added owner/admin operations endpoints for workspace failures, job detail, safe retry, and Gmail sync health.
- Added a token-protected internal endpoint for system-wide failed jobs.
- Added structured JSON API and worker logs with request/job/resource context and sanitized errors.
- Added `/health/live`, `/health/ready`, and richer `/v1/status` dependency reporting.
- Added error classification for retryable provider, queue, and database failures.
- Added focused tests for operations access, retry behavior, sync health, redaction, and health/status.

Known remaining production follow-up:

- Connect external alert delivery and hosted runbook URLs in staging/production.
- Add a frontend operations page using the new backend endpoints.
- Add worker heartbeat and queue-depth monitoring once the deployed worker/Redis topology is finalized.

## Feature 18: Structured logging

### Requirements

Include:

- Timestamp
- Environment
- Service
- Severity
- Request ID
- Job ID
- Organization ID
- Connection ID
- Ticket ID
- Event name
- Duration
- Sanitized error

Exclude:

- Refresh tokens
- Access tokens
- Authorization headers
- Full email bodies by default
- Full AI prompts by default

### Acceptance criteria

- One ticket's path can be traced across API and worker services.
- Secret scanning of logs finds no known credentials.

## Feature 19: Error tracking and alerts

### Requirements

- API exception capture
- Worker exception capture
- Release version
- Environment
- Sanitized context
- Alert thresholds
- Alert owner
- Runbook link

### Acceptance criteria

- A forced sync failure creates a useful staging alert.
- Repeated identical errors are grouped.

## Feature 20: Health endpoints

Suggested endpoints:

```text
GET /health/live
GET /health/ready
GET /v1/status
```

### Requirements

- Liveness does not depend on every external provider.
- Readiness verifies required local dependencies.
- Detailed status is protected when it exposes internals.
- Worker heartbeat is monitored separately.

### Acceptance criteria

- Deployment platform can stop routing to an unready API.
- Worker outage is detectable even when API is healthy.

---

# M6 — Security and Tenant Hardening

## Feature 21: Authorization test matrix

Test each role against:

- Organization settings
- Gmail connect/disconnect
- Manual sync
- Watch controls
- Tickets
- Assignment
- Triage
- Reply edit
- Approval
- Draft creation
- Team management
- Audit logs
- Operations page

### Acceptance criteria

- Every endpoint has allowed and denied role tests.
- Cross-organization resource IDs return a safe denial.

## Feature 22: Rate limiting

Suggested protected actions:

- OAuth start
- Manual sync
- Triage
- Retry
- Draft creation
- Invitations
- Authentication-adjacent endpoints

### Requirements

- Per-user and per-organization limits where appropriate
- Provider-aware limits
- Clear 429 response
- Retry-after information
- No bypass through alternate endpoints

### Acceptance criteria

- Abuse tests do not overwhelm Gmail, Gemini, or worker queues.

## Feature 23: Secret and token lifecycle

### Requirements

- Rotate exposed secrets
- Version encryption keys
- Key-rotation procedure
- Reauthorization state
- Secure production secret store
- Redaction middleware
- No secrets in frontend bundles

### Acceptance criteria

- A revoked Gmail token produces a recoverable UI state.
- Secret rotation can be performed without deleting organizations.

## Feature 24: Data controls

### Requirements

- Organization export direction
- Organization deletion
- Gmail disconnect semantics
- Retention configuration
- Backup policy
- Restore test
- Audit retention
- Attachment policy

### Acceptance criteria

- The team can answer what data remains after disconnect and deletion.
- Restore from a recent staging backup succeeds.
### Local implementation status

Completed in M6 backend pass:

- Added negative authorization tests for owner/admin-only surfaces, agent-allowed workflow surfaces, disabled members, and cross-organization resource IDs.
- Tightened audit-log access to owner/admin users.
- Added in-memory rate limits for OAuth start/callback, Gmail sync/watch, triage, retry, draft creation, and member invitations with clear `429` and `Retry-After` responses.
- Added request body-size protection and security headers.
- Added Gmail token key-version metadata and `reauthorization_required` recovery state for revoked refresh tokens.
- Added redaction hardening for logs and operational errors.
- Documented secret rotation, reauthorization, data export/deletion direction, retention, backup, restore, and attachment policy.

Known remaining production follow-up:

- Rotate all real staging/production secrets in the provider dashboards.
- Move rate limiting to Redis if API instances scale horizontally.
- Implement actual organization export/deletion endpoints after legal/product approval.
- Backup/restore validation passed on 2026-07-13; see `docs/STAGING_DRILL_LOG.md`.

---

# M7 — Staging and Pilot Release

## Feature 25: Production-like staging

### Requirements

- Separate Supabase project or isolated staging database
- Separate Google Cloud project resources where practical
- Separate OAuth redirect
- Separate Redis
- API and workers deployed
- Scheduler running
- Error tracking
- Test Gmail inbox

### Acceptance criteria

- The complete Gmail-to-draft flow works without local services.

## Feature 26: E2E release suite

Cover:

- Workspace creation
- Gmail connection
- Initial sync
- Automatic new-message sync
- Triage
- Edit
- Approve
- Draft
- Resolve
- Audit
- Disconnect
- Reconnect
- Missed notification recovery

### Acceptance criteria

- Critical suite passes before every production release.

## Feature 27: Pilot controls

### Requirements

- Feature flags
- Allowlisted organizations
- Admin disable switch for sync
- Kill switch for auto-triage
- Kill switch for draft creation
- Pilot feedback collection
- Support contact

### Acceptance criteria

- Risky automation can be disabled without redeploying or deleting data.

---

# M8 — Agent Productivity Features

## Feature 28: Saved views

Examples:

- My open tickets
- Unassigned
- Critical and high
- Awaiting approval
- Waiting on customer
- Failed triage

### Acceptance criteria

- Views are scoped to the user and organization.
- A deleted or changed filter fails gracefully.

## Feature 29: Bulk actions

- Assign
- Change status
- Mark spam
- Resolve
- Re-run triage where safe

### Acceptance criteria

- Each item returns success or failure.
- Destructive actions require confirmation.
- Audit events are written.

## Feature 30: Response templates

### Requirements

- Workspace-owned templates
- Category tags
- Search
- Insert into suggestion
- Role permissions
- Version or updated metadata

### Acceptance criteria

- Inserting a template does not bypass approval.
- Agents can edit inserted content.

## Feature 31: Internal notes and mentions

### Requirements

- Separate from customer-visible reply
- Mention notifications
- Edit history
- Permissions
- Audit behavior

### Acceptance criteria

- Internal notes can never be inserted into Gmail drafts accidentally.

## Feature 32: Agent collision protection

### Requirements

- Show who is viewing or editing
- Soft lock or edit warning
- Version conflict detection
- Safe merge or reload flow

### Acceptance criteria

- One agent cannot silently overwrite another agent's reply edit.

---

# M9 — Knowledge and Routing

## Feature 33: Workspace knowledge base

Initial scope:

- Text snippets
- Policies
- FAQs
- Product facts
- Escalation instructions
- Effective dates
- Owner and status

Avoid starting with complex document ingestion.

### Acceptance criteria

- Owners/admins manage knowledge.
- Agents can see which sources influenced a reply.
- Archived knowledge is not used for new generation.

## Feature 34: Knowledge-grounded replies

### Requirements

- Retrieve only organization knowledge.
- Include source references internally.
- Respect effective and archived states.
- Fall back safely when no source exists.
- Require human approval.
- Track retrieval and prompt version.

### Acceptance criteria

- Cross-organization knowledge retrieval is impossible.
- The agent can inspect the supporting source.

## Feature 35: Routing rules

Possible conditions:

- Category
- Priority
- Sender domain
- Gmail label
- Keyword
- Sentiment
- Customer
- Business hours

Possible actions:

- Assign agent
- Assign team
- Set priority floor
- Require approval
- Add tag
- Notify owner/admin

### Acceptance criteria

- Rules have priority ordering.
- Rules can be tested before activation.
- Rule execution is recorded.

## Feature 36: SLA timers

### Requirements

- Workspace business hours
- First-review target
- Resolution target
- Pause conditions
- Breach warning
- Timezone handling

### Acceptance criteria

- SLA calculations are reproducible and timezone-safe.
- Breach status appears in inbox filters and dashboard.

---

# M10 — Analytics and Administration

## Feature 37: Support performance analytics

Metrics:

- Ticket volume
- Volume by category and priority
- First-review time
- Resolution time
- Approval wait time
- SLA attainment
- Agent workload
- Reopen rate

## Feature 38: AI quality analytics

Metrics:

- Triage completion rate
- Confidence distribution
- Agent category corrections
- Agent priority corrections
- Reply approval rate
- Average edit distance or change level
- Rejected suggestion reasons
- Provider latency and failure rate

Avoid presenting “AI accuracy” unless there is a well-defined labeled evaluation set.

## Feature 39: Gmail sync analytics

Metrics:

- Notifications received
- Incremental sync success
- Fallback recoveries
- Reconciliation count
- Duplicate skip count
- Sync latency
- Watch-renewal success
- Reauthorization count

## Feature 40: Audit log UI

### Requirements

- Actor
- Action
- Resource
- Timestamp
- Filters
- Search
- Metadata details
- Export for owner/admin

### Acceptance criteria

- Sensitive fields are redacted.
- Agents see only audit data allowed by product policy.

---

# M11 — Product Expansion

## P2 features

### Multiple Gmail inboxes per organization

Requirements:

- Connection-specific rules
- Connection label in inbox
- Independent sync status
- Per-inbox permissions or routing direction

Current status:

- Multiple Gmail inbox support is implemented and deployed to staging/production-facing services.
- Two staging Gmail inboxes have been connected and verified with active watches, active sync state, future watch expirations, ticket import/source records for both inboxes, and active import rules.
- Attachment metadata, private GCS storage, signed download URLs, and a basic malware gate are implemented and staging verified.
- Gemini quota/backoff handling and the free-only app-side daily Gemini guard are deployed; paid quota expansion remains intentionally deferred.
- Vercel production alias rollback/restore proof, sync/import/watch and approval-to-draft soak, backup/restore, and Cloud Run rollback drills passed on 2026-07-13 and are logged in `docs/STAGING_DRILL_LOG.md`.
- Staging credential cleanup is complete for Gemini, Google OAuth, Supabase backend secret, Supabase database/pooler password, and encryption-key rotation.

### Attachments

Requirements:

- Metadata first
- Size and MIME limits
- Malware scanning
- Storage policy
- Signed access URLs
- AI processing opt-in

### Direct send

Only consider after pilot validation.

Requirements:

- Explicit final confirmation
- Exact approved version
- Permission control
- Idempotency
- Sending audit event
- Undo is not guaranteed
- Safe recipient and thread display
- Rate limits
- Test mode

### Additional channels

Potential order:

1. Additional Gmail inboxes
2. Google Groups or shared mailbox patterns
3. Microsoft Outlook
4. Web form
5. Chat channels

Do not build omnichannel architecture before Gmail sync is stable.

### Billing

Possible measured units:

- Connected inboxes
- Monthly tickets
- AI-triaged tickets
- Agent seats

Do not implement complex usage billing before real pilot usage is measured.

---

## 3. Features to Delay

Delay these until the core production workflow is proven:

- Fully autonomous sending
- AI chatbot
- Voice support
- Sentiment-driven automatic refunds
- Large document RAG pipeline
- Custom model training
- Marketplace integrations
- Mobile application
- Highly customizable dashboards
- Enterprise SSO
- Complex billing tiers
- White labeling

These may be valuable later, but they add operational and security risk before the main system is mature.

---

## 4. Suggested Sprint Breakdown

This is a sequencing estimate, not a fixed promise.

### Sprint 1 — Baseline

- Environment validation
- Alembic
- CI upgrades
- Staging deployment skeleton
- Sync schema migration

### Sprint 2 — Push foundation

- Pub/Sub resources
- Authenticated webhook
- Watch registration
- Watch state UI

### Sprint 3 — Incremental sync

- History worker
- Pagination
- Message import
- Idempotency
- Per-connection lock

### Sprint 4 — Recovery

- Daily renewal
- Fallback scheduler
- Expired checkpoint reconciliation
- Retry rules
- Sync event UI

### Sprint 5 — AI pipeline

- Auto-triage
- Job states
- Prompt versions
- Retry and fallback
- Agent retry UI

### Sprint 6 — Workflow polish

- Lifecycle state machine
- Reply versioning
- Approval invalidation
- Draft idempotency
- Inbox pagination and filters

### Sprint 7 — Operations and security

- Job operations
- Structured logs
- Error tracking
- Alerts
- Authorization matrix
- Rate limits
- Secret rotation

### Sprint 8 — Release candidate

- E2E suite
- Failure testing
- Accessibility
- Responsive pass
- Performance test
- Backup and restore
- Pilot documentation

---

## 5. Feature Requirement Template

Use this for each GitHub issue or project card.

```markdown
# Feature name

## Problem

What user or operational problem does this solve?

## User story

As a [role], I want [capability], so that [outcome].

## Scope

- Included behavior
- Included roles
- Included states

## Out of scope

- Explicit exclusions

## Product rules

- Permissions
- State transitions
- Human approval requirements
- Data ownership

## Backend requirements

- Endpoint
- Service logic
- Job behavior
- Retry behavior
- Idempotency
- Audit events

## Database requirements

- Migration
- Tables and fields
- Indexes
- Unique constraints
- Retention

## Frontend requirements

- Page or component
- Loading state
- Empty state
- Success state
- Error state
- Permission state
- Mobile state

## Observability

- Logs
- Metrics
- Alerts
- Correlation IDs

## Security

- Authentication
- Authorization
- Input validation
- Secret handling
- Abuse limits

## Tests

- Unit
- Integration
- End to end
- Failure and concurrency

## Acceptance criteria

- Given / When / Then scenarios

## Rollout

- Feature flag
- Migration order
- Staging verification
- Rollback
```

---

## 6. Global Definition of Done

Every feature must include:

- Product requirement
- Permission model
- API or worker contract
- Database migration when needed
- Idempotency design for external operations
- Retry and failure behavior
- Audit or event behavior
- Complete UI states
- Tests
- Logs and metrics
- Security review
- Staging verification
- Feature flag or rollback direction
- Updated documentation

---

## 7. Immediate Next Actions

Current implementation focus before a real pilot:

1. Complete Vercel production alias rollback proof if required; Cloud Run rollback/restore has already passed.
2. Rotate provider-side credentials before cutover. Staging Cloud Run sensitive values have been moved to Google Secret Manager; replacement provider keys are still pending.
3. Add external error tracking if the pilot acceptance item must be covered.
4. Keep Gemini in free-only mode for pilot usage; defer paid quota expansion until product demand justifies it.

---

## 8. Official Gmail Sync References

- [Configure push notifications in Gmail API](https://developers.google.com/workspace/gmail/api/guides/push)
- [Gmail users.watch](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users/watch)
- [Gmail users.history.list](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.history/list)
- [Authenticate Pub/Sub push subscriptions](https://cloud.google.com/pubsub/docs/authenticate-push-subscriptions)
