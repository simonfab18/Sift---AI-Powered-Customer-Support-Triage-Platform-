# Gmail-First Pilot Runbook

Status: ready for Gmail-first pilot operations after technical staging verification.

This runbook is for the free Gmail-first pilot. It does not approve public commercial launch, paid billing, live direct send, Outlook, chat channels, or self-serve hard deletion.

## Current Pilot Posture

- Frontend: `https://ai-customer-support-triage-response.vercel.app`
- API: `https://sift-api-staging-1019789305707.asia-southeast1.run.app`
- Backend runtime: Cloud Run `sift-api-staging`
- Async work: Google Pub/Sub task topics and request-based Cloud Run task handlers
- Database/auth: Supabase
- AI model: `gemini-3.1-flash-lite`
- AI mode: free-only with app-side daily caps
- Sending mode: Gmail drafts only; live direct send remains off

## Before Connecting a Real Pilot Inbox

1. Confirm the pilot owner/admin can sign in.
2. Open Settings -> Readiness.
3. Confirm the pilot support contact is set and valid.
4. Confirm Gmail sync is enabled.
5. Confirm automatic AI triage is enabled if the pilot wants AI classification.
6. Confirm Gmail draft creation is enabled and approval is required.
7. Confirm Direct Gmail send is off.
8. Confirm Attachment AI processing is off unless the owner explicitly opted in.
9. Open Settings -> Gmail and confirm every connected inbox is healthy.
10. Open Dashboard and confirm the Pilot operations panel is understandable.

## Daily Pilot Monitoring

Run these checks at the start and end of each pilot day:

1. Settings -> Gmail
   - All connected inboxes should show healthy sync/watch status.
   - No import should be stuck in running state.
   - Watch expiration should be in the future.

2. Dashboard -> Pilot operations
   - Review degraded inbox count.
   - Review failed import or AI jobs.
   - Retry only retryable jobs.
   - For manual-review jobs, inspect the related ticket or Gmail settings before retrying.

3. Settings -> Readiness
   - Confirm AI usage remaining for the day.
   - If AI is paused by the app-side cap, agents can still review tickets manually and retry later.
   - Confirm direct send is still off.

4. Tickets
   - Failed AI triage tickets should show Not classified, not fallback medium/other labels.
   - Agents should review suggested replies before drafts are created.
   - Approved replies should create Gmail drafts only.

## Test Email Smoke Set

Use these as simple pilot checks when validating AI behavior:

1. Refund/billing urgent
   - Expected: refund, high, human review required.

2. Damaged item
   - Expected: damaged_item, high, human review required.

3. Account access
   - Expected: account_access, medium or high, human review required.

4. Product question
   - Expected: product_question, low or medium, no human review unless details are risky.

For direct provider verification, run `apps/api/scripts/gemini_triage_smoke.py` with the staging Gemini Secret Manager key.

## If Gmail Sync Is Degraded

1. Open Settings -> Gmail.
2. Check whether an import is already running.
3. If no import is running, click Import now.
4. If watch remains degraded, reconnect Gmail.
5. If reconnect fails, check Pub/Sub push configuration and Scheduler/watch renewal.
6. Keep tickets visible and handle urgent messages manually from Gmail if needed.

## If AI Triage Fails

1. Confirm the ticket is visible in the queue.
2. Confirm the UI shows Not classified if no AI result exists.
3. Check Settings -> Readiness for daily AI usage remaining.
4. If the job is retryable, use Retry from the dashboard operations panel or Regenerate from ticket detail.
5. If Gemini quota/caps are exhausted, handle the ticket manually and retry after reset.

## Draft And Approval Policy

- Suggestions are not sent automatically.
- Agents must review and approve suggested replies.
- Approved replies create Gmail drafts.
- Live direct send must remain off unless explicitly approved for a controlled test.

## Rollback Quick Reference

Frontend rollback:
- Use Vercel deployment history or alias the stable domain back to the last known-good deployment.
- Verify `/dashboard`, `/dashboard/tickets`, `/dashboard/settings/gmail`, and `/dashboard/settings/readiness` return 200.

Backend rollback:
- Use Cloud Run revisions to route traffic back to the last known-good `sift-api-staging` revision.
- Verify `/health/ready` and `/v1/status`.

Database rollback:
- Do not roll back schema casually.
- Back up or restore-test before risky migration recovery.
- Prefer forward fixes unless a migration is clearly unsafe.

Gmail disconnect fallback:
- If pilot sync is unsafe, pause Gmail sync from Settings -> Readiness or disconnect/reconnect the affected Gmail inbox.
- Operators can continue replying directly in Gmail while Sift is paused.

## Known Deferred Items

- Live direct Gmail send is off.
- Outlook and chat channels are deferred.
- Paid billing and customer charging are deferred.
- Full antivirus scanning beyond the current basic malware gate is deferred.
- Self-serve hard deletion is deferred; deletion request intake exists and pauses workspace activity.
- Public/commercial launch still requires external legal review.

## Pilot Completion Review

At the end of the pilot, record:

- Number of connected inboxes.
- Number of imported tickets.
- AI triage success/failure pattern.
- Draft approval-to-draft success pattern.
- Any degraded sync incidents and recovery time.
- Any confusing UI labels or manual workarounds.
- Whether paid Gemini quota, live direct send, Outlook/chat, or billing are justified by real usage.
