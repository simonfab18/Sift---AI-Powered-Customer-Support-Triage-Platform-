"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { Button } from "@/components/ui/Button";
import { StatCard } from "@/components/ui/StatCard";
import { TriageMeter } from "@/components/ui/TriageMeter";
import { getStoredOrganizationId } from "@/features/organizations/components/OrganizationManager";
import { getGmailConnections } from "@/lib/api-client";
import type { GmailConnection } from "@/lib/api-types";
import { createClient } from "@/lib/supabase/client";
import {
  createSavedView,
  deleteSavedView,
  getMetricsOverview,
  getSavedViews,
  getTickets,
  runBulkTicketAction,
  updateSavedView,
} from "../api";
import type { MetricsOverview, SavedView, TicketListItem } from "../types";
import { TicketList } from "./TicketList";

const urgencyOrder: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };
const statusOptions = ["all", "new", "open", "pending", "awaiting_approval", "draft_created", "resolved", "spam"];
const slaOptions = ["all", "on_track", "warning", "breached", "paused"];

export function TicketDashboard() {
  const supabase = createClient();
  const [tickets, setTickets] = useState<TicketListItem[]>([]);
  const [metrics, setMetrics] = useState<MetricsOverview | null>(null);
  const [savedViews, setSavedViews] = useState<SavedView[]>([]);
  const [gmailConnections, setGmailConnections] = useState<GmailConnection[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [urgency, setUrgency] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [slaFilter, setSlaFilter] = useState("all");
  const [inboxFilter, setInboxFilter] = useState("all");
  const [sourceTypeFilter, setSourceTypeFilter] = useState("all");
  const [sort, setSort] = useState("urgency");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkAction, setBulkAction] = useState("resolve");
  const [bulkStatus, setBulkStatus] = useState("pending");
  const [bulkAssignee, setBulkAssignee] = useState("");
  const [viewName, setViewName] = useState("");
  const [savingView, setSavingView] = useState(false);
  const [updatingView, setUpdatingView] = useState(false);
  const [activeSavedViewId, setActiveSavedViewId] = useState<string | null>(null);
  const [runningBulk, setRunningBulk] = useState(false);
  const [pendingBulkConfirm, setPendingBulkConfirm] = useState<{ action: string; ticketIds: string[] } | null>(null);

  async function getContext() {
    const organizationId = getStoredOrganizationId();
    if (!organizationId) return null;
    const { data } = await supabase.auth.getSession();
    const accessToken = data.session?.access_token;
    if (!accessToken) return null;
    return { organizationId, accessToken };
  }

  async function loadTickets() {
    setLoading(true);
    setMessage(null);

    const context = await getContext();
    if (!context) {
      setMessage("Select an organization and sign in before viewing tickets.");
      setLoading(false);
      return;
    }

    try {
      const [loadedTickets, loadedMetrics, views, connections] = await Promise.all([
        getTickets(context.organizationId, context.accessToken, {
          status: statusFilter,
          priority: urgency,
          sla_status: slaFilter,
          gmail_connection_id: inboxFilter,
          gmail_inbox_type: sourceTypeFilter,
        }),
        getMetricsOverview(context.organizationId, context.accessToken),
        getSavedViews(context.organizationId, context.accessToken).catch(() => []),
        getGmailConnections(context.accessToken, context.organizationId).catch(() => []),
      ]);
      setTickets(loadedTickets);
      setMetrics(loadedMetrics);
      setSavedViews(views);
      setGmailConnections(connections);
      setSelectedIds(new Set());
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to load tickets.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadTickets();
  }, [urgency, statusFilter, slaFilter, inboxFilter, sourceTypeFilter]);

  const visibleTickets = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return tickets
      .filter((ticket) => urgency === "all" || ticket.priority === urgency)
      .filter((ticket) => statusFilter === "all" || ticket.status === statusFilter)
      .filter((ticket) => slaFilter === "all" || ticket.sla_status === slaFilter)
      .filter((ticket) => inboxFilter === "all" || ticket.gmail_connection_id === inboxFilter)
      .filter((ticket) => sourceTypeFilter === "all" || ticket.gmail_connection_inbox_type === sourceTypeFilter)
      .filter((ticket) => {
        if (!normalizedQuery) return true;
        return [ticket.subject, ticket.customer_email, ticket.customer_name ?? "", ticket.category, ticket.status]
          .join(" ")
          .toLowerCase()
          .includes(normalizedQuery);
      })
      .sort((left, right) => {
        if (sort === "recent") return new Date(right.received_at).getTime() - new Date(left.received_at).getTime();
        return (urgencyOrder[left.priority] ?? 4) - (urgencyOrder[right.priority] ?? 4) || new Date(right.received_at).getTime() - new Date(left.received_at).getTime();
      });
  }, [tickets, query, urgency, statusFilter, slaFilter, inboxFilter, sourceTypeFilter, sort]);

  function currentSavedViewFilters() {
    const filters: Record<string, string> = {};
    if (urgency !== "all") filters.priority = urgency;
    if (statusFilter !== "all") filters.status = statusFilter;
    if (slaFilter !== "all") filters.sla_status = slaFilter;
    if (inboxFilter !== "all") filters.gmail_connection_id = inboxFilter;
    if (sourceTypeFilter !== "all") filters.gmail_inbox_type = sourceTypeFilter;
    return filters;
  }

  function normalizeFilters(filters: Record<string, string>) {
    return JSON.stringify(Object.keys(filters).sort().reduce<Record<string, string>>((result, key) => {
      result[key] = filters[key];
      return result;
    }, {}));
  }

  function savedViewSummary(view: SavedView) {
    const labels: string[] = [];
    if (view.filters.priority) labels.push(view.filters.priority.replaceAll("_", " "));
    if (view.filters.status) labels.push(view.filters.status.replaceAll("_", " "));
    if (view.filters.sla_status) labels.push(`SLA ${view.filters.sla_status.replaceAll("_", " ")}`);
    if (view.filters.gmail_connection_id) {
      const connection = gmailConnections.find((item) => item.id === view.filters.gmail_connection_id);
      labels.push(connection?.display_name || connection?.gmail_email || "Saved inbox");
    }
    if (view.filters.gmail_inbox_type) labels.push(view.filters.gmail_inbox_type.replaceAll("_", " "));
    return labels.length ? labels.join(" / ") : "All active tickets";
  }

  const activeSavedView = savedViews.find((view) => view.id === activeSavedViewId) ?? null;
  const activeSavedViewChanged = activeSavedView ? normalizeFilters(activeSavedView.filters) !== normalizeFilters(currentSavedViewFilters()) : false;

  function toggleSelection(ticketId: string) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(ticketId)) next.delete(ticketId);
      else next.add(ticketId);
      return next;
    });
  }

  function applySavedView(view: SavedView) {
    setUrgency(view.filters.priority ?? "all");
    setStatusFilter(view.filters.status ?? "all");
    setSlaFilter(view.filters.sla_status ?? "all");
    setInboxFilter(view.filters.gmail_connection_id ?? "all");
    setSourceTypeFilter(view.filters.gmail_inbox_type ?? "all");
    setQuery("");
    setActiveSavedViewId(view.id);
    setMessage(`Applied ${view.name}.`);
  }

  async function handleSaveView() {
    const context = await getContext();
    if (!context) return;
    if (!viewName.trim()) {
      setMessage("Name the view before saving it.");
      return;
    }
    setSavingView(true);
    setMessage(null);
    try {
      const created = await createSavedView(context.organizationId, context.accessToken, viewName.trim(), currentSavedViewFilters());
      setViewName("");
      setSavedViews((views) => [...views.filter((view) => view.id !== created.id), created].sort((left, right) => left.name.localeCompare(right.name)));
      setActiveSavedViewId(created.id);
      setMessage("Saved view created.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to save view.");
    } finally {
      setSavingView(false);
    }
  }

  async function handleUpdateActiveView() {
    const context = await getContext();
    if (!context || !activeSavedView) return;
    setUpdatingView(true);
    setMessage(null);
    try {
      const updated = await updateSavedView(context.organizationId, context.accessToken, activeSavedView.id, { filters: currentSavedViewFilters() });
      setSavedViews((views) => views.map((view) => (view.id === updated.id ? updated : view)));
      setMessage(`Updated ${updated.name}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to update saved view.");
    } finally {
      setUpdatingView(false);
    }
  }
  async function handleDeleteView(viewId: string) {
    const context = await getContext();
    if (!context) return;
    try {
      await deleteSavedView(context.organizationId, context.accessToken, viewId);
      setSavedViews((views) => views.filter((view) => view.id !== viewId));
      if (activeSavedViewId === viewId) setActiveSavedViewId(null);
      setMessage("Saved view deleted.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to delete view.");
    }
  }

  function bulkActionLabel(action: string) {
    return action.replaceAll("_", " ");
  }

  async function executeBulkAction(ticketIds: string[], action: string, confirmed: boolean) {
    const context = await getContext();
    if (!context) return;
    const destructive = action === "resolve" || action === "mark_spam";

    setRunningBulk(true);
    setMessage(null);
    try {
      const result = await runBulkTicketAction(context.organizationId, context.accessToken, {
        ticket_ids: ticketIds,
        action,
        assigned_to_user_id: action === "assign" ? bulkAssignee.trim() || null : undefined,
        status: action === "change_status" ? bulkStatus : undefined,
        confirm: destructive ? confirmed : undefined,
      });
      const succeeded = result.results.filter((item) => item.success).length;
      const failed = result.results.length - succeeded;
      setPendingBulkConfirm(null);
      await loadTickets();
      setMessage(`${bulkActionLabel(action)} finished: ${succeeded} ticket${succeeded === 1 ? "" : "s"} updated${failed ? `, ${failed} failed` : ""}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Bulk action failed.");
    } finally {
      setRunningBulk(false);
    }
  }

  async function handleBulkAction() {
    const ticketIds = Array.from(selectedIds);
    if (ticketIds.length === 0) {
      setMessage("Select tickets before running a bulk action.");
      return;
    }
    const destructive = bulkAction === "resolve" || bulkAction === "mark_spam";
    if (destructive) {
      setPendingBulkConfirm({ action: bulkAction, ticketIds });
      setMessage(null);
      return;
    }

    await executeBulkAction(ticketIds, bulkAction, false);
  }

  return (
    <section className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="font-mono text-xs uppercase tracking-wide text-slate-500">Active queue</p>
          <h2 className="font-display text-3xl font-semibold tracking-tight text-slate-900">Triage queue</h2>
          <p className="mt-2 max-w-2xl text-slate-600">Filter, save working views, and run queue actions without opening tickets one by one.</p>
        </div>
        <Button type="button" onClick={() => void loadTickets()} variant="outline">Refresh</Button>
      </div>

      {message ? (
        <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-600">
          {message} {message.includes("organization") ? <Link href="/dashboard/organizations" className="font-medium text-teal-700 underline">Go to organizations</Link> : null}
        </div>
      ) : null}

      {metrics ? (
        <div className="grid gap-6 xl:grid-cols-[1fr_1fr]">
          <div className="grid overflow-hidden rounded-lg border border-slate-200 sm:grid-cols-3">
            <StatCard label="Active" value={metrics.active_tickets} />
            <StatCard label="Critical" value={metrics.critical_tickets} />
            <StatCard label="High" value={metrics.high_priority_tickets} />
          </div>
          <TriageMeter metrics={metrics} />
        </div>
      ) : null}

      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <div className="grid gap-3 xl:grid-cols-[1fr_auto_auto_auto_auto_auto_auto]">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search subject, sender, category..."
            className="rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-slate-900"
          />
          <select value={urgency} onChange={(event) => setUrgency(event.target.value)} className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm">
            <option value="all">All urgency</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm">
            {statusOptions.map((status) => <option key={status} value={status}>{status === "all" ? "All status" : status.replaceAll("_", " ")}</option>)}
          </select>
          <select value={slaFilter} onChange={(event) => setSlaFilter(event.target.value)} className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm">
            {slaOptions.map((sla) => <option key={sla} value={sla}>{sla === "all" ? "All SLA" : sla.replaceAll("_", " ")}</option>)}
          </select>
          <select value={inboxFilter} onChange={(event) => setInboxFilter(event.target.value)} className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm">
            <option value="all">All inboxes</option>
            {gmailConnections.map((connection) => <option key={connection.id} value={connection.id}>{connection.display_name || connection.gmail_email}</option>)}
          </select>
          <select value={sourceTypeFilter} onChange={(event) => setSourceTypeFilter(event.target.value)} className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm">
            <option value="all">All sources</option>
            <option value="individual">Individual inboxes</option>
            <option value="google_group">Google Groups</option>
            <option value="shared_mailbox">Shared mailboxes</option>
          </select>
          <select value={sort} onChange={(event) => setSort(event.target.value)} className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm">
            <option value="urgency">Sort by urgency</option>
            <option value="recent">Sort by recency</option>
          </select>
        </div>

        <div className="mt-4 grid gap-3 xl:grid-cols-[1fr_auto] xl:items-start">
          <div className="space-y-2">
            <div className="flex flex-wrap gap-2">
              {savedViews.length ? savedViews.map((view) => {
                const active = view.id === activeSavedViewId;
                return (
                  <span key={view.id} className={`inline-flex items-center gap-2 rounded-md border px-2 py-1 text-xs ${active ? "border-teal-300 bg-teal-50 text-teal-800" : "border-slate-200 bg-slate-50 text-slate-600"}`} title={savedViewSummary(view)}>
                    <button type="button" onClick={() => applySavedView(view)} className="text-left font-medium">{view.name}</button>
                    {active ? <span className="rounded bg-white/70 px-1 font-medium">Active</span> : null}
                    <button type="button" onClick={() => void handleDeleteView(view.id)} className="text-slate-400 hover:text-rose-600" aria-label={`Delete ${view.name}`}>x</button>
                  </span>
                );
              }) : <p className="text-xs text-slate-500">No saved views yet.</p>}
            </div>
            {activeSavedView ? (
              <p className="text-xs text-slate-500">
                Current view: <span className="font-medium text-slate-700">{activeSavedView.name}</span> / {savedViewSummary(activeSavedView)}{activeSavedViewChanged ? " / filters changed" : ""}
              </p>
            ) : null}
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <input value={viewName} onChange={(event) => setViewName(event.target.value)} placeholder="View name" className="min-w-0 rounded-md border border-slate-300 px-3 py-2 text-sm" />
            <Button type="button" variant="outline" onClick={() => void handleSaveView()} disabled={savingView}>{savingView ? "Saving..." : "Save view"}</Button>
            <Button type="button" variant="outline" onClick={() => void handleUpdateActiveView()} disabled={!activeSavedView || !activeSavedViewChanged || updatingView}>{updatingView ? "Updating..." : "Update current"}</Button>
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <div className="grid gap-3 lg:grid-cols-[auto_auto_1fr_auto] lg:items-center">
          <p className="text-sm font-medium text-slate-700">{selectedIds.size} selected</p>
          <select value={bulkAction} onChange={(event) => { setBulkAction(event.target.value); setPendingBulkConfirm(null); }} className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm">
            <option value="resolve">Resolve</option>
            <option value="mark_spam">Mark spam</option>
            <option value="change_status">Change status</option>
            <option value="rerun_triage">Re-run triage</option>
            <option value="assign">Assign</option>
          </select>
          {bulkAction === "change_status" ? (
            <select value={bulkStatus} onChange={(event) => setBulkStatus(event.target.value)} className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm">
              {statusOptions.filter((status) => status !== "all").map((status) => <option key={status} value={status}>{status.replaceAll("_", " ")}</option>)}
            </select>
          ) : bulkAction === "assign" ? (
            <input value={bulkAssignee} onChange={(event) => setBulkAssignee(event.target.value)} placeholder="User ID" className="rounded-md border border-slate-300 px-3 py-2 text-sm" />
          ) : <span />}
          <Button type="button" variant="primary" onClick={() => void handleBulkAction()} disabled={runningBulk || selectedIds.size === 0}>{runningBulk ? "Running..." : "Apply"}</Button>
        </div>
        {pendingBulkConfirm ? (
          <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="font-medium capitalize">Confirm {bulkActionLabel(pendingBulkConfirm.action)}</p>
                <p className="mt-1 text-amber-800">This will update {pendingBulkConfirm.ticketIds.length} selected ticket{pendingBulkConfirm.ticketIds.length === 1 ? "" : "s"}. You can still find resolved or spam tickets by changing the status filter.</p>
              </div>
              <div className="flex shrink-0 gap-2">
                <Button type="button" variant="outline" onClick={() => setPendingBulkConfirm(null)} disabled={runningBulk}>Cancel</Button>
                <Button type="button" variant="primary" onClick={() => void executeBulkAction(pendingBulkConfirm.ticketIds, pendingBulkConfirm.action, true)} disabled={runningBulk}>{runningBulk ? "Applying..." : "Confirm"}</Button>
              </div>
            </div>
          </div>
        ) : null}
      </div>

      {loading ? (
        <p className="rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-600">Loading tickets...</p>
      ) : (
        <TicketList tickets={visibleTickets} selectedIds={selectedIds} onToggleSelection={toggleSelection} />
      )}
    </section>
  );
}
