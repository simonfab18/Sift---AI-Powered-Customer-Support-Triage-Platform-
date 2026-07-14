import Link from "next/link";

import { ChartBars, EmptyState, IntegrationCard, MetricCard, SeverityBadge, StatusPill } from "@/components/sift/SiftComponents";
import { activity, automationRules, chartBars, customers, integrations, knowledgeSources, metrics, tickets } from "@/lib/mock-data";

export function OverviewPage() {
  return <div className="app-page-grid"><div className="page-title"><span className="eyebrow">Overview</span><h1>Good afternoon, Simon</h1><p>Here&apos;s what needs attention across your support queue.</p></div><div className="metrics-grid">{metrics.map((m) => <MetricCard key={m.label} {...m} />)}</div><div className="dashboard-grid"><TicketList title="Needs attention now" limit={4} /><ActivityPanel /></div><div className="dashboard-grid"><section className="panel"><h2>Queue health</h2><ChartBars values={chartBars} /></section><section className="panel"><h2>Setup checklist</h2>{["Connect Gmail", "Import conversations", "Invite teammate", "Review first draft"].map((item, index) => <p key={item}><StatusPill tone={index < 2 ? "success" : "neutral"}>{index < 2 ? "done" : "next"}</StatusPill> {item}</p>)}</section></div></div>;
}

export function InboxPage() {
  return <div className="app-page-grid"><div className="page-title"><span className="eyebrow">Inbox</span><h1>Prioritized ticket queue</h1><p>Saved views, filters, sorting, SLA risk, and AI reasoning are visible before agents open a thread.</p></div><section className="panel"><div className="hero-actions" style={{ marginTop: 0 }}><StatusPill tone="critical">Critical</StatusPill><StatusPill tone="warning">SLA risk</StatusPill><StatusPill tone="info">Assigned to me</StatusPill><StatusPill>Unassigned</StatusPill></div></section><TicketList title="All active tickets" /></div>;
}

export function TicketDetailPage({ id = "SFT-1042" }: { id?: string }) {
  const ticket = tickets.find((item) => item.id === id) ?? tickets[0];
  return <div className="app-page-grid"><div className="page-title"><span className="eyebrow">{ticket.id}</span><h1>{ticket.subject}</h1><p>{ticket.customer} at {ticket.company} · {ticket.preview}</p></div><div className="dashboard-grid"><section className="panel"><h2>Conversation</h2><p style={{ color: "var(--muted)", lineHeight: 1.8 }}>Customer reports a time-sensitive issue and needs confirmation before their launch window. Sift keeps the thread, analysis, and suggested reply in one place for review.</p><div className="reply-card"><strong>Suggested reply</strong><p>Thanks for flagging this. I can see the payment issue affected your workspace access. We&apos;ll restore access now, reconcile the charge, and keep this open until you confirm everything is working.</p></div><div className="hero-actions"><Link className="button primary" href="/app/approvals">Approve draft</Link><Link className="button secondary" href="/app/inbox">Back to inbox</Link></div></section><section className="panel"><h2>AI analysis</h2><p><SeverityBadge severity={ticket.severity} /> <StatusPill tone="warning">{ticket.sla}</StatusPill></p><p><strong>Intent</strong><br />{ticket.intent}</p><p><strong>Category</strong><br />{ticket.category}</p><p><strong>Sentiment</strong><br />{ticket.sentiment}</p><p><strong>Confidence</strong><br />{ticket.confidence}%</p></section></div></div>;
}

export function ApprovalsPage() {
  return <div className="app-page-grid"><div className="page-title"><span className="eyebrow">Approvals</span><h1>Review AI suggestions before Gmail drafts are created.</h1><p>Keyboard flow: A approve, E edit, R reject, J/K move through suggestions.</p></div><TicketList title="Waiting for me" limit={3} approvals /></div>;
}

export function AnalyticsPage() {
  return <div className="app-page-grid"><div className="page-title"><span className="eyebrow">Analytics</span><h1>Queue, team, SLA, and AI quality.</h1><p>Metrics are operational indicators, not employee scorecards.</p></div><div className="metrics-grid">{metrics.map((m) => <MetricCard key={m.label} {...m} />)}</div><div className="dashboard-grid"><section className="panel"><h2>Ticket volume over time</h2><ChartBars values={chartBars} /></section><section className="panel"><h2>AI quality</h2>{["Approved without edits 52%", "Approved with edits 35%", "Rejected 13%", "Average confidence 88%"].map((item) => <p key={item}>{item}</p>)}</section></div></div>;
}

