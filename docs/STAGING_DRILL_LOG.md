# Staging Drill Log

## 2026-07-13 - Supabase backup/restore drill

Status: Complete.

What was verified:

- Active staging database inventory and integrity checks passed.
- A staging public-schema custom-format dump was created with PostgreSQL 18.4 client tools.
- The dump was restored into a temporary local PostgreSQL database named `sift_restore_drill_20260713`.
- Restored migration head matched staging: `0018_widen_gmail_attachment_id`.
- Restored core table counts matched the staging database at the dump point.
- Restored database integrity checks passed.
- The backend database layer successfully connected to the restored database and loaded core records.
- Temporary restore database and local dump file were deleted after verification.

Environment checked:

- Supabase project: `ai-customer-support-triage-response`
- Project ref: `gvpftpnyqeancxugyxqf`
- Region: `ap-northeast-1`
- Database status from Supabase: `ACTIVE_HEALTHY`
- Migration head in staging/restored database: `0018_widen_gmail_attachment_id`
- Local PostgreSQL client tools: `18.4`

Restored core table inventory:

| Table | Rows |
| --- | ---: |
| `audit_logs` | 14 |
| `gmail_connections` | 2 |
| `job_runs` | 130 |
| `organization_members` | 4 |
| `organizations` | 4 |
| `reply_approvals` | 46 |
| `ticket_attachments` | 1 |
| `tickets` | 115 |

Integrity checks on restored database:

| Check | Issues |
| --- | ---: |
| `approvals_missing_ticket` | 0 |
| `attachments_missing_ticket` | 0 |
| `gmail_connections_missing_org` | 0 |
| `jobs_missing_org_when_set` | 0 |
| `members_missing_org` | 0 |
| `tickets_missing_org` | 0 |

App-layer restore check:

- Backend SQLAlchemy engine connected to the restored database.
- Loaded migration head, organizations, tickets, and ticket attachment counts successfully.

Notes:

- Supabase branching was not available on the current plan, so the restore target was a temporary local PostgreSQL database instead of a Supabase branch.
- `pg_restore` reported that the local `public` schema already existed, then continued restoring successfully. The restored table counts, migration head, integrity checks, and app-layer reads all passed.
- No restore was performed against the active staging Supabase project.

## 2026-07-13 - Cloud Run and Vercel rollback drill

Status: Complete.

Completed:

- Recorded current Cloud Run staging revision: `sift-api-staging-00025-4dp`.
- Identified previous healthy Cloud Run revision: `sift-api-staging-00024-vdh`.
- Recorded current Vercel production deployment: `dpl_2pdPBd87Hd8bzu91YdNTkTkEKb9p`.
- Identified Vercel rollback candidate: `dpl_2DGbXGEcaeqk1MprVt8petkZBRuJ`.
- Recorded staging migration head: `0018_widen_gmail_attachment_id`.
- Recorded Cloud Scheduler jobs:
  - `sift-staging-fallback-sync` -> `/v1/tasks/scheduler/fallback-sync`
  - `sift-staging-watch-renewals` -> `/v1/tasks/scheduler/watch-renewals`
- Recorded Pub/Sub push targets for Gmail webhook, Gmail import, Gmail history sync, AI triage, and watch renewal.
- Shifted Cloud Run staging traffic from `sift-api-staging-00025-4dp` to `sift-api-staging-00024-vdh`.
- Verified rollback revision health:
  - `/health` returned `ok`.
  - `/health/ready` returned `ready` with database and Pub/Sub configured.
  - `/v1/status` returned `ok` with database and Pub/Sub configured.
- Restored Cloud Run staging traffic to `sift-api-staging-00025-4dp`.
- Verified restored revision health and readiness.
- Verified Vercel production routes respond with `200 OK`:
  - `/`
  - `/dashboard`
  - `/dashboard/settings/gmail`

Additional Vercel alias rollback proof completed on 2026-07-13:

