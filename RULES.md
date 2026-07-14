# Project Rules

These rules apply to every developer, coding agent, pull request, milestone, and production change in this repository.

---

## 1. Before Coding

- Read `RULES.md` before starting a new milestone or major task.
- Read only the documentation relevant to the current task.
- Do not reread every planning document for small fixes, follow-up changes, or work inside an already active milestone.
- Read the current milestone section from `NEXT_FEATURES_IMPLEMENTATION_ROADMAP.md`.
- Use `CURRENT_FEATURES.md` to confirm what is already implemented.
- Read `ARCHITECTURE.md` only when the task changes system structure, data flow, integrations, deployment, database design, or major application boundaries.
- Read `PRODUCTION_READINESS_PLAN.md` only when the task involves production reliability, security, deployment, Gmail synchronization, operations, testing, staging, or release preparation.
- Read `HOMEPAGE_AND_DASHBOARD_PLAN.md` only when changing the public homepage, authenticated dashboard, navigation, visual system, or product experience.
- Read `PROJECT_IDEA.md` only when making a product-scope or target-user decision.
- Read `USE_CASES.md` when changing business behavior, actor permissions, workflows, or acceptance criteria.
- Prefer reading the relevant section of a large document instead of loading the whole file.
- Do not repeatedly summarize documents already reviewed in the current coding session.
- Inspect the existing implementation before creating new files, services, components, models, or abstractions.
- Follow the current monorepo structure and naming conventions.
- Reuse existing utilities, services, schemas, components, and patterns where practical.
- Do not assume a feature is missing until the related code has been searched.
- Do not replace working code only to use a different style or library.
- Keep changes focused on the requested task or milestone.
- Document important assumptions made during implementation.

## 1.1 Documentation Selection Guide

Use the smallest documentation set needed for the task.

### Starting a new production milestone

Read:

- `RULES.md`
- `CURRENT_FEATURES.md`
- The relevant milestone section from `NEXT_FEATURES_IMPLEMENTATION_ROADMAP.md`
- The relevant section from `PRODUCTION_READINESS_PLAN.md`

Read `ARCHITECTURE.md` only when the milestone changes architecture or data flow.

### Continuing work inside an active milestone

Read:

- `RULES.md`
- The current task description
- The affected code and tests

Do not reread the full roadmap or production plan unless the task requirements are unclear.

### Small bug fix

Read:

- `RULES.md`
- The affected code
- The related tests
- Any directly relevant documentation section

Do not load unrelated planning files.

### Database or backend architecture change

Read:

- `RULES.md`
- `ARCHITECTURE.md`
- The relevant milestone section
- The affected models, migrations, schemas, services, and tests

### Gmail synchronization change

Read:

- `RULES.md`
- The Gmail synchronization milestone
- The Gmail-related section of `ARCHITECTURE.md`
- The related backend integration, worker, model, and test files

### Homepage or dashboard change

Read:

- `RULES.md`
- `HOMEPAGE_AND_DASHBOARD_PLAN.md`
- The affected frontend components and API contracts

Do not read the full production roadmap unless the UI change affects production behavior.

### Security or authorization change

Read:

- `RULES.md`
- The relevant security requirements
- The affected authorization services and tests
- `ARCHITECTURE.md` only when security boundaries change

### Documentation-only change

Read:

- The document being changed
- The source code or completed milestone needed to verify accuracy

Do not load every planning document.

---

## 2. Architecture

- Follow the current architecture unless the task explicitly requires an architectural change.
- Keep the Next.js frontend, FastAPI backend, Supabase PostgreSQL database, Redis, Celery workers, Gmail API, and Gemini responsibilities separated.
- Keep business logic in backend services rather than API route handlers.
- Keep API route handlers small and focused on validation, authorization, service calls, and responses.
- Keep external-provider code inside integration or service modules.
- Do not place long-running Gmail or AI operations inside synchronous HTTP requests.
- Use Celery workers for background synchronization, AI triage, Gmail operations, and maintenance jobs.
- Do not introduce a new framework, queue, database, state-management library, or major dependency without a clear requirement.
- Avoid circular dependencies between routes, services, models, schemas, and integrations.
- Prefer simple, explicit implementations over unnecessary abstractions.
- Update `ARCHITECTURE.md` when a change affects system boundaries, deployment shape, data flow, or major services.

---

## 3. Database and Migrations

