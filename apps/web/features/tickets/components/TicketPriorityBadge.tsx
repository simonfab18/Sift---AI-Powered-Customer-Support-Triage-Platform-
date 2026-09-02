import { UrgencyBadge } from "@/components/ui/Badges";

export function TicketPriorityBadge({ priority }: { priority: string }) {
  return <UrgencyBadge priority={priority} />;
}


