"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { ChartBars, EmptyState, MetricCard, SeverityBadge, StatusPill } from "@/components/sift/SiftComponents";
import { GmailConnectionPanel } from "@/features/gmail/components/GmailConnectionPanel";
import { OrganizationManager } from "@/features/organizations/components/OrganizationManager";
import { TeamSettings } from "@/features/settings/components/TeamSettings";
import { getStoredOrganizationId, setStoredOrganizationId } from "@/features/organizations/components/OrganizationManager";
import { getGmailConnections, getMe } from "@/lib/api-client";
import type { Organization } from "@/lib/api-types";
import { createClient } from "@/lib/supabase/client";
import { getMetricsOverview, getReplySuggestions, getTickets } from "@/features/tickets/api";
import type { MetricsOverview, ReplySuggestion, TicketListItem } from "@/features/tickets/types";

type LoadState = {
  loading: boolean;
  message: string | null;
  organizations: Organization[];
  organization: Organization | null;
  metrics: MetricsOverview | null;
  tickets: TicketListItem[];
  suggestions: ReplySuggestion[];
  gmailConnected: boolean;
};

function priorityToSeverity(priority: string): "critical" | "high" | "medium" | "low" {
  const value = priority.toLowerCase();
  if (value.includes("critical")) return "critical";
  if (value.includes("high")) return "high";
  if (value.includes("medium")) return "medium";
  return "low";
}

function formatStatus(value: string) {
  return value.replaceAll("_", " ");
}