- Do not change the database schema unless the current task or milestone requires it.
- Every schema change must use an Alembic migration.
- Never edit the production database manually as the normal implementation method.
- Never rely on automatic table creation in production.
- Add indexes for fields used frequently in filtering, joining, synchronization, or deduplication.
- Add unique constraints for resources that must be idempotent.
- Preserve existing data when changing schema.
- Prefer backward-compatible expand-and-contract migrations for breaking changes.
- Test migrations against both an empty database and an existing database.
- Do not remove or rename columns without a migration and rollback plan.
- Keep database models, Pydantic schemas, services, tests, and documentation synchronized.
- Store timestamps in UTC.
- Never store raw Gmail access tokens or refresh tokens in unencrypted fields.

---

## 4. Multi-Tenancy and Authorization

- Every organization-owned resource must be scoped by `organization_id`.
- Never trust an `organization_id` from the frontend without verifying the authenticated user's membership.
- Enforce organization isolation in backend queries and services.
- Frontend filtering is not a security boundary.
- Prevent cross-organization access even when a valid resource ID is supplied.
- Apply role checks consistently for Owner, Admin, and Agent.
- Owner and Admin actions must remain restricted where required.
- Agents must not gain workspace-management, Gmail-connection, or team-administration permissions accidentally.
- Add negative authorization tests for protected changes.
- Member removal or role changes must take effect immediately for future requests.
- Never expose another organization's tickets, customers, settings, Gmail connections, jobs, metrics, or audit logs.

---

## 5. Gmail Integration

- Preserve the manual Gmail sync action as a fallback.
- Automatic Gmail synchronization must use Gmail watch notifications, Google Cloud Pub/Sub, and incremental Gmail history processing.
- Treat Pub/Sub notifications as a signal to synchronize, not as the source of email content.
- Validate Pub/Sub authentication before accepting a notification.
- Acknowledge webhook requests quickly and perform Gmail processing in a worker.
- Do not fetch and process Gmail messages inside the Pub/Sub webhook request.
- Store and update the Gmail `historyId` carefully.
- Never advance the stored history checkpoint until all required pages and messages have been processed successfully.
- Handle Gmail history pagination completely.
- Handle expired or invalid history checkpoints through a bounded reconciliation sync.
- Renew Gmail watches before expiration.
- Keep a scheduled fallback sync because push notifications may be delayed or missed.
- Use a per-connection lock to prevent concurrent synchronization from corrupting state.
- Make Gmail synchronization idempotent.
- Use Gmail message IDs, Pub/Sub message IDs, draft IDs, and other stable identifiers for deduplication.
- Disconnecting Gmail must stop future synchronization and move the integration to a clear disconnected state.
- Revoked Gmail credentials must produce a `reauthorization_required` state instead of an unexplained failure.
- Never log Gmail access tokens, refresh tokens, authorization headers, or full message bodies by default.

---

## 6. AI Triage

- Keep Gemini calls in the backend or worker services.
- Do not expose AI provider secrets to the frontend.
- AI output must be structured and validated with Pydantic.
- Store the provider, model, prompt version, schema version, confidence, and result status when practical.
- Do not allow invalid AI output to crash ticket creation or synchronization.
- Use limited retries for transient provider failures.
- Do not retry permanently invalid output indefinitely.
- Low-confidence or failed AI results must require human review.
- AI triage must not automatically send customer replies.
- Preserve prior triage results when version history is required.
- Do not overwrite manually corrected ticket information without an explicit product rule.
- Keep AI-generated summaries, reasoning, classifications, and replies clearly labeled as AI-generated.
- Do not send unnecessary customer data to the AI provider.
- Never include secrets, internal credentials, or unrelated organization data in prompts.

---

## 7. Human Approval and Gmail Drafts

- Human approval is required before creating a Gmail draft.
- Never implement automatic sending unless a future milestone explicitly requires it and adds stronger safeguards.
- Rejected reply suggestions must never be used to create drafts.
- Editing an approved reply must invalidate the previous approval.
- Approval must refer to the exact reply version being drafted.
- Gmail draft creation must be idempotent.
- Prevent duplicate drafts caused by retries, double-clicks, or repeated requests.
- Preserve the correct Gmail thread when creating a draft.
- Record reply edits, approvals, rejections, and draft creation in ticket events or audit logs.
- Display the real draft status in the UI.
- Do not show a successful draft state until Gmail confirms creation.

---

## 8. Background Jobs

