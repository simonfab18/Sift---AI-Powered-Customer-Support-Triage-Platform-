import Link from "next/link";

import { UrgencyRail } from "@/components/ui/Badges";
import { TicketPriorityBadge } from "./TicketPriorityBadge";
import { TicketStatusBadge } from "./TicketStatusBadge";
import type { TicketListItem } from "../types";

const slaTone: Record<string, string> = {
  on_track: "bg-slate-100 text-slate-700",
  warning: "bg-white/50 text-[#746d80]",
  breached: "bg-white/50 text-[#6f6174]",
  paused: "bg-slate-100 text-slate-600",
};

function sourceTypeLabel(value?: string | null) {
  if (value === "google_group") return "Group";
  if (value === "shared_mailbox") return "Shared";
  return "Inbox";
}

function SourceInboxBadge({ ticket }: { ticket: TicketListItem }) {
  const label = ticket.gmail_connection_display_name || ticket.gmail_connection_email;
  if (!label) return <span className="text-xs text-slate-400">Manual</span>;
  return (
    <span className="inline-flex flex-col gap-1 rounded-md border border-[#ddd7e6] bg-white/50 px-2 py-1 text-xs font-semibold text-[#5f5a70]">
      <span>{label}</span>
      <span className="font-normal text-[#817b8d]">{sourceTypeLabel(ticket.gmail_connection_inbox_type)}{ticket.gmail_connection_shared_address ? ` / ${ticket.gmail_connection_shared_address}` : ""}</span>
    </span>
  );
}

function slaTarget(ticket: TicketListItem) {
  const targets = [
    { label: "First review", value: ticket.first_review_due_at },
    { label: "Resolution", value: ticket.resolution_due_at },
  ]
    .map((target) => ({ ...target, date: target.value ? new Date(target.value) : null }))
    .filter((target): target is { label: string; value: string; date: Date } => Boolean(target.value && target.date && !Number.isNaN(target.date.getTime())))
    .sort((first, second) => first.date.getTime() - second.date.getTime());
  return targets[0] ?? null;
}

function relativeDue(value?: string | null) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  const diffMs = date.getTime() - Date.now();
  const absMinutes = Math.max(1, Math.round(Math.abs(diffMs) / 60000));
  const hours = Math.floor(absMinutes / 60);
  const minutes = absMinutes % 60;
  const compact = hours > 0 ? `${hours}h${minutes ? ` ${minutes}m` : ""}` : `${minutes}m`;
  return diffMs < 0 ? `overdue by ${compact}` : `due in ${compact}`;
}

function slaLabel(ticket: TicketListItem) {
  if (ticket.sla_status === "paused") return "Paused";
  const target = slaTarget(ticket);
  if (!target) return ticket.sla_status.replaceAll("_", " ");
  if (ticket.sla_status === "breached") return `${target.label} breached`;
  if (ticket.sla_status === "warning") return `${target.label} at risk`;
  return `${target.label} on track`;
}
function formatDue(value?: string | null) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function slaDetail(ticket: TicketListItem) {
  if (ticket.sla_status === "paused") return "Timer paused because the ticket is pending, resolved, or spam.";
  const target = slaTarget(ticket);
  if (!target) return "No SLA target set.";
  const due = formatDue(target.value);
  const relative = relativeDue(target.value);
  if (ticket.sla_status === "breached") return `${target.label} was due ${due}${relative ? ` (${relative})` : ""}.`;
  if (ticket.sla_status === "warning") return `${target.label} is due soon: ${due}${relative ? ` (${relative})` : ""}.`;
  return `${target.label} due ${due}${relative ? ` (${relative})` : ""}.`;
}

function SlaBadge({ ticket }: { ticket: TicketListItem }) {
  const status = ticket.sla_status ?? "on_track";
  return (
    <span className={`inline-flex max-w-44 flex-col rounded-md px-2 py-1 text-xs font-medium capitalize ${slaTone[status] ?? "bg-slate-100 text-slate-600"}`} title={slaDetail(ticket)}>
      <span>{slaLabel(ticket)}</span>
      <span className="mt-0.5 truncate font-normal normal-case opacity-80">{ticket.sla_status === "paused" ? "No active timer" : relativeDue(slaTarget(ticket)?.value) ?? slaDetail(ticket)}</span>
    </span>
  );
}

