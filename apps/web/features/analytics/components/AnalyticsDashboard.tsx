"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { getStoredOrganizationId } from "@/features/organizations/components/OrganizationManager";
import { getAdminAnalytics } from "@/features/tickets/api";
import type { AdminAnalytics } from "@/features/tickets/types";
import { createClient } from "@/lib/supabase/client";

function formatNumber(value: number | null | undefined, suffix = "") {
  if (value === null || value === undefined) return "N/A";
  return `${Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value)}${suffix}`;
}

function formatRate(value: number | null | undefined) {
  if (value === null || value === undefined) return "N/A";
  return `${Math.round(value * 100)}%`;
}

function labelize(value: string) {
  return value.replaceAll("_", " ");
}

function MetricTile({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="rounded-lg border border-white/50 bg-white/60 backdrop-blur-xl p-4 shadow-[0_18px_48px_rgba(72,60,96,0.075)]">
      <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">{label}</p>
      <p className="mt-2 font-display text-2xl font-semibold tracking-tight text-slate-950">{value}</p>
      {detail ? <p className="mt-1 text-sm text-slate-500">{detail}</p> : null}
    </div>
  );
}

function InlineMetric({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="border-b border-[#eee9f2] pb-3 last:border-b-0 last:pb-0">
      <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">{label}</p>
      <p className="mt-1 font-display text-xl font-semibold text-slate-900">{value}</p>
      {detail ? <p className="mt-1 text-sm text-slate-500">{detail}</p> : null}
    </div>
  );
}
function Breakdown({ title, values }: { title: string; values: Record<string, number> }) {
  const entries = Object.entries(values).sort((a, b) => b[1] - a[1]);
  const max = Math.max(...entries.map(([, count]) => count), 1);
  return (
    <section className="rounded-lg border border-white/50 bg-white/60 backdrop-blur-xl p-5 shadow-[0_18px_48px_rgba(72,60,96,0.075)]">
      <h2 className="font-display text-lg font-semibold text-slate-950">{title}</h2>
      <div className="mt-4 space-y-3">
        {entries.length === 0 ? <p className="text-sm text-slate-500">No data yet.</p> : null}
        {entries.map(([key, count]) => (
          <div key={key}>
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="capitalize text-slate-600">{labelize(key)}</span>
              <span className="font-mono text-slate-900">{count}</span>
            </div>
            <div className="mt-1 h-2 overflow-hidden rounded-full bg-slate-100">
              <div className="h-full rounded-full bg-brand-600" style={{ width: `${Math.max(8, (count / max) * 100)}%` }} />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export function AnalyticsDashboard() {
  const supabase = createClient();
  const [analytics, setAnalytics] = useState<AdminAnalytics | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      const organizationId = getStoredOrganizationId();
      const { data } = await supabase.auth.getSession();
      const accessToken = data.session?.access_token;
      if (!organizationId || !accessToken) {
        setMessage("Select an organization and sign in to view analytics.");
        setLoading(false);
        return;
      }
      try {
        setAnalytics(await getAdminAnalytics(organizationId, accessToken));
        setMessage(null);
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Failed to load analytics.");
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, [supabase]);

  const topAgents = useMemo(() => analytics?.support.agent_workload.slice(0, 6) ?? [], [analytics]);

  if (loading) return <div className="rounded-lg border border-white/50 bg-white/60 backdrop-blur-md p-6 text-sm text-slate-500">Loading analytics...</div>;
  if (message) return <div className="rounded-lg border border-[#ddd7e6] bg-white/50 p-6 text-sm text-[#746d80]">{message}</div>;
  if (!analytics) return null;

  return (
    <div className="space-y-6">
      <section className="rounded-lg border border-white/50 bg-white/60 backdrop-blur-xl p-5 shadow-[0_18px_48px_rgba(72,60,96,0.075)]">
        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">Owner view</p>
        <h2 className="mt-1 font-display text-2xl font-semibold tracking-tight text-slate-950">Support performance at a glance</h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">Use this page to spot workload pressure, SLA risk, AI quality, and Gmail sync reliability before they become pilot issues.</p>
      </section>
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricTile label="Ticket volume" value={formatNumber(analytics.support.ticket_volume)} detail="All workspace tickets" />
        <MetricTile label="SLA attainment" value={formatRate(analytics.support.sla_attainment_rate)} detail={`${analytics.support.reopened_tickets} reopened`} />
        <MetricTile label="AI triage completion" value={formatRate(analytics.ai_quality.triage_completion_rate)} detail={`${formatNumber(analytics.ai_quality.average_confidence_score)} avg confidence`} />
        <MetricTile label="Gmail sync success" value={formatNumber(analytics.gmail_sync.incremental_sync_success)} detail={`${analytics.gmail_sync.notifications_received} notifications`} />
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <MetricTile label="First review avg" value={formatNumber(analytics.support.first_review_time_avg_minutes, "m")} />
        <MetricTile label="Resolution avg" value={formatNumber(analytics.support.resolution_time_avg_minutes, "m")} />
        <MetricTile label="Approval wait avg" value={formatNumber(analytics.support.approval_wait_time_avg_minutes, "m")} />
      </section>

      <section className="grid gap-6 xl:grid-cols-3">
        <Breakdown title="Volume by category" values={analytics.support.by_category} />
        <Breakdown title="Volume by priority" values={analytics.support.by_priority} />
        <Breakdown title="AI confidence" values={analytics.ai_quality.confidence_distribution} />
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <div className="rounded-lg border border-white/50 bg-white/60 backdrop-blur-xl p-5 shadow-[0_18px_48px_rgba(72,60,96,0.075)]">
          <h2 className="font-display text-lg font-semibold text-slate-950">AI quality signals</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <InlineMetric label="Category corrections" value={formatNumber(analytics.ai_quality.agent_category_corrections)} />
            <InlineMetric label="Priority corrections" value={formatNumber(analytics.ai_quality.agent_priority_corrections)} />
            <InlineMetric label="Reply approval rate" value={formatRate(analytics.ai_quality.reply_approval_rate)} />
            <InlineMetric label="Provider failure rate" value={formatRate(analytics.ai_quality.provider_failure_rate)} detail={`${formatNumber(analytics.ai_quality.provider_latency_avg_ms, "ms")} avg latency`} />
          </div>
          <p className="mt-4 text-sm text-slate-500">Change level: <span className="font-medium capitalize text-slate-700">{analytics.ai_quality.average_change_level}</span></p>
        </div>

        <div className="rounded-lg border border-white/50 bg-white/60 backdrop-blur-xl p-5 shadow-[0_18px_48px_rgba(72,60,96,0.075)]">
          <div className="flex items-center justify-between gap-3">
            <h2 className="font-display text-lg font-semibold text-slate-950">Gmail sync health</h2>
            <Link href="/dashboard/settings" className="text-sm font-semibold text-[#655f73] hover:text-[#201b2d]">Open Gmail</Link>
          </div>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <InlineMetric label="Fallback recoveries" value={formatNumber(analytics.gmail_sync.fallback_recoveries)} />
            <InlineMetric label="Reconciliations" value={formatNumber(analytics.gmail_sync.reconciliation_count)} />
            <InlineMetric label="Duplicate skips" value={formatNumber(analytics.gmail_sync.duplicate_skip_count)} />
            <InlineMetric label="Watch renewals" value={formatNumber(analytics.gmail_sync.watch_renewal_success)} detail={`${formatNumber(analytics.gmail_sync.sync_latency_avg_ms, "ms")} avg sync`} />
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-white/50 bg-white/60 backdrop-blur-xl p-5 shadow-[0_18px_48px_rgba(72,60,96,0.075)]">
        <h2 className="font-display text-lg font-semibold text-slate-950">Agent workload</h2>
        <div className="mt-4 overflow-hidden rounded-lg border border-slate-200">
          {topAgents.length === 0 ? <p className="p-4 text-sm text-slate-500">No assigned tickets yet.</p> : null}
          {topAgents.map((agent) => (
            <div key={agent.user_id} className="grid gap-2 border-b border-[#eee9f2] px-4 py-3 text-sm last:border-b-0 sm:grid-cols-[1fr_auto_auto]">
              <span className="font-medium text-slate-900">{agent.user_id}</span>
              <span className="text-slate-500">{agent.open_tickets} open</span>
              <span className="font-mono text-slate-700">{agent.total_assigned_tickets} total</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}