- Long-running or retryable external operations must run through workers.
- Every background job must define:
  - input validation
  - idempotency behavior
  - retryable errors
  - non-retryable errors
  - maximum attempts
  - backoff behavior
  - success state
  - terminal failure state
  - logging and metrics
- Use exponential backoff with jitter for transient failures.
- Do not retry authorization failures or invalid configuration indefinitely.
- Avoid passing secrets or large email bodies directly in queue payloads.
- Pass stable resource IDs and load required data inside the worker.
- Use separate queues when Gmail sync, AI triage, drafts, or maintenance require different concurrency or rate limits.
- Do not run more than one scheduler for the same recurring jobs.
- Failed jobs must be visible and safely retryable.
- Worker restarts must not silently lose acknowledged work.

---

## 9. Backend API

- Validate all request input with Pydantic.
- Return safe and consistent error responses.
- Do not expose stack traces, SQL errors, tokens, or internal provider responses to users.
- Use appropriate HTTP status codes.
- Keep response models explicit.
- Do not return database models directly when sensitive fields may be present.
- Use server-side pagination for growing lists.
- Use stable sorting for paginated results.
- Validate allowed state transitions in the backend.
- Write audit logs for important workspace, role, Gmail, approval, and operational actions.
- Add rate limits to expensive or abuse-prone endpoints.
- Keep health and readiness endpoints lightweight.
- Do not make liveness depend on optional external providers.

---

## 10. Frontend and UI

- Keep the UI clean, minimal, premium, and SaaS-style.
- Use clear hierarchy, consistent spacing, and readable typography.
- Keep urgency colors consistent:
  - Critical: rose
  - High: amber
  - Medium: blue
  - Low: slate
  - Primary or resolved action: teal
- Do not reuse urgency colors as random decoration.
- Use existing design-system components before creating duplicates.
- Keep components focused and reusable.
- Do not place all product content on one dashboard page.
- Each page must have a clear purpose and primary action.
- Avoid hard-coded mock data in production views.
- Do not show fake statistics, testimonials, customer logos, or compliance claims.
- Show real loading, empty, success, permission, disconnected, stale, and error states.
- Sync failures must be visible without opening developer tools.
- Destructive actions require confirmation.
- Important actions must provide immediate feedback.
- Do not rely on color alone to communicate priority or status.
- Ensure keyboard navigation and visible focus states.
- Support common mobile, tablet, and desktop widths.
- Avoid unnecessary animations, large gradients, and visual clutter.
- Keep the marketing homepage consistent with actual product behavior.
- Do not advertise a feature that is not implemented or committed to the active milestone.

---

## 11. Testing

- Add or update tests for every backend behavior change.
- Add frontend tests for important interactions and state handling.
- Add unit tests for business rules, validators, parsers, and state transitions.
- Add integration tests for database, API, Gmail-sync, worker, and authorization behavior.
- Add end-to-end tests for critical user journeys.
- Add regression tests for every fixed production bug when practical.
- Test success, failure, retry, permission, and duplicate-event cases.
- Test cross-organization access attempts.
- Test duplicate Pub/Sub notifications and Gmail messages.
- Test concurrent synchronization for the same Gmail connection.
- Test expired Gmail history recovery.
- Test revoked Gmail credentials.
- Test invalid and timed-out AI responses.
- Test duplicate Gmail draft requests.
- Do not remove a failing test only to make CI pass.
- Do not weaken assertions without explaining why.
- All relevant tests, linting, type checks, and production builds must pass before completing a milestone.

---

## 12. Security and Secrets

- Never commit `.env` files, API keys, tokens, credentials, or private certificates.
- Never place server secrets in `NEXT_PUBLIC_*` variables.
- Rotate any secret that may have been exposed.
- Redact tokens and sensitive values from logs and error tracking.
- Use production CORS allowlists.
- Validate OAuth state and expiration.
- Use one-time OAuth state records.
- Use HTTPS for production callbacks and webhooks.
- Add request-size limits where appropriate.
- Apply least-privilege permissions to Google Cloud, Gmail, Supabase, and deployment service accounts.
- Run dependency and secret scanning in CI.
- Disable debug mode in production.
- Do not claim SOC 2, HIPAA, GDPR, end-to-end encryption, or other compliance unless formally verified.
- Treat customer email content as sensitive data.
- Document retention, export, disconnect, and deletion behavior before a real production launch.

---

## 13. Observability and Operations

