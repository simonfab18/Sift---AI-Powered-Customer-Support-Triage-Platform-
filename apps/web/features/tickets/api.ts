import type {
  AITriageResult,
  BulkActionResponse,
  CollaborationLock,
  GmailDraftCreateResponse,
  InternalNote,
  InternalNoteEdit,
  InternalNoteMention,
  MetricsOverview,
  ReplySuggestion,
  ResponseTemplate,
  SavedView,
  TemplateInsertResult,
  Ticket,
  TicketEvent,
  TicketListItem,
} from "./types";

function getApiBaseUrl() {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
}

function toTicketApiError(errorText: string, status: number) {
  try {
    const parsed = JSON.parse(errorText) as { detail?: unknown };
    if (typeof parsed.detail === "string") return parsed.detail;
    if (Array.isArray(parsed.detail)) {
      return parsed.detail
        .map((item) => {
          const detailItem = item as { msg?: string };
          return detailItem.msg ?? JSON.stringify(item);
        })
        .join(", ");
    }
  } catch {
    // Keep the plain response text below.
  }
  return errorText || `Request failed with status ${status}`;
}

async function ticketApiFetch<T>(path: string, accessToken: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
      ...(init.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(toTicketApiError(errorText, response.status));
  }

  if (response.status === 204) return undefined as T;
  return response.json();
}

export async function getMetricsOverview(organizationId: string, accessToken: string): Promise<MetricsOverview> {
  return ticketApiFetch<MetricsOverview>(`/v1/orgs/${organizationId}/metrics/overview`, accessToken);
}

export async function getTickets(organizationId: string, accessToken: string): Promise<TicketListItem[]> {
  return ticketApiFetch<TicketListItem[]>(`/v1/orgs/${organizationId}/tickets`, accessToken);
}

export async function getTicket(organizationId: string, ticketId: string, accessToken: string): Promise<Ticket> {
  return ticketApiFetch<Ticket>(`/v1/orgs/${organizationId}/tickets/${ticketId}`, accessToken);
}

export async function getTicketEvents(organizationId: string, ticketId: string, accessToken: string): Promise<TicketEvent[]> {
  return ticketApiFetch<TicketEvent[]>(`/v1/orgs/${organizationId}/tickets/${ticketId}/events`, accessToken);
}

export async function runTicketTriage(organizationId: string, ticketId: string, accessToken: string): Promise<AITriageResult> {
  return ticketApiFetch<AITriageResult>(`/v1/orgs/${organizationId}/tickets/${ticketId}/triage`, accessToken, { method: "POST" });
}

export async function getTicketTriageResults(organizationId: string, ticketId: string, accessToken: string): Promise<AITriageResult[]> {
  return ticketApiFetch<AITriageResult[]>(`/v1/orgs/${organizationId}/tickets/${ticketId}/triage-results`, accessToken);
}

export async function getReplySuggestions(organizationId: string, ticketId: string, accessToken: string): Promise<ReplySuggestion[]> {
  return ticketApiFetch<ReplySuggestion[]>(`/v1/orgs/${organizationId}/tickets/${ticketId}/reply-suggestions`, accessToken);
}

export async function updateReplySuggestion(
  organizationId: string,
  suggestionId: string,
  accessToken: string,
  editedBody: string,
): Promise<ReplySuggestion> {
  return ticketApiFetch<ReplySuggestion>(`/v1/orgs/${organizationId}/reply-suggestions/${suggestionId}`, accessToken, {
    method: "PATCH",
    body: JSON.stringify({ edited_body: editedBody }),
  });
}

export async function approveReplySuggestion(organizationId: string, suggestionId: string, accessToken: string): Promise<ReplySuggestion> {
  return ticketApiFetch<ReplySuggestion>(`/v1/orgs/${organizationId}/reply-suggestions/${suggestionId}/approve`, accessToken, { method: "POST" });
}

export async function rejectReplySuggestion(organizationId: string, suggestionId: string, accessToken: string): Promise<ReplySuggestion> {
  return ticketApiFetch<ReplySuggestion>(`/v1/orgs/${organizationId}/reply-suggestions/${suggestionId}/reject`, accessToken, { method: "POST" });
}

export async function createGmailDraftFromSuggestion(
  organizationId: string,
  suggestionId: string,
  accessToken: string,
): Promise<GmailDraftCreateResponse> {
  return ticketApiFetch<GmailDraftCreateResponse>(
    `/v1/orgs/${organizationId}/reply-suggestions/${suggestionId}/create-gmail-draft`,
    accessToken,
    { method: "POST" },
  );
}

