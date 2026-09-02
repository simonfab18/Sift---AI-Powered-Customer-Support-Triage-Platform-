import { StatusBadge } from "@/components/ui/Badges";

export function TicketStatusBadge({ status }: { status: string }) {
  return <StatusBadge status={status} />;
}