- Use structured logs.
- Include request IDs and job IDs.
- Include organization, Gmail connection, and ticket identifiers where safe.
- Do not include secrets or full email bodies in normal logs.
- Track API latency and error rates.
- Track worker job duration, failures, retries, and queue depth.
- Track Gmail notification-to-ticket latency.
- Track last successful sync and watch-renewal health.
- Track AI latency, validation failures, and provider errors.
- Add alerts for system-wide and repeated connection failures.
- Every production alert must have an owner and a runbook.
- Add operational visibility before calling a background feature production ready.
- A feature is not complete if failures can only be diagnosed through local debugging.

---

## 14. Documentation

- Update documentation after finishing each milestone.
- Update `CURRENT_FEATURES.md` when behavior becomes available.
- Update `PROJECT_PLAN.md` when a milestone is completed or reprioritized.
- Update `ARCHITECTURE.md` when system design or data flow changes.
- Add setup instructions for every new external service.
- Document all new required environment variables.
- Document migrations and deployment order.
- Document known limitations and recovery procedures.
- Keep API examples and endpoint lists current.
- Remove outdated instructions rather than leaving conflicting documentation.
- Documentation must describe the actual implementation, not the intended future state.

---

## 15. Git and Change Management

- Create a focused branch for each feature, fix, or milestone.
- Keep commits small and descriptive.
- Do not mix unrelated refactors with feature work.
- Do not reformat the entire repository for a small change.
- Do not delete working code without confirming it is unused.
- Preserve backward compatibility unless the milestone explicitly allows a breaking change.
- Use feature flags for risky production behavior.
- Include migration, deployment, and rollback notes in major pull requests.
- Never force-push or rewrite shared history without explicit approval.
- Do not deploy directly from unreviewed local changes.
- Main must remain deployable.

---

## 16. Scope Control

- Build the smallest complete solution that satisfies the current milestone.
- Finish and polish the core workflow before adding unrelated features.
- Prioritize reliability, security, and usability over feature count.
- Do not add omnichannel support before Gmail synchronization is stable.
- Do not add direct automatic sending before the approval workflow is proven.
- Do not add complex billing before real pilot usage is measured.
- Do not create a large knowledge-base or RAG system before basic workspace knowledge is validated.
- Record useful out-of-scope ideas in the roadmap instead of implementing them immediately.
- Avoid premature optimization, but fix known correctness and security risks before launch.

---

## 17. Definition of Done

A task or milestone is complete only when:

- The requested behavior is implemented.
- The architecture and existing patterns are followed.
- Authorization and organization isolation are enforced.
- Database changes include tested migrations.
- External operations are idempotent.
- Retry and terminal failure behavior are defined.
- Loading, empty, success, and error states are implemented.
- Relevant unit, integration, and end-to-end tests pass.
- Logs, metrics, and operational visibility are included where needed.
- Security and secret handling have been reviewed.
- Documentation is updated.
- Staging verification is complete.
- Rollback or feature-disable behavior is understood.
- No unrelated unfinished code, placeholders, or mock data remain.

---

## 18. Rules for Coding Agents

- State which documentation and code areas were reviewed before making major changes.
- Explain the intended files and behavior before a large refactor.
- Do not invent endpoints, database fields, components, or environment variables without adding them consistently across the codebase and documentation.
- Do not report a feature as complete without verifying it.
- Do not claim tests passed unless they were run successfully.
- Clearly report skipped tests, unresolved failures, and remaining risks.
- Do not hide errors with broad exception handling.
- Do not use placeholder implementations in production paths.
- Do not silently change product rules.
- Do not weaken security, tenant isolation, approval requirements, or validation for convenience.
- When requirements conflict, prioritize:
  1. Security and organization isolation
  2. Data integrity and idempotency
  3. Human approval rules
  4. Current milestone requirements
  5. Existing architecture
  6. UI consistency
- Stop and document the risk before making a destructive or irreversible change.
- Use selective context loading. Do not read every documentation file automatically.
- Start with the smallest relevant set of documents and expand only when information is missing.
- Do not repeatedly reread unchanged documentation during the same session.
- For large planning documents, read only the active milestone or relevant section.
- Do not produce a full project summary before every small task.
- For follow-up work, continue from the current milestone context unless the user explicitly changes scope.
- Ask for or locate additional documentation only when the current task cannot be completed safely without it.
- When reporting reviewed context, list only the documents and code areas actually inspected.