export async function getSavedViews(organizationId: string, accessToken: string): Promise<SavedView[]> {
  return ticketApiFetch<SavedView[]>(`/v1/orgs/${organizationId}/saved-views`, accessToken);
}

export async function createSavedView(
  organizationId: string,
  accessToken: string,
  name: string,
  filters: Record<string, string>,
): Promise<SavedView> {
  return ticketApiFetch<SavedView>(`/v1/orgs/${organizationId}/saved-views`, accessToken, {
    method: "POST",
    body: JSON.stringify({ name, filters }),
  });
}

export async function deleteSavedView(organizationId: string, accessToken: string, viewId: string): Promise<void> {
  return ticketApiFetch<void>(`/v1/orgs/${organizationId}/saved-views/${viewId}`, accessToken, { method: "DELETE" });
}

export async function runBulkTicketAction(
  organizationId: string,
  accessToken: string,
  payload: {
    ticket_ids: string[];
    action: string;
    assigned_to_user_id?: string | null;
    status?: string | null;
    confirm?: boolean;
  },
): Promise<BulkActionResponse> {
  return ticketApiFetch<BulkActionResponse>(`/v1/orgs/${organizationId}/tickets/bulk-actions`, accessToken, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getResponseTemplates(
  organizationId: string,
  accessToken: string,
  search = "",
): Promise<ResponseTemplate[]> {
  const query = search.trim() ? `?search=${encodeURIComponent(search.trim())}` : "";
  return ticketApiFetch<ResponseTemplate[]>(`/v1/orgs/${organizationId}/response-templates${query}`, accessToken);
}

export async function insertResponseTemplate(
  organizationId: string,
  accessToken: string,
  templateId: string,
  ticketId: string,
): Promise<TemplateInsertResult> {
  return ticketApiFetch<TemplateInsertResult>(`/v1/orgs/${organizationId}/response-templates/${templateId}/insert`, accessToken, {
    method: "POST",
    body: JSON.stringify({ ticket_id: ticketId }),
  });
}

export async function getInternalNotes(organizationId: string, ticketId: string, accessToken: string): Promise<InternalNote[]> {
  return ticketApiFetch<InternalNote[]>(`/v1/orgs/${organizationId}/tickets/${ticketId}/internal-notes`, accessToken);
}

export async function createInternalNote(
  organizationId: string,
  ticketId: string,
  accessToken: string,
  body: string,
): Promise<InternalNote> {
  return ticketApiFetch<InternalNote>(`/v1/orgs/${organizationId}/tickets/${ticketId}/internal-notes`, accessToken, {
    method: "POST",
    body: JSON.stringify({ body }),
  });
}

export async function updateInternalNote(
  organizationId: string,
  noteId: string,
  accessToken: string,
  body: string,
): Promise<InternalNote> {
  return ticketApiFetch<InternalNote>(`/v1/orgs/${organizationId}/internal-notes/${noteId}`, accessToken, {
    method: "PATCH",
    body: JSON.stringify({ body }),
  });
}

export async function getInternalNoteEdits(organizationId: string, noteId: string, accessToken: string): Promise<InternalNoteEdit[]> {
  return ticketApiFetch<InternalNoteEdit[]>(`/v1/orgs/${organizationId}/internal-notes/${noteId}/edits`, accessToken);
}

export async function getInternalNoteMentions(organizationId: string, noteId: string, accessToken: string): Promise<InternalNoteMention[]> {
  return ticketApiFetch<InternalNoteMention[]>(`/v1/orgs/${organizationId}/internal-notes/${noteId}/mentions`, accessToken);
}

export async function acquireCollaborationLock(
  organizationId: string,
  accessToken: string,
  payload: { ticket_id: string; resource_type: string; resource_id: string; ttl_seconds?: number },
): Promise<CollaborationLock> {
  return ticketApiFetch<CollaborationLock>(`/v1/orgs/${organizationId}/collaboration-locks`, accessToken, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function releaseCollaborationLock(organizationId: string, accessToken: string, lockId: string): Promise<void> {
  return ticketApiFetch<void>(`/v1/orgs/${organizationId}/collaboration-locks/${lockId}`, accessToken, { method: "DELETE" });
}
