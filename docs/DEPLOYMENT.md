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
2. Create Pub/Sub topics for Gmail import, Gmail history sync, AI triage, and watch renewal tasks.
3. Create Pub/Sub push subscriptions for each task topic.
4. Configure each push subscription with OIDC authentication using the task Pub/Sub invoker service account.
5. Set each push endpoint to the matching Cloud Run route:
   - `/v1/tasks/gmail/import`
   - `/v1/tasks/gmail/history-sync`
   - `/v1/tasks/ai/triage`
   - `/v1/tasks/gmail/watch-renewal`
6. Create Cloud Scheduler jobs for:
   - `/v1/tasks/scheduler/fallback-sync`
   - `/v1/tasks/scheduler/watch-renewals`
7. Configure Scheduler OIDC with the scheduler invoker service account.
8. Update the Gmail Pub/Sub push subscription endpoint to the new Cloud Run webhook URL:
   - `/v1/webhooks/google/gmail`
9. Update Vercel `NEXT_PUBLIC_API_BASE_URL` to the Cloud Run API URL after staging verification.

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
- Restrict `API_CORS_ORIGINS` to the deployed frontend domain.
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