function TicketWorkflowStatusBadge({ ticket }: { ticket: TicketListItem }) {
  if (ticket.latest_reply_status === "approved" && !ticket.latest_reply_gmail_draft_id) {
    return (
      <span className="inline-flex flex-col rounded-md border border-[#ddd7e6] bg-white/50 px-2 py-1 text-xs font-semibold text-[#655f73]" title="Reply is approved. Create a Gmail draft when ready.">
        <span>Reply approved</span>
        <span className="mt-0.5 font-normal">Draft not created</span>
      </span>
    );
  }
  return <TicketStatusBadge status={ticket.status} />;
}

function triageState(ticket: TicketListItem) {
  const status = ticket.triage_status;
  const error = ticket.triage_error_message?.toLowerCase() ?? "";
  if (status === "triaged") return { label: "Triaged", className: "border-slate-200 bg-slate-100 text-slate-700", detail: null as string | null };
  if (status === "queued") return { label: "Queued", className: "border-[#ddd7e6] bg-white/50 text-[#655f73]", detail: null as string | null };
  if (status === "triaging") return { label: "Running", className: "border-[#ddd7e6] bg-white/50 text-[#655f73]", detail: null as string | null };
  if (status === "triage_failed") {
    const quota = error.includes("quota") || error.includes("free gemini") || error.includes("too_many_requests") || error.includes("prepayment credits");
    return {
      label: quota ? "AI paused" : "Retry needed",
      className: quota ? "border-[#ddd7e6] bg-white/50 text-[#746d80]" : "border-[#d8d2e4] bg-white/50 text-[#6f6174]",
      detail: ticket.triage_error_message,
    };
  }
  return { label: status?.replaceAll("_", " ") || "Not queued", className: "border-slate-200 bg-white/30 text-slate-600", detail: null as string | null };
}

function hasAiClassification(ticket: TicketListItem) {
  return ticket.triage_status === "triaged";
}

function NotClassifiedBadge() {
  return <span className="inline-flex rounded-md border border-slate-200 bg-white/30 px-2 py-1 text-xs font-medium text-slate-600">Not classified</span>;
}

function ClassificationRail({ ticket, className }: { ticket: TicketListItem; className?: string }) {
  if (hasAiClassification(ticket)) return <UrgencyRail priority={ticket.priority} className={className} />;
  return <span className={`block w-1.5 bg-slate-200 ${className ?? ""}`} aria-hidden="true" />;
}

function TicketClassification({ ticket, type }: { ticket: TicketListItem; type: "priority" | "category" }) {
  if (!hasAiClassification(ticket)) return <NotClassifiedBadge />;
  if (type === "priority") return <TicketPriorityBadge priority={ticket.priority} />;
  return <>{ticket.category.replaceAll("_", " ")}</>;
}

function TriageStateBadge({ ticket }: { ticket: TicketListItem }) {
  const state = triageState(ticket);
  return (
    <span className={`inline-flex max-w-44 flex-col rounded-md border px-2 py-1 text-xs font-medium capitalize ${state.className}`} title={state.detail ?? undefined}>
      <span>{state.label}</span>
      {state.detail ? <span className="mt-1 truncate font-normal normal-case opacity-80">{state.detail}</span> : null}
    </span>
  );
}

type TicketListProps = {
  tickets: TicketListItem[];
  selectedIds?: Set<string>;
  onToggleSelection?: (ticketId: string) => void;
};

