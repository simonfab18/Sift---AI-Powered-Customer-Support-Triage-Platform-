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

function isWatchExpiringSoon(value?: string | null) {
  if (!value) return false;
  const expiresAt = new Date(value).getTime();
  if (Number.isNaN(expiresAt)) return false;
  const twoDaysMs = 2 * 24 * 60 * 60 * 1000;
  return expiresAt - Date.now() <= twoDaysMs;
}

function connectionHealth(connection: GmailConnection, activeImport?: JobRun) {
  if (activeImport || connection.sync_status === "syncing") {
    return {
      label: "Syncing",
      className: "border-sky-200 bg-sky-50 text-sky-700",
      message: "Import is running. New messages may appear after this finishes.",
    };
  }

  if (connection.status === "reauthorization_required" || connection.sync_status === "reauthorization_required" || connection.watch_status === "reauthorization_required") {
    return {
      label: "Reconnect needed",
      className: "border-amber-200 bg-amber-50 text-amber-800",
      message: connection.reauthorization_reason ?? "Google needs this inbox to be connected again.",
    };
  }

  if (connection.sync_status === "degraded" || connection.watch_status === "degraded" || connection.watch_status === "error") {
    return {
      label: "Needs attention",
      className: "border-rose-200 bg-rose-50 text-rose-700",
      message: connection.sync_error_message ?? connection.watch_error ?? "Sync is degraded. Try import now, then reconnect Gmail if it stays degraded.",
    };
  }

  if (connection.watch_expires_at && isWatchExpiringSoon(connection.watch_expires_at)) {
    return {
      label: "Watch renewal soon",
      className: "border-amber-200 bg-amber-50 text-amber-800",
      message: "Gmail watch is close to renewal. Scheduler should refresh it before expiry.",
    };
  }

  if (connection.status === "active" && connection.sync_status === "active" && connection.watch_status === "active") {
    return {
      label: "Healthy",
      className: "border-emerald-200 bg-emerald-50 text-emerald-700",
      message: "Gmail sync and push watch are active.",
    };
  }

  return {
    label: "Setup in progress",
    className: "border-slate-200 bg-slate-50 text-slate-700",
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
      const connectionId = typeof job.job_metadata.gmail_connection_id === "string" ? job.job_metadata.gmail_connection_id : null;
      if (!connectionId || !["queued", "running"].includes(job.status)) continue;
      if (!active.has(connectionId)) active.set(connectionId, job);
    }
    return active;
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
        shared_address: connectionMeta.inbox_type === "individual" ? null : connectionMeta.shared_address.trim() || null,
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
      await loadConnections();
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
      setMessage(job.status === "queued" || job.status === "running" ? "Import is running for this inbox." : `Import ${job.status}.`);
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
      setMessage(`Queued import job ${job.id}. Status: ${job.status}.`);
      await loadConnections();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to queue Gmail import.");
    } finally {
      setQueueingConnectionId(null);
    }
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-base font-semibold">Gmail inboxes</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Connect multiple Gmail inboxes, label each source, and keep import rules separate per inbox.
          </p>
        </div>
        <button type="button" onClick={handleConnect} disabled={connecting || !organizationId} className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white disabled:bg-slate-400">
          {connecting ? "Connecting..." : "Connect Gmail"}
        </button>
      </div>

      {message ? (
        <div className="mt-5 rounded-md border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
          {message} {!organizationId ? <Link href="/dashboard/organizations" className="font-medium text-slate-950 underline">Go to organizations</Link> : null}
        </div>
      ) : null}

      <div className="mt-6">
        <h3 className="text-sm font-semibold">Connected inboxes</h3>
        {loading ? <p className="mt-3 text-sm text-slate-600">Loading...</p> : null}
        {!loading && connections.length === 0 ? <p className="mt-3 text-sm text-slate-600">No Gmail inbox connected yet.</p> : null}
        <div className="mt-3 space-y-4">
          {connections.map((connection) => {
            const draftRule = draftRules[connection.id] ?? rulesByConnectionId.get(connection.id);
            const draftMeta = draftConnectionMeta[connection.id] ?? { inbox_type: connection.inbox_type ?? "individual", shared_address: connection.shared_address ?? "", channel_notes: connection.channel_notes ?? "" };
            const activeImport = activeImportByConnectionId.get(connection.id);
            const importIsBusy = Boolean(activeImport) || syncingConnectionId === connection.id || queueingConnectionId === connection.id;
            const health = connectionHealth(connection, activeImport);
            const savedInboxType = connection.inbox_type ?? "individual";
            const sourceLabel = savedInboxType === "google_group" ? "Google Group" : savedInboxType === "shared_mailbox" ? "Shared mailbox" : "Individual inbox";
            const sourceAddress = savedInboxType === "individual" ? "" : connection.shared_address?.trim() ?? "";
            const draftSourceAddress = draftMeta.shared_address.trim();
            const sharedSourceNeedsAddress = draftMeta.inbox_type !== "individual";
            const sharedAddressInvalid = sharedSourceNeedsAddress && Boolean(draftSourceAddress) && !isValidEmailAddress(draftSourceAddress);
            const saveDisabled = savingConnectionId === connection.id || (sharedSourceNeedsAddress && (!draftSourceAddress || sharedAddressInvalid));
            return (
              <div key={connection.id} className="rounded-lg border border-slate-200 p-4 text-sm">
                <div className="grid gap-4 xl:grid-cols-[1fr_auto]">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-medium text-slate-900">{inboxName(connection)}</p>
                      <span className={`rounded-md border px-2 py-1 text-xs font-medium ${health.className}`}>{health.label}</span>
                    </div>
                    <p className="mt-1 text-xs text-slate-500">{connection.gmail_email}</p>
                    <p className="mt-1 text-xs text-slate-500">{sourceLabel}{sourceAddress ? ` / ${sourceAddress}` : ""}</p>
                    <p className="mt-2 text-xs leading-5 text-slate-600">{health.message}</p>
                    <div className="mt-3 grid gap-2 text-xs text-slate-600 sm:grid-cols-2 xl:grid-cols-4">
                      <div className="rounded-md bg-slate-50 p-2">
                        <span className="block font-medium text-slate-900">Sync</span>
                        <span>{connection.sync_status ?? "unknown"}</span>
                      </div>
                      <div className="rounded-md bg-slate-50 p-2">
                        <span className="block font-medium text-slate-900">Watch</span>
                        <span>{connection.watch_status ?? "unknown"}</span>
                      </div>
                      <div className="rounded-md bg-slate-50 p-2">
                        <span className="block font-medium text-slate-900">Last success</span>
                        <span>{formatDateTime(connection.last_successful_sync_at ?? connection.last_sync_at)}</span>
                      </div>
                      <div className="rounded-md bg-slate-50 p-2">
                        <span className="block font-medium text-slate-900">Watch expires</span>
                        <span>{formatDateTime(connection.watch_expires_at)}</span>
                      </div>
                    </div>
                    <div className="mt-2 grid gap-2 text-xs text-slate-500 sm:grid-cols-2">
                      <p>Last notification: {formatDateTime(connection.last_notification_at)}</p>
                      <p>Failures: {connection.consecutive_sync_failures ?? 0}</p>
                    </div>
                    {activeImport ? (
                      <div className="mt-3 rounded-md border border-sky-200 bg-sky-50 p-3 text-xs text-sky-700">
                        Import job {activeImport.id} is {activeImport.status}. Import buttons stay locked until this clears.
                      </div>
                    ) : null}
                    {connection.sync_error_message || connection.watch_error ? (
                      <div className="mt-3 rounded-md border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">
                        {connection.sync_error_message ?? connection.watch_error}
                      </div>
                    ) : null}
                    {health.label === "Needs attention" || health.label === "Reconnect needed" ? (
                      <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
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
                    <button type="button" onClick={() => handleSync(connection.id)} disabled={importIsBusy} className="rounded-md border border-slate-300 px-3 py-2 text-xs font-medium text-slate-700 disabled:text-slate-400">
                      {activeImport ? "Import running" : syncingConnectionId === connection.id ? "Starting..." : "Import now"}
                    </button>
                    <button type="button" onClick={() => handleQueueSync(connection.id)} disabled={importIsBusy} className="rounded-md bg-slate-950 px-3 py-2 text-xs font-medium text-white disabled:bg-slate-400">
                      {activeImport ? "Import running" : queueingConnectionId === connection.id ? "Queueing..." : "Queue import"}
                    </button>
                    {health.label === "Reconnect needed" || health.label === "Needs attention" ? (
                      <button type="button" onClick={handleConnect} disabled={connecting || !organizationId} className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs font-medium text-amber-800 disabled:opacity-50">
                        Reconnect Gmail
                      </button>
                    ) : null}
                  </div>
                </div>

                <div className="mt-4 grid gap-3 lg:grid-cols-4 lg:items-start">
                  <label className="block">
                    <span className="text-xs font-medium text-slate-500">Inbox label</span>
                    <input value={draftLabels[connection.id] ?? ""} onChange={(event) => setDraftLabels((current) => ({ ...current, [connection.id]: event.target.value }))} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
                    <span className="mt-1 block min-h-8 text-xs text-transparent">No validation message</span>
                  </label>
                  <label className="block">
                    <span className="text-xs font-medium text-slate-500">Source type</span>
                    <select value={draftMeta.inbox_type} onChange={(event) => setDraftConnectionMeta((current) => ({ ...current, [connection.id]: { ...draftMeta, inbox_type: event.target.value } }))} className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm">
                      {inboxTypeOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                    </select>
                    <span className="mt-1 block min-h-8 text-xs text-transparent">No validation message</span>
                  </label>
                  <label className="block">
                    <span className="text-xs font-medium text-slate-500">Group/shared address</span>
                    <input type="email" inputMode="email" value={draftMeta.shared_address} onChange={(event) => setDraftConnectionMeta((current) => ({ ...current, [connection.id]: { ...draftMeta, shared_address: event.target.value } }))} disabled={draftMeta.inbox_type === "individual"} placeholder="support@example.com" className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-50" />
                    <span className={`mt-1 block min-h-8 text-xs ${sharedAddressInvalid ? "text-rose-700" : sharedSourceNeedsAddress && !draftSourceAddress ? "text-amber-700" : "text-transparent"}`}>
                      {sharedAddressInvalid ? "Use a valid email address." : sharedSourceNeedsAddress && !draftSourceAddress ? "Enter the group or shared mailbox email before saving." : "No validation message"}
                    </span>
                  </label>
                  <label className="block">
                    <span className="text-xs font-medium text-slate-500">Gmail support label ID</span>
                    <input value={draftRule?.support_label_id ?? ""} onChange={(event) => setDraftRules((current) => ({ ...current, [connection.id]: { ...(current[connection.id] ?? draftRule), support_label_id: event.target.value || null } }))} placeholder="Optional" className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
                    <span className="mt-1 block min-h-8 text-xs text-transparent">No validation message</span>
                  </label>
                  <label className="block">
                    <span className="text-xs font-medium text-slate-500">Routing direction</span>
                    <select value={draftRule?.routing_direction ?? "shared_queue"} onChange={(event) => setDraftRules((current) => ({ ...current, [connection.id]: { ...(current[connection.id] ?? draftRule), routing_direction: event.target.value } }))} className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm">
                      {routingOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                    </select>
                  </label>
                  <label className="block lg:col-span-3">
                    <span className="text-xs font-medium text-slate-500">Source notes</span>
                    <textarea value={draftMeta.channel_notes} onChange={(event) => setDraftConnectionMeta((current) => ({ ...current, [connection.id]: { ...draftMeta, channel_notes: event.target.value } }))} rows={2} placeholder="Example: Google Group forwards to this connected Gmail account." className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
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
          <button type="button" onClick={() => void loadConnections()} className="text-xs font-medium text-slate-600">Refresh</button>
        </div>
        {imports.length === 0 ? <p className="mt-3 text-sm text-slate-600">No imports yet.</p> : null}
        <div className="mt-3 space-y-2">
          {imports.map((job) => {
            const connection = connections.find((item) => item.id === job.job_metadata.gmail_connection_id);
            const statusClass = job.status === "failed" ? "text-rose-700" : job.status === "succeeded" ? "text-emerald-700" : "text-sky-700";
            return (
              <div key={job.id} className="rounded-md bg-slate-50 p-3 text-xs text-slate-600">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className={`font-medium ${statusClass}`}>{job.status}</span>
                  <span className="text-slate-500">{formatJobTime(job)}</span>
                </div>
                <div className="mt-1">
                  {connection ? inboxName(connection) : "Gmail inbox"}
                  {" - "}imported {String(job.job_metadata.imported_count ?? 0)}, skipped {String(job.job_metadata.skipped_count ?? 0)}
                </div>
                {job.error_message ? <p className="mt-1 text-rose-700">{job.error_message}</p> : null}
                <span className="mt-1 block text-slate-500">Job {job.id}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
