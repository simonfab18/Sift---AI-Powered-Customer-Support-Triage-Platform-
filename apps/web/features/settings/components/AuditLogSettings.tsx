"use client";

import { useEffect, useMemo, useState } from "react";

import { getStoredOrganizationId } from "@/features/organizations/components/OrganizationManager";
import { getAuditLogs } from "@/features/tickets/api";
import type { AuditLog } from "@/features/tickets/types";
import { createClient } from "@/lib/supabase/client";

function formatDate(value: string) {
  return new Date(value).toLocaleString();
}

function escapeCsv(value: unknown) {
  const text = typeof value === "string" ? value : JSON.stringify(value ?? "");
  return `"${text.replaceAll('"', '""')}"`;
}

function buildCsv(logs: AuditLog[]) {
  const header = ["timestamp", "actor", "action", "resource_type", "resource_id", "metadata"];
  const rows = logs.map((log) => [log.created_at, log.actor_user_id ?? "system", log.action, log.resource_type, log.resource_id ?? "", log.metadata]);
  return [header, ...rows].map((row) => row.map(escapeCsv).join(",")).join("\n");
}

export function AuditLogSettings() {
  const supabase = createClient();
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [search, setSearch] = useState("");
  const [action, setAction] = useState("");
  const [resourceType, setResourceType] = useState("");
  const [selected, setSelected] = useState<AuditLog | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    const organizationId = getStoredOrganizationId();
    const { data } = await supabase.auth.getSession();
    const accessToken = data.session?.access_token;
    if (!organizationId || !accessToken) {
      setMessage("Select an organization and sign in to view audit logs.");
      setLoading(false);
      return;
    }
    try {
      const rows = await getAuditLogs(organizationId, accessToken, {
        search: search.trim() || undefined,
        action: action.trim() || undefined,
        resource_type: resourceType.trim() || undefined,
        limit: 100,
      });
      setLogs(rows);
      setSelected(rows[0] ?? null);
      setMessage(null);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to load audit logs.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const actions = useMemo(() => Array.from(new Set(logs.map((log) => log.action))).sort(), [logs]);
  const resourceTypes = useMemo(() => Array.from(new Set(logs.map((log) => log.resource_type))).sort(), [logs]);

  function exportCsv() {
    const blob = new Blob([buildCsv(logs)], { type: "text/csv;charset=utf-8" });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `audit-logs-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    window.URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-6">
      <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm shadow-slate-900/5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h2 className="font-display text-xl font-semibold text-slate-900">Audit log</h2>
            <p className="mt-1 text-sm text-slate-500">Review owner/admin-visible workspace activity with sensitive metadata redacted.</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-[220px_180px_180px_auto_auto]">
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search actor, action, resource" className="rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-teal-600" />
            <select value={action} onChange={(event) => setAction(event.target.value)} className="rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-teal-600">
              <option value="">All actions</option>
              {actions.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
            <select value={resourceType} onChange={(event) => setResourceType(event.target.value)} className="rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-teal-600">
              <option value="">All resources</option>
              {resourceTypes.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
            <button type="button" onClick={load} className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800">Filter</button>
            <button type="button" onClick={exportCsv} disabled={logs.length === 0} className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:border-slate-400 disabled:cursor-not-allowed disabled:opacity-50">Export</button>
          </div>
        </div>
        {message ? <p className="mt-4 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">{message}</p> : null}
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
        <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm shadow-slate-900/5">
          <div className="border-b border-slate-200 px-4 py-3 text-sm text-slate-500">{loading ? "Loading..." : `${logs.length} events`}</div>
          {logs.length === 0 ? <p className="p-5 text-sm text-slate-500">No audit events match the current filters.</p> : null}
          {logs.map((log) => (
            <button key={log.id} type="button" onClick={() => setSelected(log)} className="grid w-full gap-2 border-b border-slate-100 px-4 py-3 text-left text-sm transition last:border-b-0 hover:bg-slate-50 sm:grid-cols-[1fr_auto]">
              <span>
                <span className="block font-medium text-slate-900">{log.action}</span>
                <span className="mt-1 block text-slate-500">{log.actor_user_id ?? "system"} - {log.resource_type}{log.resource_id ? ` - ${log.resource_id}` : ""}</span>
              </span>
              <span className="font-mono text-xs text-slate-500">{formatDate(log.created_at)}</span>
            </button>
          ))}
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm shadow-slate-900/5">
          <h2 className="font-display text-lg font-semibold text-slate-900">Metadata details</h2>
          {selected ? (
            <div className="mt-4 space-y-3 text-sm">
              <p><span className="text-slate-500">Actor:</span> <span className="font-medium text-slate-900">{selected.actor_user_id ?? "system"}</span></p>
              <p><span className="text-slate-500">Resource:</span> <span className="font-medium text-slate-900">{selected.resource_type}</span></p>
              <pre className="max-h-96 overflow-auto rounded-md bg-slate-950 p-4 text-xs leading-5 text-slate-100">{JSON.stringify(selected.metadata, null, 2)}</pre>
            </div>
          ) : <p className="mt-4 text-sm text-slate-500">Select an audit event to inspect metadata.</p>}
        </div>
      </section>
    </div>
  );
}