- Vercel CLI was run through the bundled Node runtime with `pnpm dlx vercel` and authenticated as `simognf-5646`.
- Temporarily rolled production alias back from `dpl_2pdPBd87Hd8bzu91YdNTkTkEKb9p` to rollback candidate `dpl_2DGbXGEcaeqk1MprVt8petkZBRuJ`.
- Verified rollback deployment routes returned `200 OK`:
  - `/`
  - `/dashboard`
  - `/dashboard/settings/gmail`
- Restored production alias to `dpl_2pdPBd87Hd8bzu91YdNTkTkEKb9p`.
- Verified restored production routes returned `200 OK`:
  - `/`
  - `/dashboard`
  - `/dashboard/settings/gmail`
- Vercel project inspection confirmed latest production deployment is again `dpl_2pdPBd87Hd8bzu91YdNTkTkEKb9p`.

Result:

- Cloud Run rollback and restore path is proven for staging.
- Vercel production alias rollback and restore path is proven.`r`n`r`n## 2026-07-13 - Staging soak window

Status: Partially complete.

Window:

- Start: 2026-07-13T08:56:15Z
- End: 2026-07-13T09:04:19Z
- Duration: about 8 minutes

Completed checks:

- Ran five repeated checks of Cloud Run `/health`, Cloud Run `/health/ready`, and the Vercel `/dashboard` route.
- Every live check passed:
  - `/health` returned `ok`.
  - `/health/ready` returned `ready` with database and Pub/Sub configured.
  - Vercel `/dashboard` returned `200 OK`.
- Confirmed Cloud Run traffic remained on `sift-api-staging-00025-4dp` at 100%.
- Confirmed both Gmail connections are active:
  - `simognf@gmail.com`: `sync_status=active`, `watch_status=active`, zero consecutive sync failures.
  - `razelfabregas@gmail.com`: `sync_status=active`, `watch_status=active`, zero consecutive sync failures.
- Confirmed Gmail watches remain active until 2026-07-18 for both inboxes.
- Confirmed Pub/Sub push subscriptions are active for Gmail webhook, Gmail import, Gmail history sync, AI triage, and watch renewal.
- Confirmed Cloud Scheduler jobs are enabled for fallback sync and watch renewal.
- Observed live Gmail sync during the window:
  - `simognf@gmail.com` received a notification at 2026-07-13T09:03:45Z and synced successfully at 2026-07-13T09:03:48Z.
  - `simognf@gmail.com` ticket count increased from 85 to 88 during the window.
- Confirmed `razelfabregas@gmail.com` has imported tickets and the attachment smoke case remains present.
- Confirmed stored attachment state:
  - `Simogn_Fabregas_Resume.pdf`, `application/pdf`, `stored`, `clean`.
- Confirmed no duplicate Gmail message imports were found by `(gmail_connection_id, gmail_message_id)`.
- Confirmed recent AI triage job records ended successfully during the window, including one retry that succeeded after a transient Gemini reachability error.

Observed issues:

- Cloud Run logs showed one transient AI triage failure at 2026-07-13T09:00:11Z: `Could not reach Gemini API from the API server`.
- The affected recent job later completed successfully after retry, so this did not become a stuck queue condition.
- No `task.job_deferred` logs appeared during the 15-minute post-window check.

Not completed:

- Approval and Gmail draft creation were not verified in this soak window. Staging currently has 49 pending reply approvals, zero approved approvals, zero draft-created approvals, and zero rows in `gmail_drafts`.
- Completing that part requires a signed-in user to approve one pending reply from the dashboard and create the Gmail draft.

Result:

- Staging sync/import/watch health passed for both connected Gmail inboxes during the live window.
- Attachment storage state remains valid.
- No duplicate imports were detected.
- One Gemini reachability blip occurred and recovered through retry.
- Full production soak is still blocked on manual approval-to-draft verification in the UI.

## 2026-07-13 - Approval-to-draft soak completion

Status: Complete.

Correction:

- The production-facing dashboard workflow stores approval state in `reply_suggestions`, not `reply_approvals`.
- Earlier soak checks that counted only `reply_approvals` incorrectly reported zero approved items even though the UI approval later persisted through the active workflow table.

Verified records:

- Reply suggestion `636bcbc0-86de-4d25-bc97-67c97af16607` moved to `draft_created`.
- Reply suggestion approval time: 2026-07-13T09:16:11Z.
- Gmail draft row `a54755f9-e477-4d8e-8c75-c3f0152ef280` was created at 2026-07-13T09:19:20Z.
- Linked ticket `f2728392-16be-4b2e-bb5d-10608fc6758a` moved to `draft_created`.
- Audit logs include:
  - `reply_suggestion.approved` at 2026-07-13T09:16:11Z.
  - `gmail.draft.created` at 2026-07-13T09:19:20Z.

Final workflow counters:

| Metric | Count |
| --- | ---: |
| `reply_suggestions_pending` | 0 |
| `reply_suggestions_approved` | 0 |
| `reply_suggestions_draft_created` | 1 |
| `gmail_drafts` | 1 |

Result:

- Approval-to-draft staging soak is complete.
- The full Gmail sync/import/triage/approval/draft path has now been verified in staging, with the known caveat that Gemini may still hit provider quota/reachability limits during repeated tests.

## 2026-07-13 - Staging Secret Manager migration

Status: Complete for staging secret-store migration. Provider-side credential replacement remains pending.

Completed:

- Created Google Secret Manager secrets for current staging values:
  - `sift-staging-google-client-secret`
  - `sift-staging-gemini-api-key`
  - `sift-staging-encryption-key`
  - `sift-staging-database-url`
- Confirmed existing `supabase_secret` is used for `SUPABASE_SECRET_KEY`.
- Updated Cloud Run staging so these sensitive values are loaded from Secret Manager instead of plain environment values:
  - `GOOGLE_CLIENT_SECRET`
  - `GEMINI_API_KEY`
  - `ENCRYPTION_KEY`
  - `SUPABASE_SECRET_KEY`
  - `DATABASE_URL`
- Confirmed no temporary local secret files remained in `C:\tmp` after migration.
- Verified Cloud Run health, readiness, and `/v1/status` after the update.

Verification:

- `/health` returned `ok`.
- `/health/ready` returned `ready` with database and Pub/Sub configured.
- `/v1/status` returned `ok` with database and Pub/Sub configured.
- Cloud Run traffic remained on `sift-api-staging-00025-4dp` at 100%.

Not completed:

- This migrated current values into Secret Manager; it did not generate new provider-side credentials.
- True rotation still requires creating replacement values in the provider dashboards/APIs for Google OAuth, Gemini, Supabase, and any production database credentials.
- Rotating `ENCRYPTION_KEY` now has multi-key decrypt support through `ENCRYPTION_KEYRING`, but live rotation still requires deploying the old key in the keyring until affected Gmail connections reconnect or are re-encrypted.

## 2026-07-13 - Encryption keyring backend deploy

Status: Complete for staging code deployment. Live provider-side credential replacement remains pending.

Actions:

- Deployed the backend build with `ENCRYPTION_KEYRING` support to Cloud Run staging.
- Granted the Cloud Run staging runtime service account `roles/secretmanager.secretAccessor` on the staging Secret Manager secrets required by the new revision.
- Routed staging traffic to Cloud Run revision `sift-api-staging-00027-v58`.
- Verified `/health`, `/health/ready`, and `/v1/status` returned `200` after routing traffic.

Notes:

- No live `ENCRYPTION_KEY` rotation was performed in this step.
- Future encryption-key rotation must keep previous key versions available through `ENCRYPTION_KEYRING` until no active Gmail connection depends on them.

## 2026-07-13 - Gemini staging key rotation

Status: Complete for staging Gemini provider credential replacement.

Actions:

- Created a new staging Gemini API key restricted to `generativelanguage.googleapis.com`.
- Stored the final key as Secret Manager version `3` for `sift-staging-gemini-api-key`.
- Restarted Cloud Run staging so the API reads the latest Gemini secret version.
- Enabled `generativelanguage.googleapis.com` in project `customer-support-triage-501408` after the direct Gemini verification reported the service was disabled.
- Disabled older Secret Manager versions `1` and `2` for `sift-staging-gemini-api-key`.
- Deleted exposed intermediate Gemini API keys created during the rotation attempt.

Verification:

- Cloud Run `/health/ready` returned `200`.
- Direct Gemini model-list reachability using the latest secret returned `200`.
- Secret Manager now shows version `3` enabled and versions `1` and `2` disabled.

Notes:

- Gemini quota/billing limits are unchanged by this key rotation.
- No Gmail, Supabase, Google OAuth, or encryption-key provider credentials were rotated in this step.

## 2026-07-13 - Google OAuth client secret rotation attempt

Status: Complete for backend-side staging Google OAuth secret rotation. Old Google Console client secret disablement remains manual.

Findings:

- Cloud Run staging reads `GOOGLE_CLIENT_SECRET` from Secret Manager secret `sift-staging-google-client-secret:latest`.
- `sift-staging-google-client-secret` currently has version `1` enabled.
- The installed `gcloud iam oauth-clients` commands manage IAM OAuth clients, not the existing Gmail OAuth web client used by this app. The command-supported OAuth client type only lists limited Google Cloud identity scopes and does not cover Gmail scopes required by this product.
- `gcloud iam oauth-clients list --location=global` returned no manageable clients for this project.

Actions after Console reset:

- Added the new OAuth client secret as Secret Manager version `2` for `sift-staging-google-client-secret`.
- Removed the temporary local secret file from `C:\tmp`.
- Restarted Cloud Run staging so it reads the latest OAuth secret.
- Verified Cloud Run `/health/ready` and `/v1/status` returned `200`.

Remaining verification:

- Gmail OAuth reconnect from the Vercel app succeeded.
- Disabled Secret Manager version `1`; version `2` remains enabled.
- Cloud Run `/health/ready` returned `200` after disabling version `1`.
- The old OAuth client secret `****7Xgv` was disabled in Google Cloud Console.

## 2026-07-13 - Supabase backend secret rotation

Status: Complete for staging Supabase backend secret rotation.

Actions:

- Added the new Supabase backend secret as Secret Manager version `2` for `supabase_secret`.
- Removed the temporary local secret file from `C:\tmp`.
- Restarted Cloud Run staging so it reads the latest Supabase secret.
- Verified the latest Supabase secret authenticated to Supabase Admin API with status `200`.
- Disabled old Secret Manager version `1`; version `2` remains enabled.

Verification:

- Cloud Run `/health/ready` returned `200` after restart and after disabling version `1`.
- `supabase_secret` version `2` is enabled and version `1` is disabled.

Notes:

- The app currently requires `SUPABASE_SECRET_KEY` at startup for staging/production configuration. Normal JWT verification uses Supabase JWKS.

## 2026-07-13 - Encryption key rotation

Status: Complete for staging `ENCRYPTION_KEY` rotation.

Actions:

- Created Secret Manager secret `sift-staging-encryption-keyring` for previous encryption keys.
- Stored the previous active encryption key in keyring format as version `1:<old-key>` without printing secret values.
- Generated a new random active encryption key and stored it as `sift-staging-encryption-key` version `2`.
- Updated Cloud Run staging with `ENCRYPTION_KEYRING=sift-staging-encryption-keyring:latest` and `ENCRYPTION_KEY_VERSION=2`.
- Disabled old active encryption-key Secret Manager version `1`; version `2` remains enabled.

Verification:

- Cloud Run `/health/ready` returned `200`.
- Cloud Run `/v1/status` returned `200`.
- Existing Gmail refresh token decrypt smoke test checked `2` connections with `0` failures before and after disabling old active key version `1`.
- Temporary local rotation files were removed.

