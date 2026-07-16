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

function formatDateTime(value?: string | null) {
  if (!value) return "Not scheduled";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not scheduled";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function operationLabel(jobType: string) {
  return jobType.replace(/_/g, " ");
}

function hasAiClassification(ticket: TicketListItem) {
  return ticket.triage_status === "triaged";
}

function NotClassifiedBadge() {
  return <span className="inline-flex rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-xs font-medium text-slate-600">Not classified</span>;
}

function formatConfidence(value?: number | null) {
  return typeof value === "number" ? `${Math.round(value)}%` : "No AI data";
}

function operationTone(job: OperationsJob) {
  if (job.retryable) return "border-amber-200 bg-amber-50 text-amber-900";
  if (job.error_code === "quota_exceeded") return "border-sky-200 bg-sky-50 text-sky-800";
  return "border-rose-200 bg-rose-50 text-rose-800";
}

function syncHealthLabel(syncHealth: SyncHealth | null) {
  if (!syncHealth) return "Not loaded";
  if (syncHealth.degraded_connections > 0 || syncHealth.disconnected_connections > 0 || syncHealth.stale_connections > 0) return "Needs attention";
  if (syncHealth.active_connections > 0) return "Healthy";
  return "No inboxes";
}

function syncHealthTone(syncHealth: SyncHealth | null) {
  const label = syncHealthLabel(syncHealth);
  if (label === "Healthy") return "border-emerald-200 bg-emerald-50 text-emerald-700";
  if (label === "Needs attention") return "border-amber-200 bg-amber-50 text-amber-800";
  return "border-slate-200 bg-slate-50 text-slate-600";
}
export function DashboardHome() {
  const supabase = createClient();
  const [metrics, setMetrics] = useState<MetricsOverview | null>(null);
  const [tickets, setTickets] = useState<TicketListItem[]>([]);
  const [suggestions, setSuggestions] = useState<ReplySuggestion[]>([]);
  const [operationFailures, setOperationFailures] = useState<OperationsJob[]>([]);
  const [syncHealth, setSyncHealth] = useState<SyncHealth | null>(null);
  const [operationsMessage, setOperationsMessage] = useState<string | null>(null);
  const [retryingJobId, setRetryingJobId] = useState<string | null>(null);
  const [dismissingJobId, setDismissingJobId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

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
        getOperationsFailures(context.accessToken, context.organizationId, 5),
        getSyncHealth(context.accessToken, context.organizationId),
      ]);
      setOperationFailures(failureData.jobs);
      setSyncHealth(healthData);
      setOperationsMessage(null);
    } catch (error) {
      setOperationFailures([]);
      setSyncHealth(null);
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
      setTickets(ticketData.slice(0, 5));

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
      <div className="rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-600">
        {message} <Link href="/dashboard/organizations" className="font-medium text-teal-700 underline">Go to organizations</Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <section className="grid gap-6 xl:grid-cols-[1.5fr_1fr]">
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-900/5 sm:p-6">
          <p className="font-mono text-xs uppercase tracking-wide text-slate-500">Today</p>
          <h2 className="mt-2 font-display text-3xl font-semibold tracking-tight text-slate-900">Good to see you. Your support queue is sorted by severity.</h2>
          <p className="mt-3 max-w-2xl text-slate-600">Critical and high-priority tickets rise first, AI suggestions stay human-approved, and Gmail drafts are created only after an agent approves the reply.</p>
          {metrics ? (
            <div className="mt-6 grid overflow-hidden rounded-lg border border-slate-200 bg-white sm:grid-cols-2 lg:grid-cols-4">
              <StatCard label="Open tickets" value={metrics.active_tickets} />
              <StatCard label="Pending approval" value={suggestions.length} />
              <StatCard label="Auto-triaged today" value={metrics.total_tickets} detail="Imported ticket total" />
              <StatCard label="Avg AI confidence" value={formatConfidence(metrics.average_confidence_score)} detail={metrics.average_confidence_score === null ? "No completed AI triage yet" : "Completed AI triage"} />
            </div>
          ) : null}
        </div>
        {metrics ? <TriageMeter metrics={metrics} /> : <div className="rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-500">Loading triage meter...</div>}
      </section>

      <OnboardingChecklist />

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-900/5 sm:p-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="font-mono text-xs uppercase tracking-wide text-slate-500">Pilot operations</p>
            <h2 className="mt-2 font-display text-lg font-semibold text-slate-900">Gmail workflow health</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">Watch for degraded sync, failed import or AI jobs, and safe retries before a pilot inbox gets busy.</p>
          </div>
          <span className={`inline-flex w-fit rounded-md border px-2 py-1 text-xs font-medium ${syncHealthTone(syncHealth)}`}>{syncHealthLabel(syncHealth)}</span>
        </div>

        {operationsMessage ? <p className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">{operationsMessage}</p> : null}

        <div className="mt-5 grid gap-3 sm:grid-cols-4">
          <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm">
            <p className="text-xs text-slate-500">Active inboxes</p>
            <p className="mt-1 text-xl font-semibold text-slate-900">{syncHealth?.active_connections ?? "-"}</p>
          </div>
          <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm">
            <p className="text-xs text-slate-500">Needs attention</p>
            <p className="mt-1 text-xl font-semibold text-slate-900">{(syncHealth?.degraded_connections ?? 0) + (syncHealth?.disconnected_connections ?? 0)}</p>
          </div>
          <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm">
            <p className="text-xs text-slate-500">Stale sync</p>
            <p className="mt-1 text-xl font-semibold text-slate-900">{syncHealth?.stale_connections ?? "-"}</p>
          </div>
          <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm">
            <p className="text-xs text-slate-500">Failed jobs</p>
            <p className="mt-1 text-xl font-semibold text-slate-900">{operationFailures.length}</p>
          </div>
        </div>

        {syncHealth?.connections.some((connection) => connection.degraded) ? (
          <div className="mt-4 grid gap-2 lg:grid-cols-2">
            {syncHealth.connections.filter((connection) => connection.degraded).slice(0, 4).map((connection) => (
              <div key={connection.connection_id} className="rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
                <p className="font-medium">{connection.gmail_email}</p>
                <p className="mt-1">Sync: {connection.sync_status ?? "unknown"} / Watch: {connection.watch_status ?? "unknown"}</p>
                {connection.sync_error_message ? <p className="mt-1 font-medium">{connection.sync_error_message}</p> : null}
              </div>
            ))}
          </div>
        ) : null}

        <div className="mt-5">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold text-slate-900">Recent failed jobs</h3>
            <Link href="/dashboard/settings/gmail" className="text-xs font-medium text-teal-700 underline">Open Gmail settings</Link>
          </div>
          {operationFailures.length === 0 ? <p className="mt-3 text-sm text-slate-500">No failed Gmail or AI jobs are waiting for action.</p> : null}
          <div className="mt-3 space-y-2">
            {operationFailures.map((job) => (
              <div key={job.id} className={`rounded-md border p-3 text-xs ${operationTone(job)}`}>
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="font-medium capitalize">{operationLabel(job.job_type)}</p>
                    <p className="mt-1">{job.error_message ?? job.error_code ?? "Job failed without a detailed message."}</p>
                    <p className="mt-1 opacity-80">Attempts {job.attempts}/{job.max_attempts}{job.next_retry_at ? ` / next retry ${formatDateTime(job.next_retry_at)}` : ""}</p>
                  </div>
                  <div className="flex flex-wrap gap-2 sm:justify-end">
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
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1fr_1fr]">
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm shadow-slate-900/5">
          <div className="border-b border-slate-200 px-5 py-4">
            <h2 className="font-display text-lg font-semibold">Needs approval</h2>
          </div>
          {suggestions.length === 0 ? (
            <p className="p-5 text-sm text-slate-500">Nothing waiting on you. Check back after the next import or triage run.</p>
          ) : (
            <div className="divide-y divide-slate-100">
              {suggestions.slice(0, 5).map((suggestion) => (
                <Link key={suggestion.id} href={`/dashboard/tickets/${suggestion.ticket_id}`} className="block px-5 py-4 text-sm hover:bg-slate-50">
                  <p className="font-medium text-slate-900">{suggestion.edited_body ?? suggestion.body}</p>
                  <p className="mt-1 font-mono text-xs text-slate-500">{suggestion.id}</p>
                </Link>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-xl border border-slate-200 bg-white shadow-sm shadow-slate-900/5">
          <div className="border-b border-slate-200 px-5 py-4">
            <h2 className="font-display text-lg font-semibold">Latest active tickets</h2>
          </div>
          {tickets.length === 0 ? (
            <p className="p-5 text-sm text-slate-500">Nothing waiting on you. Check back later.</p>
          ) : (
            <div className="divide-y divide-slate-100">
              {tickets.map((ticket) => (
                <Link key={ticket.id} href={`/dashboard/tickets/${ticket.id}`} className="grid gap-3 px-5 py-4 text-sm hover:bg-slate-50 sm:grid-cols-[1fr_auto]">
                  <div>
                    <p className="font-medium text-slate-900">{ticket.subject}</p>
                    <p className="mt-1 text-slate-500">{ticket.customer_name ?? ticket.customer_email}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {hasAiClassification(ticket) ? <UrgencyBadge priority={ticket.priority} /> : <NotClassifiedBadge />}
                    <StatusBadge status={ticket.status} />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

