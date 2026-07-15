# Deployment Notes

This project now targets Google Cloud Run for the backend runtime while keeping Vercel for the frontend and Supabase for database/auth.

Render should stay online as a fallback until Cloud Run staging is verified end to end.

## Recommended production layout

- Frontend: Vercel, running `pnpm run build:web` from the monorepo root.
- Backend API: Google Cloud Run service built from `apps/api/Dockerfile`.
- Async tasks: Google Pub/Sub push subscriptions invoking protected Cloud Run task routes under `/v1/tasks/...`.
- Scheduler: Google Cloud Scheduler invoking protected Cloud Run scheduler routes.
- Database: Supabase Postgres using the Session Pooler connection string.
- Auth: Supabase Auth.
- Gmail: Google OAuth app with environment-specific callback URLs.
- Private attachment storage: Google Cloud Storage bucket per environment when enabled.
- Secrets: staging can temporarily use Cloud Run environment variables; production secrets should move to Secret Manager.

Redis and Celery are not part of the staging or production architecture.

## Resource naming

Use the same Google Cloud project for now: `customer-support-triage-501408`.

Keep staging and production separated by resource names and configuration:

- Cloud Run staging API: `support-triage-api-staging`
- Cloud Run production API: `support-triage-api-prod`
- Staging task topics:
  - `support-triage-staging-gmail-import`
  - `support-triage-staging-gmail-history-sync`
  - `support-triage-staging-ai-triage`
  - `support-triage-staging-watch-renewal`
- Production task topics use the same names with `prod` instead of `staging`.
- Gmail notification topic can remain `projects/customer-support-triage-501408/topics/gmail-notifications` until a separate production topic is created.

Preferred region: `asia-southeast1`.

## Backend deployment commands

Install dependencies locally:

```bash
pip install -e .
```

Run migrations before starting a new release:

```bash
alembic upgrade head
```

Run API locally:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Cloud Run runs the same API container. Background work is delivered as authenticated HTTP requests to the task routes; there is no separate worker process.

## Google Cloud setup

Create or confirm these resources for each environment:

1. Build and deploy the backend image to Cloud Run.
2. Create a private Google Cloud Storage bucket if `ATTACHMENT_STORAGE_BACKEND=gcs`.
3. Create Pub/Sub topics for Gmail import, Gmail history sync, AI triage, and watch renewal tasks.
4. Create Pub/Sub push subscriptions for each task topic.
5. Configure each push subscription with OIDC authentication using the task Pub/Sub invoker service account.
6. Set each push endpoint to the matching Cloud Run route:
   - `/v1/tasks/gmail/import`
   - `/v1/tasks/gmail/history-sync`
   - `/v1/tasks/ai/triage`
   - `/v1/tasks/gmail/watch-renewal`
7. Create Cloud Scheduler jobs for:
   - `/v1/tasks/scheduler/fallback-sync`
   - `/v1/tasks/scheduler/watch-renewals`
8. Configure Scheduler OIDC with the scheduler invoker service account.
9. Update the Gmail Pub/Sub push subscription endpoint to the new Cloud Run webhook URL:
   - `/v1/webhooks/google/gmail`
10. Update Vercel `NEXT_PUBLIC_API_BASE_URL` to the Cloud Run API URL after staging verification.

The public Cloud Run service must remain reachable by Vercel, Google OAuth callbacks, and Gmail webhook delivery. Internal task and scheduler routes reject requests without valid Google service-account OIDC tokens.

## CI coverage

GitHub Actions should check:

- backend linting with Ruff
- Alembic migration application against SQLite
- backend tests with Pytest
- frontend linting
- frontend typecheck
- frontend production build
- backend container image build

## Production checklist

Before a real launch:

- Rotate any secrets that were pasted into chat or logs.
- Store `GOOGLE_CLIENT_SECRET`, `GEMINI_API_KEY`, `SUPABASE_SECRET_KEY`, and `ENCRYPTION_KEY` only in deployment secret stores.
- Move production secrets to Secret Manager when production is cut over.
- Use Supabase Postgres for `DATABASE_URL`; do not use SQLite in production.
- Confirm `GOOGLE_REDIRECT_URI` exactly matches the Cloud Run callback URL.
- Set `TASK_QUEUE_BACKEND=pubsub` in staging and production.
- Configure all task topic env vars and OIDC service-account/audience env vars.
- If attachment storage is enabled, set `ATTACHMENT_STORAGE_BACKEND=gcs`, `ATTACHMENT_STORAGE_BUCKET`, and bucket IAM for the Cloud Run runtime service account.
- Restrict `API_CORS_ORIGINS` to the deployed frontend domain. Cloud Run staging also allows generated Vercel preview origins through a staging-only CORS regex so preview deployments can call the staging API.
- Run `alembic upgrade head` before starting the deployed API.
- Keep Render running until Cloud Run staging passes the smoke suite.

## Release control

Use pull requests for changes to `main`, require CI to pass, and tag deployable releases. Date-based tags are acceptable for the current project stage, for example:

```powershell
git tag release-2026-07-10.1
git push origin release-2026-07-10.1
```

A release candidate is ready for staging only after:

- Backend Ruff passes.
- Backend tests pass.
- Alembic upgrade, downgrade, and upgrade validation passes.
- Frontend lint, typecheck, and production build pass.
- Backend and frontend container images build.
- Staging environment variables are confirmed separate from production.
- Pilot allowlist and kill-switch variables are configured intentionally for the release candidate.

## Deployment order