Notes:

- Existing Gmail connections still have `token_key_version=1` and decrypt through `ENCRYPTION_KEYRING`.
- Newly connected/reconnected Gmail accounts will store tokens with `token_key_version=2`.
- Keep `sift-staging-encryption-keyring` enabled until no active Gmail connection depends on token key version `1`, or until a future re-encryption job rewrites those tokens.

## 2026-07-13 - Google Cloud Error Reporting deploy

Status: Configured, deployed, and verified with a controlled staging event.

Actions:

- Switched the backend error tracking path to support `ERROR_TRACKING_PROVIDER=google-cloud` with no external DSN.
- Added safe event redaction for token, authorization, API key, password, prompt, and email-body fields before sending events.
- Captures unhandled API exceptions and failed request-based task exceptions with safe request/job/resource context.
- Added `google-cloud-error-reporting` to backend dependencies and kept the old DSN-backed Sentry path as an optional fallback.
- Enabled `clouderrorreporting.googleapis.com` in `customer-support-triage-501408`.
- Granted `roles/errorreporting.writer` to the Cloud Run runtime service account `1019789305707-compute@developer.gserviceaccount.com`.
- Deployed the backend to Cloud Run staging revision `sift-api-staging-00034-ttt` with `ERROR_TRACKING_PROVIDER=google-cloud`.
- Added a hidden `POST /v1/operations/error-reporting-test` endpoint protected by the existing Scheduler OIDC service-account check.
- Deployed the protected verification endpoint to Cloud Run staging revision `sift-api-staging-00037-j6v` after correcting the deployment source to `apps/api` and routing 100% traffic to that revision.
- Created, ran once, and deleted temporary Scheduler job `sift-error-reporting-test-20260713` to trigger the endpoint with Google OIDC.

Verification:

- Full backend test suite passed: `164 passed`.
- Ruff passed for backend app and focused tests.
- Cloud Run service configuration shows `ERROR_TRACKING_PROVIDER=google-cloud`.
- Cloud Run `/health/ready` returned `200`.
- Cloud Run `/v1/status` returned `200` with database and Pub/Sub task queue healthy.
- Cloud Run traffic is 100% on `sift-api-staging-00037-j6v`.
- Unauthenticated `POST /v1/operations/error-reporting-test` returned `401`.
- Scheduler OIDC `POST /v1/operations/error-reporting-test` returned `200`.
- Google Cloud Error Reporting returned group `CJzzx9Gtis-cSg` under service `api`, version `0.1.0`, message `operations.error_reporting_test: RuntimeError: sift controlled error reporting test`.
- Cloud Run logs show no `error_tracking.missing_dependency` warning after deploy.

Notes:

- Google Cloud documentation says Cloud Run can use the Python Error Reporting library without explicit credentials when the runtime service account has Error Reporting Writer access.
- Controlled Error Reporting event delivery is verified. Future checks can reuse the hidden OIDC-protected endpoint with a temporary Scheduler job or direct Google service-account OIDC call.





## 2026-07-13 - Gemini free-only quota guard

Status: Implemented, deployed, and verified in Cloud Run staging.

Actions:

- Chose free-only Gemini operation for the current pilot stage; no paid Gemini billing/quota expansion is required yet.
- Added `AI_TRIAGE_DAILY_GEMINI_LIMIT` with default `20` Gemini triage calls per UTC day.
- Added a backend guard that defers extra AI triage jobs before calling Gemini once the app-side daily cap is reached.
- Kept existing provider quota handling so real Gemini 429 responses still become visible, retryable `quota_exceeded` failures with retry timing.

Verification:

- Focused backend tests passed: `32 passed`.
- Full backend test suite passed: `168 passed`.
- Ruff passed for the backend app and focused tests.
- Cloud Run staging service configuration shows `AI_TRIAGE_DAILY_GEMINI_LIMIT=20`.
- Cloud Run `/health/ready` returned `200`.
- Cloud Run `/v1/status` returned `200`.