export function TicketList({ tickets, selectedIds, onToggleSelection }: TicketListProps) {
  if (tickets.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 bg-white/60 p-8 shadow-[0_18px_48px_rgba(72,60,96,0.075)] backdrop-blur-xl">
        <h2 className="font-display text-lg font-semibold text-slate-950">Nothing waiting on you</h2>
        <p className="mt-2 text-sm text-slate-600">The active queue is clear. Check back after the next Gmail import or triage run.</p>
      </div>
    );
  }

  const selectable = Boolean(onToggleSelection && selectedIds);

  return (
    <div className="overflow-hidden rounded-lg border border-white/50 bg-white/60 backdrop-blur-xl shadow-[0_18px_48px_rgba(72,60,96,0.075)]">
      <div className="hidden md:block">
        <table className="w-full border-collapse text-left text-sm">
          <thead className="border-b border-slate-200 bg-white/30 text-[11px] uppercase tracking-[0.08em] text-slate-500">
            <tr>
              <th className="w-3 px-0 py-3" />
              {selectable ? <th className="w-10 px-3 py-3">Select</th> : null}
              <th className="px-4 py-3">Subject</th>
              <th className="px-4 py-3">Sender</th>
              <th className="px-4 py-3">Inbox</th>
              <th className="px-4 py-3">Urgency</th>
              <th className="px-4 py-3">Category</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">AI state</th>
              <th className="px-4 py-3">SLA</th>
              <th className="px-4 py-3">Received</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#eee9f2]">
            {tickets.map((ticket) => (
              <tr key={ticket.id} className="transition hover:bg-white/30">
                <td className="px-0 py-0 align-stretch"><ClassificationRail ticket={ticket} className="h-full min-h-14 rounded-none" /></td>
                {selectable ? (
                  <td className="px-3 py-3">
                    <input
                      aria-label={`Select ${ticket.subject}`}
                      checked={selectedIds?.has(ticket.id) ?? false}
                      onChange={() => onToggleSelection?.(ticket.id)}
                      type="checkbox"
                      className="h-4 w-4 rounded border-slate-300"
                    />
                  </td>
                ) : null}
                <td className="px-4 py-3 font-semibold text-slate-950"><Link href={`/dashboard/tickets/${ticket.id}`}>{ticket.subject}</Link></td>
                <td className="px-4 py-3 text-slate-600">{ticket.customer_name ?? ticket.customer_email}</td>
                <td className="px-4 py-3"><SourceInboxBadge ticket={ticket} /></td>
                <td className="px-4 py-3"><TicketClassification ticket={ticket} type="priority" /></td>
                <td className="px-4 py-3 text-slate-600"><TicketClassification ticket={ticket} type="category" /></td>
                <td className="px-4 py-3"><TicketWorkflowStatusBadge ticket={ticket} /></td>
                <td className="px-4 py-3"><TriageStateBadge ticket={ticket} /></td>
                <td className="px-4 py-3"><SlaBadge ticket={ticket} /></td>
                <td className="px-4 py-3 font-mono text-xs text-slate-500">{new Date(ticket.received_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="divide-y divide-[#eee9f2] md:hidden">
        {tickets.map((ticket) => (
          <div key={ticket.id} className="grid grid-cols-[auto_1fr] gap-3 p-4">
            <ClassificationRail ticket={ticket} className="h-full rounded-full" />
            <div>
              <div className="flex items-start gap-3">
                {selectable ? (
                  <input
                    aria-label={`Select ${ticket.subject}`}
                    checked={selectedIds?.has(ticket.id) ?? false}
                    onChange={() => onToggleSelection?.(ticket.id)}
                    type="checkbox"
                    className="mt-1 h-4 w-4 rounded border-slate-300"
                  />
                ) : null}
                <div>
                  <Link href={`/dashboard/tickets/${ticket.id}`} className="font-semibold text-slate-950">{ticket.subject}</Link>
                  <p className="mt-1 text-sm text-slate-500">{ticket.customer_name ?? ticket.customer_email}</p>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <TicketClassification ticket={ticket} type="priority" />
                <TicketWorkflowStatusBadge ticket={ticket} />
                <SlaBadge ticket={ticket} />
                <TriageStateBadge ticket={ticket} />
              </div>
              {slaTarget(ticket) ? <p className="mt-2 text-xs text-slate-500">{slaLabel(ticket)}: {slaDetail(ticket)}</p> : null}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}






