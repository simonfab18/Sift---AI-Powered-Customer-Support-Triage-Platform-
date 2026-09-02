# Security and Data Controls

## Secret and Token Lifecycle

Production and staging secrets must live in the hosting/provider secret store, not in source control or frontend bundles.

Required rotation procedure for `ENCRYPTION_KEY`:

1. Create the replacement active encryption key in the provider secret store.
2. Keep the previous key available through backend-only `ENCRYPTION_KEYRING` using `version:key` format.
3. Deploy the API with the replacement `ENCRYPTION_KEY`, incremented `ENCRYPTION_KEY_VERSION`, and the previous key in `ENCRYPTION_KEYRING`.
4. Verify existing Gmail connections can still sync and newly connected/reconnected accounts show the new `token_key_version`.
5. Remove an old key from `ENCRYPTION_KEYRING` only after no active Gmail connection uses that `token_key_version`.

Encrypted Gmail refresh tokens are versioned with `token_key_version`, and the backend can decrypt previous key versions through `ENCRYPTION_KEYRING`. Automatic bulk re-encryption is not implemented yet, so old keys must stay configured until affected Gmail accounts reconnect or a future re-encryption job rewrites those tokens.

Staging `ENCRYPTION_KEY` rotation completed on 2026-07-13: the active key is version `2`, and previous Gmail token version `1` remains available through `sift-staging-encryption-keyring`.


## Current Secret Store Status

As of 2026-07-13, Cloud Run staging loads these sensitive values from Google Secret Manager: `GOOGLE_CLIENT_SECRET`, `GEMINI_API_KEY`, `ENCRYPTION_KEY`, `SUPABASE_SECRET_KEY`, and `DATABASE_URL`.

This is a secret-store migration for the current values, not full credential rotation. Before a real pilot, create replacement provider-side credentials where applicable, add them as new secret versions, deploy, verify, and revoke the old provider credentials after dependent services are confirmed healthy. Google OAuth client secret rotation requires a Google Cloud Console reset; see `docs/GOOGLE_OAUTH_SECRET_ROTATION.md`.

## Gmail Reauthorization

When Google rejects a refresh token as revoked or invalid, the backend marks the Gmail connection as:

```text
status = reauthorization_required
sync_status = reauthorization_required
watch_status = reauthorization_required
sync_error_code = reauthorization_required
```

The connection is recoverable by starting Gmail OAuth again for the same Google account. Reauthorization clears the error state and stores the new token using the current `ENCRYPTION_KEY_VERSION`.

## Gmail Disconnect Semantics

Disconnecting Gmail marks the connection as revoked/disconnected and stops sync/watch operations. Existing tickets, audit logs, triage results, reply approvals, and Gmail draft records remain in the application for continuity and auditability.

Disconnect does not delete imported email content. Organization deletion/export controls are required before real production customers can self-serve data removal.

## Organization Export Direction

Self-serve organization export now exists for owner/admin users in Settings -> Readiness. Operator-run exports should still follow the same data-boundary rules:

1. Verify requester identity and owner/admin role.
2. Export organization-scoped records only: organization, members, customers, tickets, ticket events, audit logs, Gmail connection metadata, sync events, AI triage results, reply suggestions/approvals, and draft metadata.
3. Exclude encrypted refresh tokens and provider access tokens.
4. Deliver exports through a secure, expiring channel.
5. Record the export in audit logs.

## Organization Deletion Direction

Deletion must be explicit, audited, and delayed enough to prevent accidental loss. The current self-serve control records an owner deletion request and pauses workspace automation; it does not hard-delete records automatically. See `docs/HARD_DELETION_POLICY.md` for the future operator-reviewed hard-deletion policy.

Recommended future behavior:

1. Disable Gmail sync and revoke active connections.
2. Soft-delete or archive the organization immediately.
3. Queue hard deletion for organization-scoped data after a retention window.
4. Preserve minimal billing/security/audit records only where legally required.
5. Verify backups age out according to the backup-retention policy.

## Retention Policy

Initial pilot policy direction:

- Ticket email bodies: retain while the organization is active.
- Gmail sync events and job runs: retain operational history for at least 90 days.
- Audit logs: retain for at least 1 year during pilot unless legal requirements differ.
- AI prompts/outputs: retain only what is needed for ticket auditability and troubleshooting.
- Attachments: not imported by default; add an explicit attachment policy before enabling attachment ingestion.

## Backup and Restore

Before pilot launch:

1. Confirm database backup schedule and retention in the managed database provider.
2. Restore the latest staging backup into an isolated staging database.
3. Run migrations against the restored database.
4. Verify organization list, tickets, audit logs, Gmail connection metadata, and operations status load correctly.
5. Record restore date, operator, source backup, and result.

## Frontend Secret Boundary

Frontend bundles must never include service-role keys, Gmail client secrets, Gemini API keys, encrypted refresh tokens, raw refresh tokens, internal operations tokens, or database URLs.

## Legal Review Boundary

Privacy, terms, data-processing, support, status, export, and deletion policy text is product-readiness documentation only until reviewed and approved. Track that external approval in `docs/LEGAL_REVIEW_CHECKLIST.md`.