1. Confirm the release tag or commit SHA.
2. Confirm staging or production secret-store values.
3. Build the frontend and backend images from the repository.
4. Run `alembic upgrade head` against the target database.
5. Deploy the Cloud Run API.
6. Create or update Pub/Sub topics and push subscriptions.
7. Create or update Cloud Scheduler jobs.
8. Update Gmail Pub/Sub push subscription to the Cloud Run webhook.
9. Deploy or promote the Vercel frontend with the Cloud Run API URL.
10. Check `/health`, `/health/ready`, and `/v1/status`.
11. Run a smoke test: sign in, load organizations, view Gmail status, list tickets, connect Gmail, receive a message, triage, approve, and create a draft.

## Rollback procedure

Frontend rollback:

1. Promote the previous known-good Vercel deployment.
2. Confirm `NEXT_PUBLIC_API_BASE_URL` still points at the intended API environment.
3. Smoke test login and the app shell.

API rollback:

1. Redeploy the previous known-good Cloud Run backend image or release tag.
2. Confirm the API starts with the current environment settings.
3. Check `/health` and `/v1/status`.
4. Review logs for startup validation failures.
5. If Cloud Run staging is not yet verified, keep or restore traffic to Render temporarily.

Task rollback:

1. Point Pub/Sub push subscriptions back to the previous known-good Cloud Run revision, or pause task subscriptions if needed.
2. Confirm failed `job_runs` and `gmail_sync_events` are retryable or safely replayable.
3. Watch task route logs for retry storms or repeated failures.

Database rollback:

1. Prefer forward fixes for non-destructive migrations.
2. If rollback is required, back up the target database first.
3. Run the specific Alembic downgrade only after confirming data-loss risk.
4. Redeploy API versions compatible with the downgraded schema.

## Backup, rollback, and soak drills

Run these drills in staging before any real pilot inbox is connected. Record completed runs in `docs/STAGING_DRILL_LOG.md`.

Backup/restore drill:

1. Export a staging Supabase backup or provider-managed restore point.
2. Restore it into a temporary staging-restore database, not the active staging database.
3. Point a temporary API environment or local API process at the restored database.
4. Confirm migrations are at the expected head and core records load: organizations, members, Gmail connections, tickets, attachments, approvals, audit logs, and job runs.
5. Delete the temporary restore database after verification and record the backup timestamp, restore target, and result.

Rollback drill:

1. Record the current Cloud Run revision, Vercel deployment, migration head, Pub/Sub subscription targets, and Scheduler jobs.
2. Promote or redeploy the previous known-good backend revision in staging.
3. Promote the previous known-good Vercel deployment or verify the current frontend remains compatible.
4. Confirm `/health`, `/health/ready`, `/v1/status`, login, ticket list, Gmail settings, and attachment download behavior.
5. Restore traffic to the latest known-good revision and record the rollback duration and any manual fixes.

Staging soak:

1. Use at least two connected staging Gmail inboxes.
2. Send test emails to each inbox, including one with an allowed attachment.
3. Confirm Gmail push/history sync creates tickets without duplicate imports.
4. Confirm AI triage either succeeds or records a clean retryable quota failure when Gemini quota is exhausted.
5. Approve a reply, create a Gmail draft, resolve the ticket, and review audit logs.
6. Review Cloud Run, Pub/Sub, Scheduler, Supabase, and Vercel logs for repeated failures or retry storms.
7. Record start/end time, inboxes used, created ticket IDs, draft IDs if available, and unresolved issues.

## M7 Staging Verification

Before pilot use, staging must use separate production-like configuration for Supabase/Postgres, Cloud Run API/task routes, Cloud Scheduler, Google OAuth redirect, Pub/Sub topic/subscription, Gmail test inbox, Gemini, and error tracking.

Required staging verification:

1. Run migrations against staging with `alembic upgrade head`.
2. Deploy Cloud Run with `TASK_QUEUE_BACKEND=pubsub` and all task topics configured.
3. Confirm `/health/live`, `/health/ready`, and `/v1/status` report expected dependency status.
4. Confirm task endpoints reject requests without valid Google OIDC identity.
5. Connect a test Gmail inbox, receive a test message, verify ticket creation, automatic triage, edit/approve, Gmail draft creation, resolve, audit log, disconnect, reconnect, and missed-notification fallback.
6. Verify global kill switches for sync, automatic triage, and draft creation in staging.
7. Confirm backup/restore and rollback procedures before connecting a real pilot inbox.

The local mocked M7 release smoke test does not replace this deployed staging verification.

## Gmail Push Deployment Setup

Before validating staging:

1. Confirm the backend API is deployed on Cloud Run.
2. Confirm the Pub/Sub push endpoint is configured as `https://<cloud-run-api-url>/v1/webhooks/google/gmail`.
3. Configure the push subscription to use OIDC authentication with `pub-sub-push-invoker@customer-support-triage-501408.iam.gserviceaccount.com` or the environment-specific Gmail webhook invoker.
4. Set the push audience to the full webhook URL.
5. Confirm the Gmail publisher service account has `Pub/Sub Publisher` on `projects/customer-support-triage-501408/topics/gmail-notifications`.
6. Connect or reconnect Gmail; the OAuth callback should register a Gmail watch and store the returned `historyId` and expiration.

A successful push notification should receive a fast `200` response and create a `gmail_sync_events` record for known active connections, then dispatch history processing through the internal Pub/Sub task topic.

## Pilot operations runbook

Use docs/PILOT_RUNBOOK.md for Gmail-first pilot daily monitoring, degraded Gmail handling, AI triage failure handling, draft-only policy, rollback quick reference, known deferred items, and pilot completion review notes.

