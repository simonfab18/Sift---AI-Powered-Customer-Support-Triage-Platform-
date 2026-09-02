"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { StatusBadge, UrgencyBadge } from "@/components/ui/Badges";
import { StatCard } from "@/components/ui/StatCard";
import { TriageMeter } from "@/components/ui/TriageMeter";
import { getStoredOrganizationId } from "@/features/organizations/components/OrganizationManager";
import { dismissOperationsJob, getOperationsFailures, getSyncHealth, retryOperationsJob } from "@/lib/api-client";
import { OnboardingChecklist } from "@/features/onboarding/components/OnboardingChecklist";
import { getMetricsOverview, getReplySuggestions, getTickets } from "@/features/tickets/api";
import type { MetricsOverview, ReplySuggestion, TicketListItem } from "@/features/tickets/types";
import type { OperationsJob, SyncHealth } from "@/lib/api-types";
import { createClient } from "@/lib/supabase/client";

type DashboardContext = {
  organizationId: string;
  accessToken: string;
};

const DASHBOARD_PREVIEW_LIMIT = 4;
const FAILED_JOBS_PREVIEW_LIMIT = 3;

function formatDateTime(value?: string | null) {
  if (!value) return "Not scheduled";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not scheduled";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function formatShortDateTime(value?: string | null) {
  if (!value) return "No date";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "No date";
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(date);
}

function formatStatusLabel(value?: string | null) {
  if (!value) return "Unknown";
  return value.replace(/_/g, " ");
}

function inboxLabel(ticket?: TicketListItem | null) {
  if (!ticket) return "Inbox unknown";
  return ticket.gmail_connection_shared_address || ticket.gmail_connection_display_name || ticket.gmail_connection_email || "Inbox unknown";
}

function suggestionBody(suggestion: ReplySuggestion) {
  return suggestion.edited_body ?? suggestion.body;
}

function operationLabel(jobType: string) {
  return jobType.replace(/_/g, " ");
}

function hasAiClassification(ticket: TicketListItem) {
  return ticket.triage_status === "triaged";
}

function NotClassifiedBadge() {
  return <span className="inline-flex rounded-md border border-slate-200 bg-white/30 px-2 py-1 text-xs font-medium text-slate-600">Not classified</span>;
}

function formatConfidence(value?: number | null) {
  return typeof value === "number" ? `${Math.round(value)}%` : "No AI data";
}

function operationTone(job: OperationsJob) {
  if (job.error_code === "quota_exceeded") return "border-[#ddd7e6] bg-white/50 text-[#655f73]";
  if (job.retryable) return "border-slate-200 bg-white/30 text-slate-700";
  return "border-[#d8d2e4] bg-white/50 text-[#6f6174]";
}

function operationSeverityLabel(job: OperationsJob) {
  if (job.error_code === "quota_exceeded") return "Paused by quota";
  if (job.retryable) return "Retryable";
  return "Manual review";
}

function operationNextStep(job: OperationsJob) {
  const message = `${job.error_code ?? ""} ${job.error_message ?? ""}`.toLowerCase();
  if (message.includes("quota") || message.includes("too_many_requests")) return "Wait for the Gemini quota window to reset, then retry. Dismiss only after a newer successful triage exists.";
  if (job.job_type.includes("gmail") || job.job_type.includes("sync") || job.job_type.includes("import")) return "Open Gmail settings, check inbox health, then retry the job or reconnect the inbox if sync stays degraded.";
  if (job.retryable) return "Retry is safe. If it fails again, check the error message and related resource before dismissing.";
  return "Review the related ticket or inbox before dismissing this failure.";
}

function connectionNextStep(connection: SyncHealth["connections"][number]) {
  if (connection.status !== "active") return "Reconnect or remove this inbox before relying on live sync.";
  if (connection.watch_status !== "active") return "Renew the Gmail watch from Gmail settings.";
  if (connection.sync_status !== "active") return "Queue an import from Gmail settings and review the latest sync error.";
  if (connection.consecutive_sync_failures > 0) return "Run import now once, then watch whether failures continue.";
  return "No action needed.";
}

