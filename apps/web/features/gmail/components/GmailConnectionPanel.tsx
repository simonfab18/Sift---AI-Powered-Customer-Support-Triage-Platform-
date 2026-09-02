"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { getStoredOrganizationId } from "@/features/organizations/components/OrganizationManager";
import {
  getGmailConnections,
  getGmailImportRules,
  getRecentImports,
  queueGmailSync,
  startGmailOAuth,
  updateGmailConnection,
  updateGmailImportRule,
} from "@/lib/api-client";
import type { GmailConnection, JobRun, MailImportRule } from "@/lib/api-types";
import { createClient } from "@/lib/supabase/client";

const inboxTypeOptions = [
  { value: "individual", label: "Individual inbox" },
  { value: "google_group", label: "Google Group" },
  { value: "shared_mailbox", label: "Shared mailbox" },
];

const routingOptions = [
  { value: "shared_queue", label: "Shared queue" },
  { value: "priority_queue", label: "Priority queue" },
  { value: "specialist_queue", label: "Specialist queue" },
];

function inboxName(connection: GmailConnection) {
  return connection.display_name?.trim() || connection.gmail_email;
}

function isValidEmailAddress(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}

function formatDateTime(value?: string | null) {
  if (!value) return "Not recorded";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not recorded";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function formatJobTime(job: JobRun) {
  return formatDateTime(job.finished_at ?? job.started_at ?? job.created_at);
}
function jobConnectionId(job: JobRun) {
  return typeof job.job_metadata.gmail_connection_id === "string" ? job.job_metadata.gmail_connection_id : null;
}

