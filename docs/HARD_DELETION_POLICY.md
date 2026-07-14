# Future Hard-Deletion Policy

This policy describes the intended future hard-deletion process. The current product only records deletion requests and pauses workspace automation; it does not yet hard-delete organization data automatically.

## Current Behavior

When an owner requests organization deletion from Settings -> Readiness, the backend:

1. Records an audit event.
2. Stores the deletion-request metadata in workspace settings.
3. Pauses Gmail sync, automatic AI triage, and Gmail draft creation.
4. Leaves organization records in place for operator review.

## Future Operator-Reviewed Hard Deletion

Before hard deletion is implemented, legal/product must approve the retention rules and exceptions. The intended flow is:

1. Verify the requester is the organization owner.
2. Confirm the organization ID, requester identity, and request timestamp.
3. Pause all automation immediately.
4. Revoke or disconnect active Gmail connections where possible.
5. Generate and offer a final export before irreversible deletion.
6. Wait through the approved retention/cooling-off window.
7. Run a dry-run deletion report listing organization-scoped records and attachment objects.
8. Require a second operator confirmation for the final hard delete.
9. Delete organization-scoped operational data, including customers, tickets, ticket events, AI triage results, reply suggestions, approvals, Gmail drafts, Gmail sync events, job runs, saved views, routing rules, templates, notes, locks, and stored attachment objects.
10. Retain only minimal records required for security, abuse prevention, audit, legal, tax, or compliance purposes.
11. Record an audit tombstone that does not contain imported Gmail message bodies, attachment contents, refresh tokens, or AI prompt bodies.
12. Verify backups age out according to the documented backup-retention policy.

## Data That Must Not Be Exposed In Exports Or Tombstones

- Gmail refresh tokens or provider access tokens.
- Backend service keys, database URLs, encryption keys, or API keys.
- Raw attachment bytes unless delivered through the approved export channel.
- Cross-organization records.

## Implementation Requirements Before Shipping Hard Delete

- Legal approval recorded in `docs/LEGAL_REVIEW_CHECKLIST.md`.
- A migration or data model for deletion request status, retention deadline, and operator approvals.
- A dry-run deletion command or endpoint with record counts.
- Storage deletion support for attachment objects.
- Tests proving tenant isolation and token exclusion.
- A staging drill recorded in `docs/STAGING_DRILL_LOG.md`.