function useRealSupportData() {
  const [state, setState] = useState<LoadState>({
    loading: true,
    message: null,
    organizations: [],
    organization: null,
    metrics: null,
    tickets: [],
    suggestions: [],
    gmailConnected: false,
  });

  const load = useCallback(async () => {
    const supabase = createClient();
    setState((current) => ({ ...current, loading: true, message: null }));
    const { data } = await supabase.auth.getSession();
    const accessToken = data.session?.access_token;
    if (!accessToken) {
      setState((current) => ({ ...current, loading: false, message: "Sign in to load your real support dashboard." }));
      return;
    }

    try {
      const me = await getMe(accessToken);
      const stored = getStoredOrganizationId();
      const selected = me.organizations.find((item) => item.id === stored) ?? me.organizations[0] ?? null;
      if (selected) setStoredOrganizationId(selected.id);

      if (!selected) {
        setState({ loading: false, message: "Create or join a workspace before viewing dashboard data.", organizations: me.organizations, organization: null, metrics: null, tickets: [], suggestions: [], gmailConnected: false });
        return;
      }

      const [metricData, ticketData, gmailConnections] = await Promise.all([
        getMetricsOverview(selected.id, accessToken),
        getTickets(selected.id, accessToken),
        getGmailConnections(accessToken, selected.id),
      ]);

      const suggestionGroups = await Promise.all(
        ticketData.slice(0, 20).map(async (ticket) => {
          try {
            return await getReplySuggestions(selected.id, ticket.id, accessToken);
          } catch {
            return [];
          }
        }),
      );

      setState({
        loading: false,
        message: null,
        organizations: me.organizations,
        organization: selected,
        metrics: metricData,
        tickets: ticketData,
        suggestions: suggestionGroups.flat(),
        gmailConnected: gmailConnections.some((connection) => connection.status === "active"),
      });
    } catch (error) {
      setState((current) => ({ ...current, loading: false, message: error instanceof Error ? error.message : "Failed to load dashboard data." }));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return { ...state, reload: load };
}

function RealDataFrame({ children }: { children: (data: ReturnType<typeof useRealSupportData>) => React.ReactNode }) {
  const data = useRealSupportData();
  if (data.loading) return <section className="panel"><h2>Loading real support data...</h2><p style={{ color: "var(--muted)" }}>Reading your Supabase session and backend queue.</p></section>;
  if (data.message) return <EmptyState title="Dashboard data is not available" body={data.message} action="Sign in" href="/login" />;
  return <>{children(data)}</>;
}

export function RealOverviewPage() {
  return <RealDataFrame>{({ metrics, tickets, suggestions, gmailConnected, organization }) => {
    const pendingSuggestions = suggestions.filter((item) => item.status === "suggested" || item.status === "edited");
    const metricCards = metrics ? [
      { label: "Open tickets", value: String(metrics.active_tickets), change: `${metrics.critical_tickets} critical`, tone: metrics.critical_tickets > 0 ? "warning" : "success" },
      { label: "Total conversations", value: String(metrics.total_tickets), change: `${metrics.resolved_tickets} resolved`, tone: "info" },
      { label: "Pending approvals", value: String(pendingSuggestions.length), change: "real suggestions", tone: pendingSuggestions.length > 0 ? "warning" : "success" },
      { label: "Gmail connection", value: gmailConnected ? "Live" : "Off", change: organization?.name ?? "workspace", tone: gmailConnected ? "success" : "warning" },
    ] : [];
    return <div className="app-page-grid"><div className="page-title"><span className="eyebrow">Overview</span><h1>Good afternoon, Simon</h1><p>Real queue data for {organization?.name}. No mock dashboard numbers are shown here.</p></div><div className="metrics-grid">{metricCards.map((m) => <MetricCard key={m.label} {...m} />)}</div><div className="dashboard-grid"><RealTicketList title="Needs attention now" tickets={tickets.slice(0, 6)} /><section className="panel"><h2>Queue health</h2><p><StatusPill tone={gmailConnected ? "success" : "warning"}>{gmailConnected ? "Gmail connected" : "Gmail not connected"}</StatusPill></p><p style={{ color: "var(--muted)" }}>Tickets are loaded from your backend for the selected workspace.</p>{metrics ? <ChartBars values={chartValues(metrics)} /> : null}</section></div></div>;
  }}</RealDataFrame>;
}

export function RealInboxPage() {
  return <RealDataFrame>{({ tickets, organization }) => <div className="app-page-grid"><div className="page-title"><span className="eyebrow">Inbox</span><h1>Prioritized ticket queue</h1><p>Real tickets for {organization?.name}, sorted by the backend response.</p></div><RealTicketList title="All active tickets" tickets={tickets} /></div>}</RealDataFrame>;
}

export function RealApprovalsPage() {
  return <RealDataFrame>{({ tickets, suggestions }) => {
    const ticketById = new Map(tickets.map((ticket) => [ticket.id, ticket]));
    const pending = suggestions.filter((item) => item.status === "suggested" || item.status === "edited");
    return <div className="app-page-grid"><div className="page-title"><span className="eyebrow">Approvals</span><h1>Review AI suggestions before Gmail drafts are created.</h1><p>Approval rows are built from real reply suggestions attached to real tickets.</p></div>{pending.length === 0 ? <EmptyState title="Nothing needs approval" body="New AI suggestions that require your review will appear here after triage runs." action="Open inbox" href="/app/inbox" /> : <section className="ticket-list">{pending.map((suggestion) => { const ticket = ticketById.get(suggestion.ticket_id); return <Link className="ticket-row" href={`/app/inbox/${suggestion.ticket_id}`} key={suggestion.id}><div><h3>{ticket?.subject ?? suggestion.ticket_id}</h3><small>{suggestion.edited_body ?? suggestion.body}</small></div><div className="ticket-meta"><StatusPill tone="warning">{formatStatus(suggestion.status)}</StatusPill><StatusPill tone="info">AI</StatusPill></div></Link>; })}</section>}</div>;
  }}</RealDataFrame>;
}

export function RealAnalyticsPage() {
  return <RealDataFrame>{({ metrics, tickets, suggestions, organization }) => {
    const pending = suggestions.filter((item) => item.status === "suggested" || item.status === "edited").length;
    const cards = metrics ? [
      { label: "Total conversations", value: String(metrics.total_tickets), change: `${metrics.active_tickets} active`, tone: "info" },
      { label: "Resolved tickets", value: String(metrics.resolved_tickets), change: "backend metric", tone: "success" },
      { label: "Drafts created", value: String(metrics.draft_created_tickets), change: "Gmail drafts", tone: "success" },
      { label: "Pending suggestions", value: String(pending), change: "approval queue", tone: pending > 0 ? "warning" : "success" },
    ] : [];
    return <div className="app-page-grid"><div className="page-title"><span className="eyebrow">Analytics</span><h1>Queue analytics for {organization?.name}</h1><p>These metrics come from the backend metrics and tickets endpoints.</p></div><div className="metrics-grid">{cards.map((m) => <MetricCard key={m.label} {...m} />)}</div><div className="dashboard-grid"><section className="panel"><h2>Priority distribution</h2>{metrics ? <ChartBars values={chartValues(metrics)} /> : null}</section><section className="panel"><h2>Status breakdown</h2>{metrics ? Object.entries(metrics.by_status).map(([status, count]) => <p key={status}><StatusPill tone="info">{formatStatus(status)}</StatusPill> {count}</p>) : null}<p style={{ color: "var(--muted)" }}>{tickets.length} tickets loaded in this workspace.</p></section></div></div>;
  }}</RealDataFrame>;
}

function RealTicketList({ title, tickets }: { title: string; tickets: TicketListItem[] }) {
  if (tickets.length === 0) return <EmptyState title="No conversations yet" body="Connect Gmail or import sample conversations to see Sift prioritize your support queue." action="Connect Gmail" href="/app/integrations" />;
  return <section className="ticket-list"><div style={{ padding: 18, borderBottom: "1px solid var(--border)" }}><h2 style={{ margin: 0 }}>{title}</h2></div>{tickets.map((ticket) => <Link className="ticket-row" href={`/app/inbox/${ticket.id}`} key={ticket.id}><div><h3>{ticket.subject}</h3><small>{ticket.customer_name ?? ticket.customer_email} · {formatStatus(ticket.status)} · {new Date(ticket.received_at).toLocaleString()}</small></div><div className="ticket-meta"><SeverityBadge severity={priorityToSeverity(ticket.priority)} /><StatusPill tone="info">{formatStatus(ticket.category)}</StatusPill><StatusPill tone="neutral">{formatStatus(ticket.sentiment)}</StatusPill></div></Link>)}</section>;
}

function chartValues(metrics: MetricsOverview) {
  const values = [metrics.critical_tickets, metrics.high_priority_tickets, metrics.active_tickets, metrics.resolved_tickets, metrics.draft_created_tickets].map((value) => Math.max(value, 1));
  const max = Math.max(...values, 1);
  return values.map((value) => Math.max(12, Math.round((value / max) * 100)));
}

export function RealCustomersPage() {
  return <RealDataFrame>{({ tickets, organization }) => {
    const customers = Array.from(new Map(tickets.map((ticket) => [ticket.customer_email, ticket])).values());
    if (customers.length === 0) return <EmptyState title="No customers yet" body="Import Gmail conversations and customer profiles will appear here automatically from real tickets." action="Import conversations" href="/app/integrations" />;
    return <div className="app-page-grid"><div className="page-title"><span className="eyebrow">Customers</span><h1>Customer context for {organization?.name}</h1><p>Built from real imported support conversations. No mock customer records are shown.</p></div><section className="ticket-list"><div style={{ padding: 18, borderBottom: "1px solid var(--border)" }}><h2 style={{ margin: 0 }}>Imported customers</h2></div>{customers.map((ticket) => <Link className="ticket-row" href={`/app/inbox/${ticket.id}`} key={ticket.customer_email}><div><h3>{ticket.customer_name ?? ticket.customer_email}</h3><small>{ticket.customer_email} · last conversation {new Date(ticket.received_at).toLocaleString()}</small></div><div className="ticket-meta"><SeverityBadge severity={priorityToSeverity(ticket.priority)} /><StatusPill tone="info">{formatStatus(ticket.category)}</StatusPill><StatusPill tone="neutral">{formatStatus(ticket.sentiment)}</StatusPill></div></Link>)}</section></div>;
  }}</RealDataFrame>;
}

export function RealIntegrationsPage() {
  return <div className="app-page-grid"><div className="page-title"><span className="eyebrow">Integrations</span><h1>Gmail import and conversation sync</h1><p>Connect Gmail, import support emails, and check recent import jobs from one place.</p></div><GmailConnectionPanel /></div>;
}

export function RealWorkspacePage() {
  return <div className="app-page-grid"><div className="page-title"><span className="eyebrow">Workspace</span><h1>Workspace and organization setup</h1><p>Create an organization, switch workspaces, then connect Gmail for that workspace.</p></div><OrganizationManager /></div>;
}

export function RealTeamPage() {
  return <div className="app-page-grid"><div className="page-title"><span className="eyebrow">Roles</span><h1>Team roles and access</h1><p>Owners can manage owners, admins, and agents. Admins can invite or manage agents. Agents can work tickets and approvals.</p></div><TeamSettings /></div>;
}

export function RealSettingsPage() {
  return <div className="app-page-grid"><div className="page-title"><span className="eyebrow">Settings</span><h1>Workspace controls</h1><p>Use these shortcuts to configure the core pilot workflow.</p></div><div className="metrics-grid"><Link className="panel" href="/app/settings/workspace"><h2>Workspace</h2><p style={{ color: "var(--muted)" }}>Create or switch organizations.</p></Link><Link className="panel" href="/app/integrations"><h2>Gmail import</h2><p style={{ color: "var(--muted)" }}>Connect Gmail and import conversations.</p></Link><Link className="panel" href="/app/team"><h2>Team roles</h2><p style={{ color: "var(--muted)" }}>Invite teammates and manage owner/admin/agent access.</p></Link></div></div>;
}