function compactId(value?: string | null) {
  if (!value) return null;
  return value.length > 18 ? `${value.slice(0, 8)}...${value.slice(-6)}` : value;
}
function syncHealthLabel(syncHealth: SyncHealth | null) {
  if (!syncHealth) return "Not loaded";
  if (syncHealth.degraded_connections > 0 || syncHealth.disconnected_connections > 0 || syncHealth.stale_connections > 0) return "Needs attention";
  if (syncHealth.active_connections > 0) return "Healthy";
  return "No inboxes";
}

function syncHealthTone(syncHealth: SyncHealth | null) {
  const label = syncHealthLabel(syncHealth);
  if (label === "Healthy") return "border-slate-200 bg-white/30 text-slate-700";
  if (label === "Needs attention") return "border-[#ddd7e6] bg-white/50 text-[#746d80]";
  return "border-slate-200 bg-white/30 text-slate-600";
}
export function DashboardHome() {
  const supabase = createClient();
  const [metrics, setMetrics] = useState<MetricsOverview | null>(null);
  const [tickets, setTickets] = useState<TicketListItem[]>([]);
  const [suggestions, setSuggestions] = useState<ReplySuggestion[]>([]);
  const [operationFailures, setOperationFailures] = useState<OperationsJob[]>([]);
  const [syncHealth, setSyncHealth] = useState<SyncHealth | null>(null);
  const [operationsMessage, setOperationsMessage] = useState<string | null>(null);
  const [operationsLoadedAt, setOperationsLoadedAt] = useState<string | null>(null);
  const [retryingJobId, setRetryingJobId] = useState<string | null>(null);
  const [dismissingJobId, setDismissingJobId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const ticketsById = new Map(tickets.map((ticket) => [ticket.id, ticket]));
  const visibleSuggestions = suggestions.slice(0, DASHBOARD_PREVIEW_LIMIT);
  const visibleTickets = tickets.slice(0, DASHBOARD_PREVIEW_LIMIT);
  const visibleFailedJobs = operationFailures.slice(0, FAILED_JOBS_PREVIEW_LIMIT);

  async function getContext(): Promise<DashboardContext | null> {
    const organizationId = getStoredOrganizationId();
    const { data } = await supabase.auth.getSession();
    const accessToken = data.session?.access_token;
    if (!organizationId || !accessToken) return null;
    return { organizationId, accessToken };
  }

  async function loadOperations(context: DashboardContext) {
    try {
      const [failureData, healthData] = await Promise.all([
        getOperationsFailures(context.accessToken, context.organizationId, 8),
        getSyncHealth(context.accessToken, context.organizationId),
      ]);
      setOperationFailures(failureData.jobs);
      setSyncHealth(healthData);
      setOperationsLoadedAt(new Date().toISOString());
      setOperationsMessage(null);
    } catch (error) {
      setOperationFailures([]);
      setSyncHealth(null);
      setOperationsLoadedAt(null);
      setOperationsMessage(error instanceof Error ? error.message : "Operations visibility is available to owners and admins.");
    }
  }

  async function loadDashboard() {
    const context = await getContext();
    if (!context) {
      setMessage("Select an organization and sign in to load your dashboard.");
      return;
    }

    try {
      const [metricData, ticketData] = await Promise.all([
        getMetricsOverview(context.organizationId, context.accessToken),
        getTickets(context.organizationId, context.accessToken),
      ]);
      setMetrics(metricData);
      setTickets(ticketData);

      const pendingSuggestions = await Promise.all(
        ticketData.slice(0, 8).map(async (ticket) => {
          try {
            return await getReplySuggestions(context.organizationId, ticket.id, context.accessToken);
          } catch {
            return [];
          }
        }),
      );
      setSuggestions(pendingSuggestions.flat().filter((suggestion) => suggestion.status === "suggested" || suggestion.status === "edited"));
      await loadOperations(context);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to load dashboard.");
    }
  }

  useEffect(() => {
    void loadDashboard();
  }, [supabase]);

  async function handleRefreshOperations() {
    const context = await getContext();
    if (!context) {
      setOperationsMessage("Select an organization and sign in before refreshing operations.");
      return;
    }
    await loadOperations(context);
  }

  async function handleRetryJob(job: OperationsJob) {
    const context = await getContext();
    if (!context) {
      setOperationsMessage("Select an organization and sign in before retrying jobs.");
      return;
    }

    setRetryingJobId(job.id);
    setOperationsMessage(null);
    try {
      const result = await retryOperationsJob(context.accessToken, context.organizationId, job.id);
      setOperationsMessage(`Retry queued for ${operationLabel(result.retry_job.job_type)}.`);
      await loadOperations(context);
    } catch (error) {
      setOperationsMessage(error instanceof Error ? error.message : "Failed to retry job.");
    } finally {
      setRetryingJobId(null);
    }
  }
  async function handleDismissJob(job: OperationsJob) {
    const context = await getContext();
    if (!context) {
      setOperationsMessage("Select an organization and sign in before dismissing jobs.");
      return;
    }

    setDismissingJobId(job.id);
    setOperationsMessage(null);
    try {
      await dismissOperationsJob(context.accessToken, context.organizationId, job.id);
      setOperationsMessage(`${operationLabel(job.job_type)} dismissed from the failed jobs list.`);
      await loadOperations(context);
    } catch (error) {
      setOperationsMessage(error instanceof Error ? error.message : "Failed to dismiss job.");
    } finally {
      setDismissingJobId(null);
    }
  }

  if (message) {
    return (
      <div className="rounded-lg border border-white/50 bg-white/60 backdrop-blur-md p-6 text-sm text-slate-600">
        {message} <Link href="/dashboard/organizations" className="font-semibold text-[#655f73] underline">Go to organizations</Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <section className="grid gap-6 xl:grid-cols-[1.5fr_0.8fr] xl:items-start">
        <div className="rounded-lg border border-white/50 bg-white/60 backdrop-blur-xl p-5 shadow-[0_18px_48px_rgba(72,60,96,0.075)] sm:p-6">
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">Today</p>
          <h2 className="mt-2 font-display text-3xl font-semibold tracking-tight text-slate-900">Your support queue, in order.</h2>
          <p className="mt-3 max-w-2xl text-slate-600">Critical work rises first, owners see operational risk, and agents keep control before any Gmail draft is created.</p>
          {metrics ? (
            <div className="mt-6 grid overflow-hidden rounded-lg border border-white/50 bg-white/60 backdrop-blur-md sm:grid-cols-2 lg:grid-cols-4">
              <StatCard label="Open tickets" value={metrics.active_tickets} accent="brand" />
              <StatCard label="Needs approval" value={suggestions.length} accent="brand" />
              <StatCard label="Auto-triaged" value={metrics.total_tickets} detail="Imported ticket total" accent="blue" />
              <StatCard label="Avg AI confidence" value={formatConfidence(metrics.average_confidence_score)} detail={metrics.average_confidence_score === null ? "No completed AI triage yet" : "Completed AI triage"} accent="slate" />
            </div>
          ) : null}
        </div>
        {metrics ? <TriageMeter metrics={metrics} /> : <div className="rounded-lg border border-white/50 bg-white/60 p-6 text-sm text-slate-500 shadow-[0_18px_48px_rgba(72,60,96,0.075)] backdrop-blur-xl">Loading triage meter...</div>}
      </section>

      <OnboardingChecklist />

      <section className="rounded-lg border border-white/50 bg-white/60 backdrop-blur-xl p-5 shadow-[0_18px_48px_rgba(72,60,96,0.075)] sm:p-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">Pilot operations</p>
            <h2 className="mt-2 font-display text-lg font-semibold text-slate-900">Gmail workflow health</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">Watch for degraded sync, failed import or AI jobs, and safe retries before a pilot inbox gets busy.</p>
            {operationsLoadedAt ? <p className="mt-1 text-xs text-slate-500">Last checked {formatDateTime(operationsLoadedAt)}</p> : null}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" onClick={() => void handleRefreshOperations()} className="rounded-md border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-800 shadow-sm hover:bg-white/30">Refresh ops</button>
            <span className={`inline-flex w-fit rounded-md border px-2 py-1 text-xs font-medium ${syncHealthTone(syncHealth)}`}>{syncHealthLabel(syncHealth)}</span>
          </div>
        </div>

        {operationsMessage ? <p className="mt-4 rounded-md border border-slate-200 bg-white/30 p-3 text-sm text-slate-600">{operationsMessage}</p> : null}

        <div className="mt-5 grid gap-3 sm:grid-cols-4">
          <div className="rounded-md border border-slate-200 bg-white/30 p-3 text-sm">
            <p className="text-xs text-slate-500">Active inboxes</p>
            <p className="mt-1 text-xl font-semibold text-slate-900">{syncHealth?.active_connections ?? "-"}</p>
          </div>
          <div className="rounded-md border border-slate-200 bg-white/30 p-3 text-sm">
            <p className="text-xs text-slate-500">Needs attention</p>
            <p className="mt-1 text-xl font-semibold text-slate-900">{(syncHealth?.degraded_connections ?? 0) + (syncHealth?.disconnected_connections ?? 0)}</p>
          </div>
          <div className="rounded-md border border-slate-200 bg-white/30 p-3 text-sm">
            <p className="text-xs text-slate-500">Stale sync</p>
            <p className="mt-1 text-xl font-semibold text-slate-900">{syncHealth?.stale_connections ?? "-"}</p>
          </div>
          <div className="rounded-md border border-slate-200 bg-white/30 p-3 text-sm">
            <p className="text-xs text-slate-500">Failed jobs</p>
            <p className="mt-1 text-xl font-semibold text-slate-900">{operationFailures.length}</p>
          </div>
        </div>

        {syncHealth?.connections.some((connection) => connection.degraded) ? (
          <div className="mt-4 grid gap-2 lg:grid-cols-2">
            {syncHealth.connections.filter((connection) => connection.degraded).slice(0, 4).map((connection) => (
              <div key={connection.connection_id} className="rounded-md border border-[#d8d2e4] bg-white/50 p-3 text-xs text-[#6f6174]">
                <p className="font-medium">{connection.gmail_email}</p>
                <p className="mt-1">Sync: {connection.sync_status ?? "unknown"} / Watch: {connection.watch_status ?? "unknown"}</p>
                <p className="mt-1">Failures: {connection.consecutive_sync_failures} / Last success: {formatDateTime(connection.last_successful_sync_at)}</p>
                {connection.sync_error_message ? <p className="mt-1 font-medium">{connection.sync_error_message}</p> : null}
                <p className="mt-2 rounded bg-white/70 p-2 font-medium">Next: {connectionNextStep(connection)}</p>
              </div>
            ))}
          </div>
        ) : null}

        <div className="mt-5">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold text-slate-900">Recent failed jobs</h3>
            <Link href="/dashboard/settings/gmail" className="text-xs font-semibold text-[#655f73] underline">Open Gmail settings</Link>
          </div>
          {operationFailures.length === 0 ? <p className="mt-3 text-sm text-slate-500">No failed Gmail or AI jobs are waiting for action.</p> : null}
          <div className="mt-3 max-h-[420px] space-y-2 overflow-y-auto pr-1">
            {visibleFailedJobs.map((job) => (
              <div key={job.id} className={`rounded-md border p-3 text-xs ${operationTone(job)}`}>
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="font-medium capitalize">{operationLabel(job.job_type)}</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <span className="rounded bg-white/70 px-2 py-1 font-medium">{operationSeverityLabel(job)}</span>
                      {job.error_code ? <span className="rounded bg-white/70 px-2 py-1 font-mono">{job.error_code}</span> : null}
                      {job.alert_owner ? <span className="rounded bg-white/70 px-2 py-1">Owner: {job.alert_owner}</span> : null}
                    </div>
                    <p className="mt-2">{job.error_message ?? job.error_code ?? "Job failed without a detailed message."}</p>
                    <p className="mt-1 opacity-80">Attempts {job.attempts}/{job.max_attempts}{job.next_retry_at ? ` / next retry ${formatDateTime(job.next_retry_at)}` : ""}</p>
                    <p className="mt-2 rounded bg-white/70 p-2 font-medium">Next: {operationNextStep(job)}</p>
                    <div className="mt-2 flex flex-wrap gap-2 opacity-80">
                      {job.related_resource_type && job.related_resource_id ? <span>Related {job.related_resource_type}: <span className="font-mono">{compactId(job.related_resource_id)}</span></span> : null}
                      {job.correlation_id ? <span>Correlation: <span className="font-mono">{compactId(job.correlation_id)}</span></span> : null}
                      <span>Created {formatDateTime(job.created_at)}</span>
                      {job.duration_ms !== null ? <span>Duration {job.duration_ms} ms</span> : null}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2 sm:justify-end">
                    {job.runbook_url ? (
                      <a href={job.runbook_url} target="_blank" rel="noreferrer" className="rounded-md bg-white/80 px-3 py-2 font-medium text-slate-700 shadow-sm ring-1 ring-inset ring-slate-300">
                        Runbook
                      </a>
                    ) : null}
                    {job.retryable ? (
                      <button type="button" onClick={() => void handleRetryJob(job)} disabled={retryingJobId === job.id || dismissingJobId === job.id} className="rounded-md bg-white px-3 py-2 font-medium text-slate-900 shadow-sm ring-1 ring-inset ring-slate-300 disabled:opacity-50">
                        {retryingJobId === job.id ? "Retrying..." : "Retry"}
                      </button>
                    ) : (
                      <span className="rounded-md bg-white/70 px-2 py-1 font-medium">Manual review</span>
                    )}
                    <button type="button" onClick={() => void handleDismissJob(job)} disabled={retryingJobId === job.id || dismissingJobId === job.id} className="rounded-md bg-white/80 px-3 py-2 font-medium text-slate-700 shadow-sm ring-1 ring-inset ring-slate-300 disabled:opacity-50">
                      {dismissingJobId === job.id ? "Dismissing..." : "Dismiss"}
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
          {operationFailures.length > FAILED_JOBS_PREVIEW_LIMIT ? (
            <p className="mt-3 text-xs text-slate-500">
              Showing {FAILED_JOBS_PREVIEW_LIMIT} of {operationFailures.length} failed jobs. Open Gmail settings for the full operations view.
            </p>
          ) : null}
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1fr_1fr]">
        <div className="rounded-lg border border-white/50 bg-white/60 backdrop-blur-xl shadow-[0_18px_48px_rgba(72,60,96,0.075)]">
          <div className="flex items-start justify-between gap-3 border-b border-slate-200 px-5 py-4">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">Human review</p>
              <h2 className="mt-1 font-display text-lg font-semibold text-slate-950">Needs approval</h2>
              <p className="mt-1 text-sm text-slate-500">AI reply drafts waiting for a person to review.</p>
            </div>
            {suggestions.length > 0 ? <span className="rounded-full border border-slate-200 bg-white/60 px-3 py-1 text-xs font-medium text-slate-600">{suggestions.length} waiting</span> : null}
          </div>
          {suggestions.length === 0 ? (
            <p className="p-5 text-sm text-slate-500">Nothing waiting on you. Check back after the next import or triage run.</p>
          ) : (
            <div className="max-h-[520px] divide-y divide-[#eee9f2] overflow-y-auto">
              {visibleSuggestions.map((suggestion) => {
                const ticket = ticketsById.get(suggestion.ticket_id);
                return (
                  <Link key={suggestion.id} href={`/dashboard/tickets/${suggestion.ticket_id}`} className="block px-5 py-4 text-sm transition hover:bg-white/35">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                      <div className="min-w-0">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">Ticket to review</p>
                        <p className="mt-1 line-clamp-2 font-display text-base font-semibold text-slate-950">{ticket?.subject ?? `Ticket ${compactId(suggestion.ticket_id)}`}</p>
                        <p className="mt-1 text-xs text-slate-500">
                          {ticket ? `${ticket.customer_name ?? ticket.customer_email} / ${inboxLabel(ticket)} / ${formatShortDateTime(ticket.received_at)}` : "Ticket context is still loading."}
                        </p>
                      </div>
                      <div className="flex shrink-0 flex-wrap gap-2 lg:justify-end">
                        {ticket ? (hasAiClassification(ticket) ? <UrgencyBadge priority={ticket.priority} /> : <NotClassifiedBadge />) : null}
                        {ticket ? <StatusBadge status={ticket.status} /> : null}
                        <span className="rounded-md border border-slate-200 bg-white/60 px-2 py-1 text-xs font-medium text-[#655f73]">v{suggestion.reply_version}</span>
                      </div>
                    </div>
                    <div className="mt-3 rounded-lg border border-white/60 bg-white/45 p-3 text-slate-700">
                      <p className="line-clamp-3 leading-6">{suggestionBody(suggestion)}</p>
                    </div>
                    <p className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                      <span className="rounded bg-slate-100 px-2 py-1 font-mono">Ticket {compactId(suggestion.ticket_id)}</span>
                      {ticket?.category ? <span className="rounded bg-white/50 px-2 py-1 capitalize">{formatStatusLabel(ticket.category)}</span> : null}
                      <span className="font-semibold text-[#655f73]">Review reply -&gt;</span>
                    </p>
                  </Link>
                );
              })}
            </div>
          )}
          {suggestions.length > DASHBOARD_PREVIEW_LIMIT ? (
            <div className="border-t border-slate-200 px-5 py-3">
              <Link href="/dashboard/tickets?status=awaiting_approval" className="text-sm font-semibold text-[#655f73] underline">
                View all {suggestions.length} tickets waiting for approval
              </Link>
            </div>
          ) : null}
        </div>

        <div className="rounded-lg border border-white/50 bg-white/60 backdrop-blur-xl shadow-[0_18px_48px_rgba(72,60,96,0.075)]">
          <div className="flex items-start justify-between gap-3 border-b border-slate-200 px-5 py-4">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">Queue snapshot</p>
              <h2 className="mt-1 font-display text-lg font-semibold text-slate-950">Latest active tickets</h2>
              <p className="mt-1 text-sm text-slate-500">A short preview so the dashboard stays scannable.</p>
            </div>
            {tickets.length > 0 ? <span className="rounded-full border border-slate-200 bg-white/60 px-3 py-1 text-xs font-medium text-slate-600">{tickets.length} loaded</span> : null}
          </div>
          {tickets.length === 0 ? (
            <p className="p-5 text-sm text-slate-500">Nothing waiting on you. Check back later.</p>
          ) : (
            <div className="max-h-[520px] divide-y divide-[#eee9f2] overflow-y-auto">
              {visibleTickets.map((ticket) => (
                <Link key={ticket.id} href={`/dashboard/tickets/${ticket.id}`} className="grid gap-3 px-5 py-4 text-sm transition hover:bg-white/35 sm:grid-cols-[1fr_auto]">
                  <div>
                    <p className="line-clamp-2 font-display font-semibold text-slate-950">{ticket.subject}</p>
                    <p className="mt-1 text-slate-500">{ticket.customer_name ?? ticket.customer_email}</p>
                    <p className="mt-1 text-xs text-slate-500">{inboxLabel(ticket)} / {formatShortDateTime(ticket.received_at)}</p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 sm:justify-end">
                    {hasAiClassification(ticket) ? <UrgencyBadge priority={ticket.priority} /> : <NotClassifiedBadge />}
                    <span className="rounded-md border border-slate-200 bg-white/55 px-2 py-1 text-xs capitalize text-slate-600">{formatStatusLabel(ticket.category)}</span>
                    <StatusBadge status={ticket.status} />
                  </div>
                </Link>
              ))}
            </div>
          )}
          {tickets.length > DASHBOARD_PREVIEW_LIMIT ? (
            <div className="border-t border-slate-200 px-5 py-3">
              <Link href="/dashboard/tickets" className="text-sm font-semibold text-[#655f73] underline">
                Open full triage queue
              </Link>
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );
}
