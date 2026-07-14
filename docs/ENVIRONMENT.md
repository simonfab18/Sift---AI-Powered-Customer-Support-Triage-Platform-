# Environment Configuration

Use the checked-in `.env.example` files as templates only. Real secrets stay in local `.env` files, Cloud Run environment variables, or deployment secret stores.

Staging Cloud Run sensitive values now load from Google Secret Manager. Production secrets should also use Secret Manager before real customer traffic, and provider-side credentials should be rotated before pilot.

## Local files

Create these files before running the app locally:

```powershell
Copy-Item apps/api/.env.example apps/api/.env
Copy-Item apps/web/.env.example apps/web/.env.local
```

Do not commit either generated file. They are already ignored by `.gitignore`.

## Backend variables

`apps/api/.env` controls the FastAPI app, database, Gmail OAuth, Gemini, Supabase Auth verification, and task dispatch.

Required for full local testing:

- `DATABASE_URL`: use Supabase Session Pooler for shared testing, or SQLite for quick local-only tests.
- `ENCRYPTION_KEY`: strong random value used to encrypt newly stored Gmail refresh tokens.
- `ENCRYPTION_KEY_VERSION`: active key version recorded on newly stored Gmail refresh tokens.
- `ENCRYPTION_KEYRING`: optional comma-separated `version:key` list for previous Gmail token encryption keys during rotation.
- `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_JWKS_URL`: Supabase Auth verification settings.
- `SUPABASE_SECRET_KEY`: server-only admin key. Keep this out of frontend env files.
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`: Gmail OAuth settings.
- `GOOGLE_CLOUD_PROJECT_ID`, `GOOGLE_CLOUD_REGION`: Google Cloud deployment settings.
- `GOOGLE_PUBSUB_TOPIC`, `GOOGLE_PUBSUB_SUBSCRIPTION`: Gmail notification topic/subscription settings.
- `PUBSUB_EXPECTED_AUDIENCE`, `PUBSUB_SERVICE_ACCOUNT_EMAIL`: Gmail webhook OIDC validation settings.
- `TASK_QUEUE_BACKEND`: `local` for local tests, `pubsub` for staging and production.
- `TASK_OIDC_EXPECTED_AUDIENCE`: expected Cloud Run audience for internal task and scheduler routes.
- `TASK_PUBSUB_SERVICE_ACCOUNT_EMAIL`: Pub/Sub push invoker service account for task routes.
- `SCHEDULER_SERVICE_ACCOUNT_EMAIL`: Cloud Scheduler invoker service account for scheduler routes.
- `TASK_PUBSUB_GMAIL_IMPORT_TOPIC`: Pub/Sub topic for Gmail import tasks.
- `TASK_PUBSUB_GMAIL_HISTORY_SYNC_TOPIC`: Pub/Sub topic for Gmail history sync tasks.
- `TASK_PUBSUB_AI_TRIAGE_TOPIC`: Pub/Sub topic for AI triage tasks.
- `TASK_PUBSUB_WATCH_RENEWAL_TOPIC`: Pub/Sub topic for Gmail watch-renewal tasks.
- `GEMINI_API_KEY`, `GEMINI_MODEL`: AI triage settings.
- `AI_TRIAGE_DAILY_GEMINI_LIMIT`: free-only app-side cap for Gemini triage calls per UTC day. Defaults to `20`; use `0` only to disable the app-side cap.
- `ATTACHMENT_STORAGE_BACKEND`: `disabled` locally or `gcs` when private attachment storage is enabled.
- `ATTACHMENT_STORAGE_BUCKET`: private Google Cloud Storage bucket used when `ATTACHMENT_STORAGE_BACKEND=gcs`.
- `ATTACHMENT_SIGNED_URL_TTL_SECONDS`: short-lived attachment download URL lifetime, default `300`.
- `ATTACHMENT_SIGNING_SERVICE_ACCOUNT_EMAIL`: optional service account email used for Google Cloud Storage signed attachment URLs. If unset, Cloud Run signs with the runtime service account, which must have `roles/iam.serviceAccountTokenCreator` on itself or the configured signer.
- `ATTACHMENT_MALWARE_SCANNING_BACKEND`: `basic` by default, which blocks EICAR test-signature content before upload. Use `disabled` only when the environment explicitly accepts `not_required` scan status.

Redis and Celery variables are retired for staging and production. Old local `.env` values are ignored during the migration.

Generate a local encryption key with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Frontend variables

`apps/web/.env.local` controls browser-safe frontend settings.

Required:

- `NEXT_PUBLIC_API_BASE_URL`: local default is `http://localhost:8000`; staging/production should point to the Cloud Run API URL.
- `NEXT_PUBLIC_SUPABASE_URL`: public Supabase project URL.
- `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`: public Supabase browser key.

