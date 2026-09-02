import { TicketDetailClient } from "@/features/tickets/components/TicketDetailClient";

export default function TicketDetailPage({ params }: { params: { ticketId: string } }) {
  return <TicketDetailClient ticketId={params.ticketId} />;
}