export function AutomationPage() {
  return <TablePage eyebrow="Automation" title="Rules that keep triage consistent" headers={["Rule", "Trigger", "Conditions", "Action", "Status", "Last run"]} rows={automationRules.map((r) => [r.name, r.trigger, r.conditions, r.action, r.status, r.lastRun])} />;
}

export function KnowledgePage() {
  return <div className="app-page-grid"><div className="page-title"><span className="eyebrow">Knowledge</span><h1>Improve response accuracy.</h1><p>Sync sources, inspect usage, and find low-confidence gaps.</p></div><div className="metrics-grid">{knowledgeSources.map((source) => <article className="panel" key={source.name}><h3>{source.name}</h3><p><StatusPill tone={source.status === "Synced" ? "success" : source.status === "Processing" ? "info" : "warning"}>{source.status}</StatusPill></p><p style={{ color: "var(--muted)" }}>{source.usage} · {source.gaps} gaps</p></article>)}</div></div>;
}

export function CustomersPage() {
  return <TablePage eyebrow="Customers" title="Customer context directory" headers={["Customer", "Company", "Tier", "Open tickets", "Last contact", "Sentiment", "Health"]} rows={customers.map((c) => [c.name, c.company, c.tier, String(c.open), c.last, c.sentiment, c.health])} />;
}

export function TeamPage() {
  return <TablePage eyebrow="Team" title="Roles and access" headers={["Member", "Role", "Status", "Assigned tickets", "Last active"]} rows={[["Simon", "Owner", "Active", "8", "Now"], ["Ari", "Admin", "Active", "12", "8m ago"], ["Jamie", "Agent", "Invited", "0", "Pending"], ["Morgan", "Viewer", "Active", "3", "1h ago"]]} />;
}

export function IntegrationsPage() {
  return <div className="app-page-grid"><div className="page-title"><span className="eyebrow">Integrations</span><h1>Connect support tools.</h1><p>Gmail is supported now. Planned integrations are clearly labeled coming soon.</p></div><div className="metrics-grid">{integrations.map((item) => <IntegrationCard key={item.name} {...item} />)}</div></div>;
}

export function SettingsPage({ section = "Workspace" }: { section?: string }) {
  return <div className="app-page-grid"><div className="page-title"><span className="eyebrow">Settings</span><h1>{section}</h1><p>Focused controls for workspace, roles, billing, security, notifications, and AI response policies.</p></div><section className="panel"><div className="option-grid">{["Workspace name", "Timezone", "Support hours", "Approval policy", "Retention", "Default assignee"].map((item) => <label className="field" key={item}>{item}<input className="input" placeholder={item} /></label>)}</div><div className="hero-actions"><button className="button primary">Save changes</button><button className="button secondary">Reset</button></div></section></div>;
}

function TicketList({ title, limit = tickets.length, approvals = false }: { title: string; limit?: number; approvals?: boolean }) {
  const list = tickets.slice(0, limit);
  if (!list.length) return <EmptyState title="No conversations yet" body="Connect Gmail or import sample conversations to see Sift prioritize your support queue." action="Connect Gmail" href="/app/integrations" />;
  return <section className="ticket-list"><div style={{ padding: 18, borderBottom: "1px solid var(--border)" }}><h2 style={{ margin: 0 }}>{title}</h2></div>{list.map((ticket) => <Link className="ticket-row" href={`/app/inbox/${ticket.id}`} key={ticket.id}><div><h3>{ticket.subject}</h3><small>{ticket.customer} · {ticket.company} · {ticket.preview}</small></div><div className="ticket-meta"><SeverityBadge severity={ticket.severity} /><StatusPill tone="info">{ticket.category}</StatusPill><StatusPill tone="warning">{ticket.sla}</StatusPill>{approvals ? <StatusPill tone="success">Approve</StatusPill> : null}</div></Link>)}</section>;
}

function ActivityPanel() {
  return <section className="panel"><h2>Recent activity</h2>{activity.map((item) => <p key={item} style={{ borderTop: "1px solid var(--border)", paddingTop: 12 }}>{item}</p>)}</section>;
}

function TablePage({ eyebrow, title, headers, rows }: { eyebrow: string; title: string; headers: string[]; rows: string[][] }) {
  return <div className="app-page-grid"><div className="page-title"><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>Designed states, clear status, and operational actions are ready for backend wiring.</p></div><table className="table"><thead><tr>{headers.map((h) => <th key={h}>{h}</th>)}</tr></thead><tbody>{rows.map((row, i) => <tr key={i}>{row.map((cell) => <td key={cell}>{cell}</td>)}</tr>)}</tbody></table></div>;
}
