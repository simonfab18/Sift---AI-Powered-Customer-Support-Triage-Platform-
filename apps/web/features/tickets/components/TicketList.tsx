import Link from "next/link";

import { UrgencyRail } from "@/components/ui/Badges";
import { TicketPriorityBadge } from "./TicketPriorityBadge";
import { TicketStatusBadge } from "./TicketStatusBadge";
import type { TicketListItem } from "../types";

const slaTone: Record<string, string> = {
  on_track: "bg-teal-50 text-teal-700",
  warning: "bg-amber-50 text-amber-700",
  breached: "bg-rose-50 text-rose-700",
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
    <span className="inline-flex flex-col gap-1 rounded-md bg-sky-50 px-2 py-1 text-xs font-medium text-sky-700">
      <span>{label}</span>
      <span className="font-normal text-sky-600">{sourceTypeLabel(ticket.gmail_connection_inbox_type)}{ticket.gmail_connection_shared_address ? ` / ${ticket.gmail_connection_shared_address}` : ""}</span>
    </span>
  );
}

function formatDue(value?: string | null) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function slaDetail(ticket: TicketListItem) {
  const reviewDue = formatDue(ticket.first_review_due_at);
  const resolutionDue = formatDue(ticket.resolution_due_at);
  if (ticket.sla_status === "paused") return "Paused because the ticket is pending, resolved, or spam.";
  if (ticket.sla_status === "breached") return reviewDue ? `First review was due ${reviewDue}.` : resolutionDue ? `Resolution was due ${resolutionDue}.` : "SLA target has passed.";
  if (ticket.sla_status === "warning") return reviewDue ? `First review due soon: ${reviewDue}.` : resolutionDue ? `Resolution due soon: ${resolutionDue}.` : "SLA target is close.";
  return reviewDue ? `First review due ${reviewDue}.` : resolutionDue ? `Resolution due ${resolutionDue}.` : "No SLA target set.";
}

function SlaBadge({ ticket }: { ticket: TicketListItem }) {
  const status = ticket.sla_status ?? "on_track";
  return (
    <span className={`inline-flex max-w-44 flex-col rounded-md px-2 py-1 text-xs font-medium capitalize ${slaTone[status] ?? "bg-slate-100 text-slate-600"}`} title={slaDetail(ticket)}>
      <span>{status.replaceAll("_", " ")}</span>
      <span className="mt-0.5 truncate font-normal normal-case opacity-80">{slaDetail(ticket)}</span>
    </span>
  );
}

function TicketWorkflowStatusBadge({ ticket }: { ticket: TicketListItem }) {
  if (ticket.latest_reply_status === "approved" && !ticket.latest_reply_gmail_draft_id) {
    return (
      <span className="inline-flex flex-col rounded-md border border-sky-200 bg-sky-50 px-2 py-1 text-xs font-medium text-sky-800" title="Reply is approved. Create a Gmail draft when ready.">
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
  if (status === "triaged") return { label: "Triaged", className: "border-teal-200 bg-teal-50 text-teal-700", detail: null as string | null };
  if (status === "queued") return { label: "Queued", className: "border-sky-200 bg-sky-50 text-sky-700", detail: null as string | null };
  if (status === "triaging") return { label: "Running", className: "border-sky-200 bg-sky-50 text-sky-700", detail: null as string | null };
  if (status === "triage_failed") {
    const quota = error.includes("quota") || error.includes("free gemini") || error.includes("too_many_requests") || error.includes("prepayment credits");
    return {
      label: quota ? "AI paused" : "Retry needed",
      className: quota ? "border-amber-200 bg-amber-50 text-amber-800" : "border-rose-200 bg-rose-50 text-rose-700",
      detail: ticket.triage_error_message,
    };
  }
  return { label: status?.replaceAll("_", " ") || "Not queued", className: "border-slate-200 bg-slate-50 text-slate-600", detail: null as string | null };
}

function hasAiClassification(ticket: TicketListItem) {
  return ticket.triage_status === "triaged";
}

function NotClassifiedBadge() {
  return <span className="inline-flex rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-xs font-medium text-slate-600">Not classified</span>;
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
      <div className="rounded-lg border border-dashed border-slate-300 bg-white p-8">
        <h2 className="font-display text-lg font-semibold">Nothing waiting on you</h2>
        <p className="mt-2 text-sm text-slate-600">The active queue is clear. Check back after the next Gmail import or triage run.</p>
      </div>
    );
  }

  const selectable = Boolean(onToggleSelection && selectedIds);

  return (
    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
      <div className="hidden md:block">
        <table className="w-full border-collapse text-left text-sm">
          <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
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
          <tbody className="divide-y divide-slate-100">
            {tickets.map((ticket) => (
              <tr key={ticket.id} className="hover:bg-slate-50">
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
                <td className="px-4 py-3 font-medium text-slate-900"><Link href={`/dashboard/tickets/${ticket.id}`}>{ticket.subject}</Link></td>
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

      <div className="divide-y divide-slate-100 md:hidden">
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
                  <Link href={`/dashboard/tickets/${ticket.id}`} className="font-medium text-slate-900">{ticket.subject}</Link>
                  <p className="mt-1 text-sm text-slate-500">{ticket.customer_name ?? ticket.customer_email}</p>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <TicketClassification ticket={ticket} type="priority" />
                <TicketWorkflowStatusBadge ticket={ticket} />
                <SlaBadge ticket={ticket} />
                <TriageStateBadge ticket={ticket} />
              </div>
              {ticket.first_review_due_at ? <p className="mt-2 text-xs text-slate-500">Review due {new Date(ticket.first_review_due_at).toLocaleString()}</p> : null}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