Never add backend-only secrets to the frontend env file.

## Google OAuth redirect URI

For local development, configure this redirect URI in Google Cloud Console:

```text
http://localhost:8000/v1/gmail/oauth/callback
```

For Cloud Run deployment, add the deployed API callback URL as an additional authorized redirect URI:

```text
https://<cloud-run-api-url>/v1/gmail/oauth/callback
```

## Database migrations

New databases should be created through Alembic migrations:

```powershell
cd apps/api
alembic upgrade head
```

The app still supports local SQLite startup for development, but production and shared Supabase databases should use migrations explicitly.

## Environment separation

Use three separate environment profiles:

| Environment | Purpose | Required separation |
|---|---|---|
| Development | Local engineering and tests | Local `.env`, local SQLite only for quick testing, local task dispatcher |
| Staging | Production-like release validation | Separate Supabase project or isolated staging database, staging Cloud Run service, staging task topics/subscriptions, staging Google OAuth redirect, staging scheduler jobs |
| Production | Pilot and customer traffic | Production Supabase database, production Cloud Run service, production task topics/subscriptions, production Google OAuth app/resources, production-only secret store |

For now staging and production can share the same Google Cloud project `customer-support-triage-501408`, but resource names and environment variables must remain clearly separated.

## Startup validation

The API validates production-like settings when `APP_ENV` is `staging` or `production`. Startup fails fast when required values are missing or unsafe values are present.

Required in staging and production:

- `DATABASE_URL`: Supabase/Postgres connection string. SQLite is rejected outside local development.
- `ENCRYPTION_KEY`: production-managed active encryption secret, not `dev-only-change-me`.
- `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY`.
- `SUPABASE_JWKS_URL` or `SUPABASE_JWT_SECRET`.
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`.
- `GOOGLE_CLOUD_PROJECT_ID`, `GOOGLE_CLOUD_REGION`.
- `GOOGLE_PUBSUB_TOPIC`, `GOOGLE_PUBSUB_SUBSCRIPTION`.
- `PUBSUB_EXPECTED_AUDIENCE`, `PUBSUB_SERVICE_ACCOUNT_EMAIL`.
- `TASK_QUEUE_BACKEND=pubsub`.
- `TASK_OIDC_EXPECTED_AUDIENCE`.
- `TASK_PUBSUB_SERVICE_ACCOUNT_EMAIL`.
- `SCHEDULER_SERVICE_ACCOUNT_EMAIL`.
- `TASK_PUBSUB_GMAIL_IMPORT_TOPIC`.
- `TASK_PUBSUB_GMAIL_HISTORY_SYNC_TOPIC`.
- `TASK_PUBSUB_AI_TRIAGE_TOPIC`.
- `TASK_PUBSUB_WATCH_RENEWAL_TOPIC`.
- `GEMINI_API_KEY`, `GEMINI_MODEL`.
- `AI_TRIAGE_DAILY_GEMINI_LIMIT`.
- `FRONTEND_ORIGIN`, `API_CORS_ORIGINS`.
- `SYNC_FALLBACK_INTERVAL_MINUTES`, `WATCH_RENEWAL_SCHEDULE`.
- `RELEASE_VERSION`, `OPERATIONS_ALERT_OWNER`.
- `RATE_LIMIT_SENSITIVE_LIMIT`, `RATE_LIMIT_SENSITIVE_WINDOW_SECONDS`, `MAX_REQUEST_BODY_BYTES`, `ENCRYPTION_KEY_VERSION`.
- `ENCRYPTION_KEYRING` is optional, but when present startup validates its `version:key` format.
- If `ATTACHMENT_STORAGE_BACKEND=gcs`, `ATTACHMENT_STORAGE_BUCKET` must be set and the Cloud Run runtime service account must be able to write objects and sign/read objects as required for signed URLs.

Forbidden in staging and production:

- `DEBUG=true`
- `AUTH_ALLOW_UNVERIFIED_JWT=true`
- `TASK_QUEUE_BACKEND=local`
- `API_CORS_ORIGINS=*`
- SQLite `DATABASE_URL`
- Development encryption keys

## Suggested Google Cloud values

Project:

```text
customer-support-triage-501408
```

Region:

```text
asia-southeast1
```

Staging task topics:

```text
support-triage-staging-gmail-import
support-triage-staging-gmail-history-sync
support-triage-staging-ai-triage
support-triage-staging-watch-renewal
```

Production task topics should use `support-triage-prod-...` names.

Current Gmail notification values:

- `GOOGLE_CLOUD_PROJECT_ID`: `customer-support-triage-501408`
- `GOOGLE_PUBSUB_TOPIC`: `projects/customer-support-triage-501408/topics/gmail-notifications`
- `GOOGLE_PUBSUB_SUBSCRIPTION`: `gmail-notifications-sub`
- `PUBSUB_SERVICE_ACCOUNT_EMAIL`: `pub-sub-push-invoker@customer-support-triage-501408.iam.gserviceaccount.com`

After Cloud Run staging deployment, set:

```text
PUBSUB_EXPECTED_AUDIENCE=https://<cloud-run-api-url>/v1/webhooks/google/gmail
TASK_OIDC_EXPECTED_AUDIENCE=https://<cloud-run-api-url>
```

The Gmail API publisher principal must have `Pub/Sub Publisher` on the Gmail notification topic:

```text
gmail-api-push@system.gserviceaccount.com
```

## Operations settings

- `SERVICE_NAME`: log service label, usually `api`.
- `RELEASE_VERSION`: release identifier emitted in status responses and logs.
- `OPERATIONS_ALERT_OWNER`: owner label included on failed jobs.
- `OPERATIONS_INTERNAL_TOKEN`: optional token for internal system-wide operations endpoints.
- `OPERATIONS_RUNBOOK_BASE_URL`: optional base URL used to populate job runbook links.
- `OPERATIONS_FAILURE_ALERT_THRESHOLD`: repeated-failure threshold for alerting policy.

`ERROR_TRACKING_PROVIDER` controls backend error tracking. Use `google-cloud` on Cloud Run to send unhandled API exceptions and failed request-based task exceptions to Google Cloud Error Reporting with redacted request/job context; no DSN is required for that provider. `ERROR_TRACKING_DSN` is only required when `ERROR_TRACKING_PROVIDER=sentry`.

## Security and pilot settings

- `RATE_LIMIT_ENABLED`: enables route-level rate limiting for sensitive actions.
- `RATE_LIMIT_DEFAULT_LIMIT`, `RATE_LIMIT_DEFAULT_WINDOW_SECONDS`: default limiter settings.
- `RATE_LIMIT_SENSITIVE_LIMIT`, `RATE_LIMIT_SENSITIVE_WINDOW_SECONDS`: limiter settings for OAuth, sync, triage, retry, draft, and invite actions.
- `MAX_REQUEST_BODY_BYTES`: maximum accepted request body size before the API returns `413`.
- `ENCRYPTION_KEY_VERSION`: metadata version recorded on newly stored Gmail refresh tokens.
- `ENCRYPTION_KEYRING`: previous-key map used only during encryption-key rotation, for example `1:old-secret,2:older-secret`. Keep this in Secret Manager or an equivalent backend-only secret store.
- `PILOT_REQUIRE_ALLOWLIST`: when true, pilot-gated organization actions require the organization ID to appear in `PILOT_ALLOWLISTED_ORGANIZATION_IDS`.
- `PILOT_ALLOWLISTED_ORGANIZATION_IDS`: comma-separated organization IDs allowed to use pilot-gated production paths.
- `PILOT_SYNC_ENABLED`: global kill switch for Gmail sync/import/history/watch behavior.
- `PILOT_AUTO_TRIAGE_ENABLED`: global kill switch for automatic AI triage queueing.
- `PILOT_DRAFT_CREATION_ENABLED`: global kill switch for Gmail draft creation.

Workspace owners/admins can also disable sync and draft creation per workspace through workspace settings. Automatic triage can still be disabled per workspace through `auto_triage_enabled`.

See `docs/SECURITY_AND_DATA_CONTROLS.md` for rotation, reauthorization, export, deletion, retention, and backup/restore procedures.

## Migration validation

Every schema change must include an Alembic migration. CI validates migrations with:

```powershell
cd apps/api
alembic upgrade head
alembic downgrade base
alembic upgrade head
```

Production deployments should run:

```powershell
cd apps/api
alembic upgrade head
```

before starting the new API release.
