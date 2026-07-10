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

function SlaBadge({ status }: { status: string }) {
  return <span className={`rounded-md px-2 py-1 text-xs font-medium capitalize ${slaTone[status] ?? "bg-slate-100 text-slate-600"}`}>{status.replaceAll("_", " ")}</span>;
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
                <td className="px-0 py-0 align-stretch"><UrgencyRail priority={ticket.priority} className="h-full min-h-14 rounded-none" /></td>
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
                <td className="px-4 py-3"><TicketPriorityBadge priority={ticket.priority} /></td>
                <td className="px-4 py-3 text-slate-600">{ticket.category.replaceAll("_", " ")}</td>
                <td className="px-4 py-3"><TicketStatusBadge status={ticket.status} /></td>
                <td className="px-4 py-3 font-mono text-xs text-slate-500">{ticket.triage_status?.replaceAll("_", " ") ?? "N/A"}</td>
                <td className="px-4 py-3"><SlaBadge status={ticket.sla_status ?? "on_track"} /></td>
                <td className="px-4 py-3 font-mono text-xs text-slate-500">{new Date(ticket.received_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="divide-y divide-slate-100 md:hidden">
        {tickets.map((ticket) => (
          <div key={ticket.id} className="grid grid-cols-[auto_1fr] gap-3 p-4">
            <UrgencyRail priority={ticket.priority} className="h-full" />
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
                <TicketPriorityBadge priority={ticket.priority} />
                <TicketStatusBadge status={ticket.status} />
                <SlaBadge status={ticket.sla_status ?? "on_track"} />
              </div>
              {ticket.first_review_due_at ? <p className="mt-2 text-xs text-slate-500">Review due {new Date(ticket.first_review_due_at).toLocaleString()}</p> : null}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

