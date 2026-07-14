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

const routingOptions = [
  { value: "shared_queue", label: "Shared queue" },
  { value: "priority_queue", label: "Priority queue" },
  { value: "specialist_queue", label: "Specialist queue" },
];

function inboxName(connection: GmailConnection) {
  return connection.display_name?.trim() || connection.gmail_email;
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
      await updateGmailConnection(accessToken, organizationId, connection.id, {
        display_name: draftLabels[connection.id]?.trim() || null,
      });
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
            const activeImport = activeImportByConnectionId.get(connection.id);
            const importIsBusy = Boolean(activeImport) || syncingConnectionId === connection.id || queueingConnectionId === connection.id;
            return (
              <div key={connection.id} className="rounded-lg border border-slate-200 p-4 text-sm">
                <div className="grid gap-4 xl:grid-cols-[1fr_auto]">
                  <div>
                    <p className="font-medium text-slate-900">{inboxName(connection)}</p>
                    <p className="mt-1 text-xs text-slate-500">{connection.gmail_email}</p>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs">
                      <span className="rounded-md bg-slate-100 px-2 py-1 text-slate-600">Connection: {connection.status}</span>
                      <span className="rounded-md bg-slate-100 px-2 py-1 text-slate-600">Sync: {connection.sync_status ?? "unknown"}</span>
                      <span className="rounded-md bg-slate-100 px-2 py-1 text-slate-600">Watch: {connection.watch_status ?? "unknown"}</span>
                    </div>
                  </div>
                  <div className="flex flex-col gap-2 sm:flex-row">
                    <button type="button" onClick={() => handleSync(connection.id)} disabled={importIsBusy} className="rounded-md border border-slate-300 px-3 py-2 text-xs font-medium text-slate-700 disabled:text-slate-400">
                      {activeImport ? "Import running" : syncingConnectionId === connection.id ? "Starting..." : "Import now"}
                    </button>
                    <button type="button" onClick={() => handleQueueSync(connection.id)} disabled={importIsBusy} className="rounded-md bg-slate-950 px-3 py-2 text-xs font-medium text-white disabled:bg-slate-400">
                      {activeImport ? "Import running" : queueingConnectionId === connection.id ? "Queueing..." : "Queue import"}
                    </button>
                  </div>
                </div>

                <div className="mt-4 grid gap-3 lg:grid-cols-[1fr_1fr_1fr_auto] lg:items-end">
                  <label className="block">
                    <span className="text-xs font-medium text-slate-500">Inbox label</span>
                    <input value={draftLabels[connection.id] ?? ""} onChange={(event) => setDraftLabels((current) => ({ ...current, [connection.id]: event.target.value }))} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
                  </label>
                  <label className="block">
                    <span className="text-xs font-medium text-slate-500">Gmail support label ID</span>
                    <input value={draftRule?.support_label_id ?? ""} onChange={(event) => setDraftRules((current) => ({ ...current, [connection.id]: { ...(current[connection.id] ?? draftRule), support_label_id: event.target.value || null } }))} placeholder="Optional" className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
                  </label>
                  <label className="block">
                    <span className="text-xs font-medium text-slate-500">Routing direction</span>
                    <select value={draftRule?.routing_direction ?? "shared_queue"} onChange={(event) => setDraftRules((current) => ({ ...current, [connection.id]: { ...(current[connection.id] ?? draftRule), routing_direction: event.target.value } }))} className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm">
                      {routingOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                    </select>
                  </label>
                  <button type="button" onClick={() => void handleSaveInbox(connection)} disabled={savingConnectionId === connection.id} className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 disabled:opacity-50">
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
            return (
              <div key={job.id} className="rounded-md bg-slate-50 p-3 text-xs text-slate-600">
                <span className="font-medium text-slate-800">{job.status}</span>
                {connection ? ` - ${inboxName(connection)}` : ""}
                {" - "}imported {String(job.job_metadata.imported_count ?? 0)}, skipped {String(job.job_metadata.skipped_count ?? 0)}
                <span className="mt-1 block text-slate-500">Job {job.id}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