Notes:

- Cloud Run staging has `AI_TRIAGE_DAILY_GEMINI_LIMIT=20` set. Keep the same value in production while the product remains free-only.
- Use `0` only if the app-side cap should be disabled and the system should rely entirely on provider-side quota responses.

## 2026-07-13 - M11 multiple Gmail inbox staging verification

Status: Implemented, deployed, and verified for backend/staging data. Signed-in browser creation of a saved view with an inbox filter remains optional.

Actions:

- Fixed saved-view filter sanitization so `gmail_connection_id` and `sla_status` are preserved instead of being stripped.
- Added backend coverage for saved-view inbox-filter preservation.
- Deployed the backend fix to Cloud Run staging.

Verification:

- Full backend test suite passed: `169 passed`.
- Focused M11/M8/ticket tests passed: `20 passed`.
- Ruff passed for the touched backend service and related tests.
- Frontend production build passed.
- Cloud Run `/health/ready` returned `200`.
- Cloud Run `/v1/status` returned `200`.
- Vercel `/dashboard/tickets` returned `200`.
- Staging Supabase migration head is `0018_widen_gmail_attachment_id`.
- Staging has `2` active Gmail inbox connections in one organization.
- Both staging inboxes have `sync_status=active`, `watch_status=active`, future watch expirations, no sync error code, and no watch error.
- Tickets are linked to both source inboxes: `30` for one inbox and `94` for the other at verification time.
- Both inboxes have active import rules with `routing_direction=shared_queue`.

Notes:

- No schema migration was needed for the saved-view filter fix.
- Existing staging data had no saved views containing `gmail_connection_id` at verification time, so live saved-view preservation was verified by deployed backend code and automated tests rather than by creating a new signed-in browser saved view.

## 2026-07-13 - Production-readiness cleanup verification

Status: Verified for staging Cloud Run/Pub/Sub/Scheduler/Error Reporting. Follow-up Supabase database/pooler password rotation completed on 2026-07-14.

Actions:

- Routed Cloud Run staging traffic to ready revision `sift-api-staging-00039-8dc` after discovering the service was still sending 100% traffic to `sift-api-staging-00037-j6v`.
- Ran the existing Cloud Scheduler fallback-sync and watch-renewal jobs manually to verify protected scheduler routes after the latest deploy.
- Triggered the protected Error Reporting test endpoint through a temporary OIDC Scheduler job, then deleted the temporary job.
- Checked Secret Manager version states without printing secret values.
- Checked recent staging job/sync records and Gmail connection health.

Verification:

- Cloud Run traffic is 100% on `sift-api-staging-00039-8dc`.
- Cloud Run `/health/ready` returned `200`.
- Cloud Run `/v1/status` returned `200`.
- All Gmail/task Pub/Sub push subscriptions are `ACTIVE` and point at the Cloud Run staging URL with `sift-pubsub-push-staging` OIDC authentication.
- Scheduler jobs `sift-staging-fallback-sync` and `sift-staging-watch-renewals` are `ENABLED`, point at the Cloud Run staging URL, and use `sift-scheduler-staging` OIDC authentication.
- Manual Scheduler runs completed with empty status objects; fallback sync recorded recent succeeded `gmail_sync_events`.
- Watch-renewal manual run had no due work because both staging Gmail watches are active and future-dated.
- Google Cloud Error Reporting group `CJzzx9Gtis-cSg` now has count `2`, with last seen time `2026-07-13T15:20:12Z` for the controlled backend event.
- Secret Manager states: Google OAuth client secret version `2` enabled/version `1` disabled; Gemini API key version `3` enabled/versions `1` and `2` disabled; Supabase backend secret version `2` enabled/version `1` disabled; active encryption key version `2` enabled/version `1` disabled; encryption keyring version `1` enabled; database URL version `1` enabled.
- Recent staging DB check found no failed Gmail sync events and both active Gmail inboxes have `sync_status=active`, `watch_status=active`, no sync error code, and no watch error.
- Recent non-success job runs are limited to retryable `ai_triage` / `quota_exceeded` failures from Gemini free-tier testing.

