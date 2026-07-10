# Google Cloud Run Backend Deployment

This guide covers the new backend architecture:

- FastAPI backend on Google Cloud Run.
- Supabase database/auth unchanged.
- Vercel frontend unchanged.
- Google Pub/Sub task topics instead of Redis/Celery.
- Cloud Scheduler for periodic fallback sync and watch-renewal scans.
- Render remains online as fallback until Cloud Run staging is verified.

## Fixed project choices

```text
GOOGLE_CLOUD_PROJECT_ID=customer-support-triage-501408
GOOGLE_CLOUD_REGION=asia-southeast1
```

Google Cloud SDK local install path provided by the project owner:

```text
C:\Users\stanl\AppData\Local\Google\Cloud SDK
```

## Staging resource names

```text
Cloud Run service: support-triage-api-staging
Task Pub/Sub topics:
  support-triage-staging-gmail-import
  support-triage-staging-gmail-history-sync
  support-triage-staging-ai-triage
  support-triage-staging-watch-renewal
Service accounts:
  support-triage-staging-pubsub-invoker
  support-triage-staging-scheduler-invoker
Cloud Scheduler jobs:
  support-triage-staging-fallback-sync
  support-triage-staging-watch-renewals
```

Production should use the same names with `prod` instead of `staging`.

## Backend environment variables

Set these on the staging Cloud Run service after deployment:

```text
APP_ENV=staging
DEBUG=false
TASK_QUEUE_BACKEND=pubsub
GOOGLE_CLOUD_PROJECT_ID=customer-support-triage-501408
GOOGLE_CLOUD_REGION=asia-southeast1
TASK_PUBSUB_GMAIL_IMPORT_TOPIC=support-triage-staging-gmail-import
TASK_PUBSUB_GMAIL_HISTORY_SYNC_TOPIC=support-triage-staging-gmail-history-sync
TASK_PUBSUB_AI_TRIAGE_TOPIC=support-triage-staging-ai-triage
TASK_PUBSUB_WATCH_RENEWAL_TOPIC=support-triage-staging-watch-renewal
TASK_OIDC_EXPECTED_AUDIENCE=https://<cloud-run-api-url>
TASK_PUBSUB_SERVICE_ACCOUNT_EMAIL=support-triage-staging-pubsub-invoker@customer-support-triage-501408.iam.gserviceaccount.com
SCHEDULER_SERVICE_ACCOUNT_EMAIL=support-triage-staging-scheduler-invoker@customer-support-triage-501408.iam.gserviceaccount.com
PUBSUB_EXPECTED_AUDIENCE=https://<cloud-run-api-url>/v1/webhooks/google/gmail
PUBSUB_SERVICE_ACCOUNT_EMAIL=pub-sub-push-invoker@customer-support-triage-501408.iam.gserviceaccount.com
GOOGLE_REDIRECT_URI=https://<cloud-run-api-url>/v1/gmail/oauth/callback
```

Keep existing Supabase, Gmail OAuth, Gemini, encryption, CORS, pilot, and operations settings aligned with `docs/ENVIRONMENT.md`.

## Task routes

Pub/Sub push subscriptions call:

```text
POST /v1/tasks/gmail/import
POST /v1/tasks/gmail/history-sync
POST /v1/tasks/ai/triage
POST /v1/tasks/gmail/watch-renewal
```

Cloud Scheduler calls:

```text
POST /v1/tasks/scheduler/fallback-sync
POST /v1/tasks/scheduler/watch-renewals
```

All task and scheduler routes validate Google OIDC bearer tokens. Do not use a shared static secret.

## Gmail webhook

The Gmail notification subscription should call:

```text
POST https://<cloud-run-api-url>/v1/webhooks/google/gmail
```

The subscription must use OIDC authentication with the expected service account and audience.

## Cutover order

1. Build and deploy the Cloud Run API.
2. Run `alembic upgrade head` against staging Supabase before routing traffic.
3. Create Pub/Sub task topics and push subscriptions.
4. Create Cloud Scheduler jobs.
5. Update Cloud Run env vars with the final Cloud Run URL/audience values.
6. Update Google OAuth redirect URI to include the Cloud Run callback URL.
7. Update the Gmail Pub/Sub push subscription to the Cloud Run webhook URL.
8. Update Vercel `NEXT_PUBLIC_API_BASE_URL` to the Cloud Run API URL.
9. Run staging smoke verification.
10. Keep Render online until the smoke suite passes.

## Staging smoke verification

Verify:

- `/health`, `/health/ready`, and `/v1/status` return expected status.
- Normal app routes still require Supabase JWT authentication.
- Task routes reject requests without valid Google OIDC identity.
- Gmail OAuth callback succeeds on Cloud Run.
- Gmail watch registration stores `historyId` and expiration.
- Gmail notification creates a sync event and dispatches a history-sync task.
- History sync creates tickets without duplicates.
- Automatic AI triage runs through Pub/Sub task dispatch.
- Reply approval and Gmail draft creation still work.
- Cloud Scheduler fallback sync and watch-renewal routes dispatch due work.
- Pilot kill switches still pause sync, auto-triage, and draft creation.

Do not mark M7 complete until these checks pass against deployed staging credentials.