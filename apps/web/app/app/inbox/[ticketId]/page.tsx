import { TicketDetailClient } from "@/features/tickets/components/TicketDetailClient";
export default function Page({ params }: { params: { ticketId: string } }) { return <TicketDetailClient ticketId={params.ticketId} basePath="/app/inbox" />; }