function formatDuration(ms?: number | null) {
  if (typeof ms === "number" && Number.isFinite(ms)) {
    if (ms < 1000) return `${ms} ms`;
    const seconds = Math.round(ms / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return remainingSeconds ? `${minutes}m ${remainingSeconds}s` : `${minutes}m`;
  }
  return null;
}

function elapsedSince(value?: string | null) {
  if (!value) return null;
  const started = new Date(value).getTime();
  if (Number.isNaN(started)) return null;
  const seconds = Math.max(0, Math.round((Date.now() - started) / 1000));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return remainingSeconds ? `${minutes}m ${remainingSeconds}s` : `${minutes}m`;
}

function isLongRunningImport(job?: JobRun) {
  if (!job || !["queued", "running"].includes(job.status)) return false;
  const started = new Date(job.started_at ?? job.created_at).getTime();
  if (Number.isNaN(started)) return false;
  return Date.now() - started > 5 * 60 * 1000;
}

function importStatusTone(status: string) {
  if (status === "succeeded") return "border-slate-200 bg-white/30 text-slate-700";
  if (status === "failed") return "border-[#d8d2e4] bg-white/50 text-[#6f6174]";
  if (status === "queued" || status === "running") return "border-[#ddd7e6] bg-white/50 text-[#655f73]";
  return "border-slate-200 bg-white/30 text-slate-600";
}

function importCounts(job?: JobRun) {
  if (!job) return "No completed import yet";
  const imported = String(job.job_metadata.imported_count ?? 0);
  const skipped = String(job.job_metadata.skipped_count ?? 0);
  return `${imported} imported, ${skipped} skipped`;
}

function importRuntime(job: JobRun) {
  const duration = formatDuration(job.duration_ms);
  if (duration) return duration;
  if (job.status === "running") return elapsedSince(job.started_at ?? job.created_at);
  if (job.status === "queued") return elapsedSince(job.created_at);
  return null;
}

function isWatchExpiringSoon(value?: string | null) {
  if (!value) return false;
  const expiresAt = new Date(value).getTime();
  if (Number.isNaN(expiresAt)) return false;
  const twoDaysMs = 2 * 24 * 60 * 60 * 1000;
  return expiresAt - Date.now() <= twoDaysMs;
}


function syncTroubleshootingSummary(connection: GmailConnection) {
  if (connection.status === "reauthorization_required" || connection.sync_status === "reauthorization_required" || connection.watch_status === "reauthorization_required") {
    return "Reconnect Gmail to refresh permission and token access.";
  }
  if (connection.watch_status === "error" || connection.watch_status === "degraded") {
    return "Run Import now, then reconnect Gmail if watch stays degraded. If both fail, check Pub/Sub push and Scheduler.";
  }
  if (connection.sync_status === "degraded") {
    return "Run Import now after any active import finishes. If it fails again, review the latest import error and reconnect Gmail.";
  }
  if (connection.watch_expires_at && isWatchExpiringSoon(connection.watch_expires_at)) {
    return "Watch renewal is due soon. Scheduler should renew it automatically; run watch renewal manually if expiry gets close.";
  }
  if (!connection.last_notification_at) {
    return "No Gmail push notification has arrived yet. Send a test email or run Import now to confirm the inbox path.";
  }
  return "No action needed. Push watch and sync are active.";
}

function inputClassName(hasError = false) {
  return `mt-1 w-full rounded-md border px-3 py-2 text-sm ${hasError ? "border-[#bcb4cb] outline-[#d8d2e4]" : "border-slate-300"}`;
}
function connectionHealth(connection: GmailConnection, activeImport?: JobRun) {
  if (activeImport || connection.sync_status === "syncing") {
    return {
      label: "Syncing",
      className: "border-[#ddd7e6] bg-white/50 text-[#655f73]",
      message: "Import is running. New messages may appear after this finishes.",
    };
  }

  if (connection.status === "reauthorization_required" || connection.sync_status === "reauthorization_required" || connection.watch_status === "reauthorization_required") {
    return {
      label: "Reconnect needed",
      className: "border-slate-300 bg-slate-100 text-slate-700",
      message: connection.reauthorization_reason ?? "Google needs this inbox to be connected again.",
    };
  }

  if (connection.sync_status === "degraded" || connection.watch_status === "degraded" || connection.watch_status === "error") {
    return {
      label: "Needs attention",
      className: "border-[#d8d2e4] bg-white/50 text-[#6f6174]",
      message: connection.sync_error_message ?? connection.watch_error ?? "Sync is degraded. Try import now, then reconnect Gmail if it stays degraded.",
    };
  }

  if (connection.watch_expires_at && isWatchExpiringSoon(connection.watch_expires_at)) {
    return {
      label: "Watch renewal soon",
      className: "border-slate-300 bg-slate-100 text-slate-700",
      message: "Gmail watch is close to renewal. Scheduler should refresh it before expiry.",
    };
  }

  if (connection.status === "active" && connection.sync_status === "active" && connection.watch_status === "active") {
    return {
      label: "Active",
      className: "border-white/50 bg-white/60 backdrop-blur-md text-slate-700",
      message: "Gmail sync and push watch are active.",
    };
  }

  return {
    label: "Setup in progress",
    className: "border-slate-200 bg-white/30 text-slate-700",
    message: "This inbox is connected, but sync status is still settling.",
  };
}

export function GmailConnectionPanel() {
  const supabase = createClient();
  const [connections, setConnections] = useState<GmailConnection[]>([]);
  const [rules, setRules] = useState<MailImportRule[]>([]);
  const [imports, setImports] = useState<JobRun[]>([]);
  const [organizationId, setOrganizationId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [syncingConnectionId, setSyncingConnectionId] = useState<string | null>(null);
  const [queueingConnectionId, setQueueingConnectionId] = useState<string | null>(null);
  const [savingConnectionId, setSavingConnectionId] = useState<string | null>(null);
  const [draftLabels, setDraftLabels] = useState<Record<string, string>>({});
  const [draftConnectionMeta, setDraftConnectionMeta] = useState<Record<string, { inbox_type: string; shared_address: string; channel_notes: string }>>({});
  const [draftRules, setDraftRules] = useState<Record<string, Partial<MailImportRule>>>({});

  async function getAccessToken() {
    const { data } = await supabase.auth.getSession();
    return data.session?.access_token ?? null;
  }

  async function loadConnections() {
    const gmailConnected = new URLSearchParams(window.location.search).get("gmail") === "connected";
    setLoading(true);
    setMessage(gmailConnected ? "Gmail connected successfully." : null);
    const selectedOrganizationId = getStoredOrganizationId();
    setOrganizationId(selectedOrganizationId);

    if (!selectedOrganizationId) {
      setMessage("Select or create an organization first.");
      setLoading(false);
      return;
    }

    const accessToken = await getAccessToken();
    if (!accessToken) {
      setMessage("Sign in before connecting Gmail.");
      setLoading(false);
      return;
    }

    try {
      const [connectionData, ruleData, importData] = await Promise.all([
        getGmailConnections(accessToken, selectedOrganizationId),
        getGmailImportRules(accessToken, selectedOrganizationId),
        getRecentImports(accessToken, selectedOrganizationId),
      ]);
      setConnections(connectionData);
      setRules(ruleData);
      setImports(importData);
      setDraftLabels(Object.fromEntries(connectionData.map((connection) => [connection.id, inboxName(connection)])));
      setDraftConnectionMeta(Object.fromEntries(connectionData.map((connection) => [connection.id, { inbox_type: connection.inbox_type ?? "individual", shared_address: connection.shared_address ?? "", channel_notes: connection.channel_notes ?? "" }])));
      setDraftRules(Object.fromEntries(ruleData.map((rule) => [rule.gmail_connection_id, { ...rule }])));
      if (gmailConnected) setMessage("Gmail connected successfully.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to load Gmail inboxes.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadConnections();
  }, []);

  const rulesByConnectionId = useMemo(() => new Map(rules.map((rule) => [rule.gmail_connection_id, rule])), [rules]);
  const activeImportByConnectionId = useMemo(() => {
    const active = new Map<string, JobRun>();
    for (const job of imports) {
      const connectionId = jobConnectionId(job);
      if (!connectionId || !["queued", "running"].includes(job.status)) continue;
      if (!active.has(connectionId)) active.set(connectionId, job);
    }
    return active;
  }, [imports]);
  const latestImportByConnectionId = useMemo(() => {
    const latest = new Map<string, JobRun>();
    for (const job of imports) {
      const connectionId = jobConnectionId(job);
      if (!connectionId) continue;
      if (!latest.has(connectionId)) latest.set(connectionId, job);
    }
    return latest;
  }, [imports]);
  const hasActiveImports = activeImportByConnectionId.size > 0;

  useEffect(() => {
    if (!hasActiveImports) return undefined;
    const intervalId = window.setInterval(() => {
      void loadConnections();
    }, 5000);
    return () => window.clearInterval(intervalId);
  }, [hasActiveImports]);

  async function handleConnect() {
    if (!organizationId) {
      setMessage("Select or create an organization first.");
      return;
    }

    const accessToken = await getAccessToken();
    if (!accessToken) {
      setMessage("Sign in before connecting Gmail.");
      return;
    }

    setConnecting(true);
    setMessage(null);

    try {
      const { auth_url } = await startGmailOAuth(accessToken, organizationId);
      window.location.href = auth_url;
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to start Gmail OAuth.");
      setConnecting(false);
    }
  }

  async function handleSaveInbox(connection: GmailConnection) {
    if (!organizationId) return;
    const accessToken = await getAccessToken();
    if (!accessToken) {
      setMessage("Sign in before updating Gmail inboxes.");
      return;
    }

    const rule = rulesByConnectionId.get(connection.id);
    setSavingConnectionId(connection.id);
    setMessage(null);
    try {
      const connectionMeta = draftConnectionMeta[connection.id] ?? { inbox_type: connection.inbox_type ?? "individual", shared_address: connection.shared_address ?? "", channel_notes: connection.channel_notes ?? "" };
      if (connectionMeta.inbox_type !== "individual" && !connectionMeta.shared_address.trim()) {
        setMessage("Group or shared mailbox sources need an email address, like support@example.com.");
        return;
      }
      if (connectionMeta.inbox_type !== "individual" && !isValidEmailAddress(connectionMeta.shared_address)) {
        setMessage("Enter a valid email address for the Google Group or shared mailbox.");
        return;
      }
      const updatedConnection = await updateGmailConnection(accessToken, organizationId, connection.id, {
        display_name: draftLabels[connection.id]?.trim() || null,
        inbox_type: connectionMeta.inbox_type,
        shared_address: connectionMeta.inbox_type === "individual" ? null : connectionMeta.shared_address.trim().toLowerCase() || null,
        channel_notes: connectionMeta.channel_notes.trim() || null,
      });
      setConnections((current) => current.map((item) => (item.id === updatedConnection.id ? updatedConnection : item)));
      setDraftConnectionMeta((current) => ({
        ...current,
        [updatedConnection.id]: {
          inbox_type: updatedConnection.inbox_type ?? "individual",
          shared_address: updatedConnection.shared_address ?? "",
          channel_notes: updatedConnection.channel_notes ?? "",
        },
      }));
      if (rule) {
        const draftRule = draftRules[connection.id] ?? {};
        await updateGmailImportRule(accessToken, organizationId, rule.id, {
          support_label_id: draftRule.support_label_id ?? null,
          processed_label_id: draftRule.processed_label_id ?? null,
          spam_label_id: draftRule.spam_label_id ?? null,
          import_unread_only: Boolean(draftRule.import_unread_only),
          routing_direction: draftRule.routing_direction ?? "shared_queue",
          is_active: draftRule.is_active ?? true,
        });
      }
      setMessage("Inbox settings saved.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to save inbox settings.");
    } finally {
      setSavingConnectionId(null);
    }
  }

  async function handleSync(connectionId: string) {
    if (activeImportByConnectionId.has(connectionId)) {
      setMessage("An import is already running for this inbox.");
      return;
    }
    if (!organizationId) {
      setMessage("Select or create an organization first.");
      return;
    }

    const accessToken = await getAccessToken();
    if (!accessToken) {
      setMessage("Sign in before importing Gmail.");
      return;
    }

    setSyncingConnectionId(connectionId);
    setMessage(null);

    try {
      const job = await queueGmailSync(accessToken, organizationId, connectionId);
      setImports((current) => [job, ...current.filter((item) => item.id !== job.id)]);
      setMessage(job.status === "queued" || job.status === "running" ? "Import is running for this inbox. Buttons stay locked until it finishes." : `Import ${job.status}.`);
      await loadConnections();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to start Gmail import.");
    } finally {
      setSyncingConnectionId(null);
    }
  }

  async function handleQueueSync(connectionId: string) {
    if (!organizationId) {
      setMessage("Select or create an organization first.");
      return;
    }

    const accessToken = await getAccessToken();
    if (!accessToken) {
      setMessage("Sign in before queueing Gmail import.");
      return;
    }

    if (activeImportByConnectionId.has(connectionId)) {
      setMessage("An import is already running for this inbox.");
      return;
    }

    setQueueingConnectionId(connectionId);
    setMessage(null);

    try {
      const job = await queueGmailSync(accessToken, organizationId, connectionId);
      setImports((current) => [job, ...current.filter((item) => item.id !== job.id)]);
      setMessage(`Queued import job ${job.id}. Buttons stay locked until it finishes.`);
      await loadConnections();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to queue Gmail import.");
    } finally {
      setQueueingConnectionId(null);
    }
  }

  return (
    <div className="rounded-lg border border-white/50 bg-white/60 backdrop-blur-xl p-5 shadow-[0_18px_48px_rgba(72,60,96,0.075)]">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">Integrations</p>
          <h2 className="mt-1 font-display text-xl font-semibold text-slate-950">Gmail inboxes</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Connect multiple Gmail inboxes, label each source, and keep import rules separate per inbox.
          </p>
        </div>
        <button type="button" onClick={handleConnect} disabled={connecting || !organizationId} className="rounded-md border border-slate-950 bg-slate-950 px-4 py-2 text-sm font-semibold text-white shadow-sm shadow-slate-900/10 disabled:border-slate-300 disabled:bg-slate-300">
          {connecting ? "Connecting..." : "Connect Gmail"}
        </button>
      </div>

      {message ? (
        <div className="mt-5 rounded-md border border-slate-200 bg-white/30 p-4 text-sm text-slate-600">
          {message} {!organizationId ? <Link href="/dashboard/organizations" className="font-medium text-slate-950 underline">Go to organizations</Link> : null}
        </div>
      ) : null}

      <div className="mt-6">
        <div className="flex items-end justify-between gap-3">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">Sources</p>
            <h3 className="mt-1 font-display text-lg font-semibold text-slate-950">Connected inboxes</h3>
          </div>
          <span className="rounded-md border border-slate-200 bg-white/30 px-2 py-1 font-mono text-xs text-slate-600">{connections.length} connected</span>
        </div>
        {loading ? <p className="mt-3 text-sm text-slate-600">Loading...</p> : null}
        {!loading && connections.length === 0 ? <p className="mt-3 text-sm text-slate-600">No Gmail inbox connected yet.</p> : null}
        <div className="mt-3 space-y-4">
          {connections.map((connection) => {
            const draftRule = draftRules[connection.id] ?? rulesByConnectionId.get(connection.id);
            const draftMeta = draftConnectionMeta[connection.id] ?? { inbox_type: connection.inbox_type ?? "individual", shared_address: connection.shared_address ?? "", channel_notes: connection.channel_notes ?? "" };
            const activeImport = activeImportByConnectionId.get(connection.id);
            const latestImport = latestImportByConnectionId.get(connection.id);
            const importIsBusy = Boolean(activeImport) || syncingConnectionId === connection.id || queueingConnectionId === connection.id;
            const activeImportRuntime = activeImport ? importRuntime(activeImport) : null;
            const latestImportRuntime = latestImport ? importRuntime(latestImport) : null;
            const health = connectionHealth(connection, activeImport);
            const savedInboxType = connection.inbox_type ?? "individual";
            const sourceLabel = savedInboxType === "google_group" ? "Google Group" : savedInboxType === "shared_mailbox" ? "Shared mailbox" : "Individual inbox";
            const sourceAddress = savedInboxType === "individual" ? "" : connection.shared_address?.trim() ?? "";
            const draftSourceAddress = draftMeta.shared_address.trim();
            const sharedSourceNeedsAddress = draftMeta.inbox_type !== "individual";
            const sharedAddressInvalid = sharedSourceNeedsAddress && Boolean(draftSourceAddress) && !isValidEmailAddress(draftSourceAddress);
            const saveDisabled = savingConnectionId === connection.id || (sharedSourceNeedsAddress && (!draftSourceAddress || sharedAddressInvalid));
            return (
              <div key={connection.id} className="rounded-lg border border-white/50 bg-white/60 backdrop-blur-xl p-4 text-sm shadow-[0_18px_48px_rgba(72,60,96,0.075)]">
                <div className="grid gap-4 xl:grid-cols-[1fr_auto]">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-medium text-slate-900">{inboxName(connection)}</p>
                      <span className={`rounded-md border px-2 py-1 text-xs font-medium ${health.className}`}>{health.label}</span>
                    </div>
                    <p className="mt-1 text-xs text-slate-500">{connection.gmail_email}</p>
                    <p className="mt-1 text-xs text-slate-500">Saved source: {sourceLabel}{sourceAddress ? ` / ${sourceAddress}` : ""}</p>
                    <p className="mt-2 text-xs leading-5 text-slate-600">{health.message}</p>
                    <div className="mt-3 grid gap-2 text-xs text-slate-600 sm:grid-cols-2 xl:grid-cols-4">
                      <div className="rounded-md border border-[#eee9f2] bg-white/30 p-2">
                        <span className="block font-medium text-slate-900">Sync</span>
                        <span>{connection.sync_status ?? "unknown"}</span>
                      </div>
                      <div className="rounded-md border border-[#eee9f2] bg-white/30 p-2">
                        <span className="block font-medium text-slate-900">Watch</span>
                        <span>{connection.watch_status ?? "unknown"}</span>
                      </div>
                      <div className="rounded-md border border-[#eee9f2] bg-white/30 p-2">
                        <span className="block font-medium text-slate-900">Last success</span>
                        <span>{formatDateTime(connection.last_successful_sync_at ?? connection.last_sync_at)}</span>
                      </div>
                      <div className="rounded-md border border-[#eee9f2] bg-white/30 p-2">
                        <span className="block font-medium text-slate-900">Watch expires</span>
                        <span>{formatDateTime(connection.watch_expires_at)}</span>
                      </div>
                    </div>
                    <div className="mt-2 grid gap-2 text-xs text-slate-500 sm:grid-cols-2">
                      <p>Last notification: {formatDateTime(connection.last_notification_at)}</p>
                      <p>Last sync started: {formatDateTime(connection.last_sync_started_at)}</p>
                      <p>Failures: {connection.consecutive_sync_failures ?? 0}</p>
                      <p>History checkpoint: {connection.gmail_history_id ?? "Not recorded"}</p>
                    </div>
                    <div className="mt-3 rounded-md border border-slate-200 bg-white/30 p-3 text-xs text-slate-600">
                      <p className="font-medium text-slate-900">Sync/watch next step</p>
                      <p className="mt-1 leading-5">{syncTroubleshootingSummary(connection)}</p>
                    </div>
                    {activeImport ? (
                      <div className={`mt-3 rounded-md border p-3 text-xs ${isLongRunningImport(activeImport) ? "border-[#d8d2e4] bg-white/50 text-[#6f6174]" : "border-[#ddd7e6] bg-white/50 text-[#655f73]"}`}>
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="font-medium">Import {activeImport.status}</span>
                          {activeImportRuntime ? <span>{activeImportRuntime}</span> : null}
                        </div>
                        <p className="mt-1">Buttons stay locked for this inbox until the job finishes. The page refreshes while it is active.</p>
                        {isLongRunningImport(activeImport) ? <p className="mt-1 font-medium">This import is taking longer than usual. If it stays here, refresh this page; the backend will mark stale jobs so you can retry.</p> : null}
                        <span className="mt-1 block text-slate-500">Job {activeImport.id}</span>
                      </div>
                    ) : latestImport ? (
                      <div className={`mt-3 rounded-md border p-3 text-xs ${importStatusTone(latestImport.status)}`}>
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="font-medium capitalize">Last import {latestImport.status}</span>
                          <span>{formatJobTime(latestImport)}</span>
                        </div>
                        <p className="mt-1">{importCounts(latestImport)}{latestImportRuntime ? ` / ${latestImportRuntime}` : ""}</p>
                        {latestImport.error_message ? <p className="mt-1 font-medium">{latestImport.error_message}</p> : null}
                        <span className="mt-1 block opacity-80">Job {latestImport.id}</span>
                      </div>
                    ) : null}
                    {connection.sync_error_message || connection.watch_error ? (
                      <div className="mt-3 rounded-md border border-[#d8d2e4] bg-white/50 p-3 text-xs text-[#6f6174]">
                        {connection.sync_error_message ?? connection.watch_error}
                      </div>
                    ) : null}
                    {health.label === "Needs attention" || health.label === "Reconnect needed" ? (
                      <div className="mt-3 rounded-md border border-slate-200 bg-white/30 p-3 text-xs text-slate-700">
                        <p className="font-medium">Recovery path</p>
                        <ol className="mt-2 list-decimal space-y-1 pl-4 leading-5">
                          <li>Run Import now after the current job finishes.</li>
                          <li>Reconnect Gmail if the inbox still needs attention.</li>
                          <li>Check Cloud Scheduler and Gmail Pub/Sub only if both import and reconnect fail.</li>
                        </ol>
                      </div>
                    ) : null}
                  </div>
                  <div className="flex flex-col gap-2 sm:flex-row xl:flex-col">
                    <button type="button" onClick={() => handleSync(connection.id)} disabled={importIsBusy} className="rounded-md border border-slate-300 bg-white/75 px-3 py-2 text-xs font-semibold text-slate-700 shadow-[0_10px_24px_rgba(72,60,96,0.06)] disabled:text-slate-400">
                      {activeImport ? "Import running" : syncingConnectionId === connection.id ? "Starting..." : "Import now"}
                    </button>
                    <button type="button" onClick={() => handleQueueSync(connection.id)} disabled={importIsBusy} className="rounded-md border border-slate-950 bg-slate-950 px-3 py-2 text-xs font-semibold text-white shadow-sm shadow-slate-900/10 disabled:border-slate-300 disabled:bg-slate-300">
                      {activeImport ? "Import running" : queueingConnectionId === connection.id ? "Queueing..." : "Queue import"}
                    </button>
                    {health.label === "Reconnect needed" || health.label === "Needs attention" ? (
                      <button type="button" onClick={handleConnect} disabled={connecting || !organizationId} className="rounded-md border border-[#d8d2e4] bg-white/50 px-3 py-2 text-xs font-semibold text-[#6f6174] disabled:opacity-50">
                        Reconnect Gmail
                      </button>
                    ) : null}
                  </div>
                </div>

                <div className="mt-4 grid gap-3 lg:grid-cols-4 lg:items-start">
                  <label className="block">
                    <span className="text-xs font-medium text-slate-500">Inbox label</span>
                    <input value={draftLabels[connection.id] ?? ""} onChange={(event) => setDraftLabels((current) => ({ ...current, [connection.id]: event.target.value }))} className={inputClassName()} />
                    <span className="mt-1 block min-h-8 text-xs text-transparent">No validation message</span>
                  </label>
                  <label className="block">
                    <span className="text-xs font-medium text-slate-500">Source type</span>
                    <select value={draftMeta.inbox_type} onChange={(event) => setDraftConnectionMeta((current) => ({ ...current, [connection.id]: { ...draftMeta, inbox_type: event.target.value, shared_address: event.target.value === "individual" ? "" : draftMeta.shared_address } }))} className={`${inputClassName()} bg-white`}>
                      {inboxTypeOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                    </select>
                    <span className="mt-1 block min-h-8 text-xs text-transparent">No validation message</span>
                  </label>
                  <label className="block">
                    <span className="text-xs font-medium text-slate-500">Group/shared address</span>
                    <input type="email" inputMode="email" value={draftMeta.shared_address} onChange={(event) => setDraftConnectionMeta((current) => ({ ...current, [connection.id]: { ...draftMeta, shared_address: event.target.value } }))} disabled={draftMeta.inbox_type === "individual"} placeholder="support@example.com" className={`${inputClassName(sharedAddressInvalid || (sharedSourceNeedsAddress && !draftSourceAddress))} disabled:bg-white/30`} />
                    <span className={`mt-1 block min-h-8 text-xs ${sharedAddressInvalid ? "text-[#6f6174]" : sharedSourceNeedsAddress && !draftSourceAddress ? "text-[#6f6174]" : "text-transparent"}`}>
                      {sharedAddressInvalid ? "Use a valid email address." : sharedSourceNeedsAddress && !draftSourceAddress ? "Enter the group or shared mailbox email before saving." : "No validation message"}
                    </span>
                  </label>
                  <label className="block">
                    <span className="text-xs font-medium text-slate-500">Gmail support label ID</span>
                    <input value={draftRule?.support_label_id ?? ""} onChange={(event) => setDraftRules((current) => ({ ...current, [connection.id]: { ...(current[connection.id] ?? draftRule), support_label_id: event.target.value || null } }))} placeholder="Optional" className={inputClassName()} />
                    <span className="mt-1 block min-h-8 text-xs text-transparent">No validation message</span>
                  </label>
                  <label className="block">
                    <span className="text-xs font-medium text-slate-500">Routing direction</span>
                    <select value={draftRule?.routing_direction ?? "shared_queue"} onChange={(event) => setDraftRules((current) => ({ ...current, [connection.id]: { ...(current[connection.id] ?? draftRule), routing_direction: event.target.value } }))} className={`${inputClassName()} bg-white`}>
                      {routingOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                    </select>
                  </label>
                  <label className="block lg:col-span-3">
                    <span className="text-xs font-medium text-slate-500">Source notes</span>
                    <textarea value={draftMeta.channel_notes} onChange={(event) => setDraftConnectionMeta((current) => ({ ...current, [connection.id]: { ...draftMeta, channel_notes: event.target.value } }))} rows={2} placeholder="Example: Google Group forwards to this connected Gmail account." className={inputClassName()} />
                  </label>
                  <button type="button" onClick={() => void handleSaveInbox(connection)} disabled={saveDisabled} className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 disabled:opacity-50">
                    {savingConnectionId === connection.id ? "Saving..." : "Save"}
                  </button>
                </div>

                <label className="mt-3 inline-flex items-center gap-2 text-xs text-slate-600">
                  <input type="checkbox" checked={draftRule?.import_unread_only ?? true} onChange={(event) => setDraftRules((current) => ({ ...current, [connection.id]: { ...(current[connection.id] ?? draftRule), import_unread_only: event.target.checked } }))} className="h-4 w-4 rounded border-slate-300" />
                  Import unread mail only
                </label>
              </div>
            );
          })}
        </div>
      </div>

      <div className="mt-6">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold">Recent imports</h3>
          <button type="button" onClick={() => void loadConnections()} className="text-xs font-semibold text-slate-600 hover:text-slate-950">Refresh</button>
        </div>
        {imports.length === 0 ? <p className="mt-3 text-sm text-slate-600">No imports yet.</p> : null}
        <div className="mt-3 space-y-2">
          {imports.map((job) => {
            const connection = connections.find((item) => item.id === jobConnectionId(job));
            const runtime = importRuntime(job);
            return (
              <div key={job.id} className={`rounded-md border p-3 text-xs ${importStatusTone(job.status)}`}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium capitalize">{job.status}</span>
                  <span>{formatJobTime(job)}</span>
                </div>
                <div className="mt-1">
                  {connection ? inboxName(connection) : "Gmail inbox"}
                  {" - "}{importCounts(job)}{runtime ? ` / ${runtime}` : ""}
                </div>
                {job.error_message ? <p className="mt-1 font-medium">{job.error_message}</p> : null}
                <span className="mt-1 block opacity-80">Job {job.id}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}