Follow-up credential rotation:

- Supabase database/pooler password rotation was completed on 2026-07-14. The Cloud Run staging service was restarted against the updated Secret Manager `sift-staging-database-url` value, the old secret version was disabled, and `/health/ready` plus `/v1/status` returned `200` with database status `ok`.

## 2026-07-14 - Attachment AI opt-in migration

Status: Applied and verified in staging Supabase.

- Applied Alembic migration `0021_attachment_ai_optin` to staging Supabase after shortening the revision id to fit the existing `alembic_version.version_num` length.
- Verified `alembic_version.version_num = 0021_attachment_ai_optin`.
- Verified `workspace_settings.attachment_ai_processing_enabled` exists with `default=false` and `nullable=NO`.
## 2026-07-14 - Gmail workflow UI deploy and AI smoke attempt

Status: Backend/frontend deployed; route smoke passed. AI provider smoke blocked by Gemini billing/credits.

- Deployed Cloud Run staging service `sift-api-staging` from `apps/api`; Cloud Run reported revision `sift-api-staging-local-cors-20260714` serving 100% traffic.
- Cloud Run `/health/ready` returned `200` and `/v1/status` returned `200` after deploy.
- Deployed Vercel frontend deployment `dpl_APyHgUQ5jpAGgowEbt4NG7Pve1FE` and pointed `https://ai-customer-support-triage-response.vercel.app` to it.
- Vercel `/dashboard/settings/readiness`, `/dashboard/settings/gmail`, and `/dashboard/tickets` returned `200`.
- Added UI follow-ups for attachment AI opt-in visibility, Gmail shared-source saved-vs-draft source display, sync/watch next-step guidance, and Gmail draft-created state.
- Attempted five Gemini triage-v2 provider smoke prompts, but Gemini returned a credits/prepayment depletion error before classifications could be verified.
## 2026-07-14 - M11 Gmail-first closure smoke

- Confirmed signed-in Settings -> Readiness smoke in the stable Vercel app: Attachment AI processing starts default-off, can be enabled by owner/admin, saves, and persists after refresh.
- Confirmed signed-in Gmail settings smoke in the stable Vercel app: Google Group/shared mailbox source editing behaves correctly with saved-source display separated from unsaved edits.
- Rechecked Cloud Run staging after env repair: revision `sift-api-staging-00062-cll` serves 100% traffic, `/health/ready` returns 200, and the live OpenAPI schema exposes `attachment_ai_processing_enabled` and `direct_send_enabled` for workspace settings read/update.
- M11 Gmail-first expansion is ready to move into pilot hardening. Real Gemini multi-email classification smoke remains pending until provider credits/quota are available.

## 2026-07-15 - Gemini pilot classification smoke runner

Status: Smoke runner implemented; real provider classification smoke remains blocked by Gemini credits/prepayment.

Checks performed:
- Added `apps/api/scripts/gemini_triage_smoke.py`, which uses the same Gemini prompt/schema path as production ticket triage with four synthetic pilot emails: urgent refund/billing, damaged item, account access, and product question.
- Ran the smoke runner with the staging Secret Manager key `sift-staging-gemini-api-key` without printing the secret.
- The runner stopped after the first case to conserve quota.

Result:
- Gemini returned `too_many_requests` with message: `Your prepayment credits are depleted`.
- No real AI classifications were produced, so the multi-email Gemini classification smoke remains pending.
- The app behavior observed in staging is expected: imported tickets remain visible, AI state shows retry/quota pause, and fallback `medium` / `other` values are hidden from the queue/detail UI unless AI triage actually succeeds.

Next action:
- Restore Gemini prepayment credits or provider availability in AI Studio, then rerun `apps/api/scripts/gemini_triage_smoke.py` before connecting a real pilot inbox.
