import { getApiBaseUrl } from "@/lib/config";
import type { GmailConnection, JobRun, MailImportRule, MeResponse, Organization, Member, OperationsFailureList, OperationsJob, OperationsRetryResult, OrganizationDeletionRequest, OrganizationExport, SyncHealth } from "@/lib/api-types";

function toApiErrorMessage(errorText: string, status: number) {
  try {
    const parsed = JSON.parse(errorText) as { detail?: unknown };
    if (typeof parsed.detail === "string") return parsed.detail;
    if (Array.isArray(parsed.detail)) return parsed.detail.map((item) => { const detailItem = item as { msg?: string }; return detailItem.msg ?? JSON.stringify(item); }).join(", ");
  } catch {
    // Keep the plain response text below.
  }
  return errorText || `Request failed with status ${status}`;
}

async function apiFetch<T>(path: string, accessToken: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
        ...(init.headers ?? {}),
      },
    });
  } catch (error) {
    throw new Error(
      error instanceof TypeError
        ? "Could not reach the API. Check your connection, then refresh and try again."
        : "Request failed before the API could respond.",
    );
  }

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(toApiErrorMessage(errorText, response.status));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

export function getMe(accessToken: string) {
  return apiFetch<MeResponse>("/v1/me", accessToken);
}

export function createOrganization(accessToken: string, name: string) {
  return apiFetch<Organization>("/v1/organizations", accessToken, {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export function getOrganizationExport(accessToken: string, organizationId: string) {
  return apiFetch<OrganizationExport>(`/v1/organizations/${organizationId}/export`, accessToken);
}

export function requestOrganizationDeletion(accessToken: string, organizationId: string, reason: string) {
  return apiFetch<OrganizationDeletionRequest>(`/v1/organizations/${organizationId}/deletion-request`, accessToken, {
    method: "POST",
    body: JSON.stringify({ confirm: true, reason }),
  });
}
export function getGmailConnections(accessToken: string, organizationId: string) {
  return apiFetch<GmailConnection[]>(`/v1/orgs/${organizationId}/gmail/connections`, accessToken);
}


export function updateGmailConnection(accessToken: string, organizationId: string, connectionId: string, payload: { display_name?: string | null; inbox_type?: string; shared_address?: string | null; channel_notes?: string | null }) {
  return apiFetch<GmailConnection>(`/v1/orgs/${organizationId}/gmail/connections/${connectionId}`, accessToken, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function getGmailImportRules(accessToken: string, organizationId: string) {
  return apiFetch<MailImportRule[]>(`/v1/orgs/${organizationId}/gmail/import-rules`, accessToken);
}

export function updateGmailImportRule(
  accessToken: string,
  organizationId: string,
  ruleId: string,
  payload: Partial<Pick<MailImportRule, "support_label_id" | "processed_label_id" | "spam_label_id" | "import_unread_only" | "routing_direction" | "is_active">>,
) {
  return apiFetch<MailImportRule>(`/v1/orgs/${organizationId}/gmail/import-rules/${ruleId}`, accessToken, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}
export function startGmailOAuth(accessToken: string, organizationId: string) {
  return apiFetch<{ auth_url: string; state: string }>(
    `/v1/orgs/${organizationId}/gmail/oauth/start`,
    accessToken,
  );
}

export function syncGmailConnection(accessToken: string, organizationId: string, connectionId: string) {
  return apiFetch<JobRun>(`/v1/orgs/${organizationId}/gmail/connections/${connectionId}/sync`, accessToken, {
    method: "POST",
    body: JSON.stringify({ max_results: 20 }),
  });
}

export function queueGmailSync(accessToken: string, organizationId: string, connectionId: string) {
  return apiFetch<JobRun>(`/v1/orgs/${organizationId}/gmail/connections/${connectionId}/sync/queue`, accessToken, {
    method: "POST",
    body: JSON.stringify({ max_results: 20 }),
  });
}

export function getRecentImports(accessToken: string, organizationId: string) {
  return apiFetch<JobRun[]>(`/v1/orgs/${organizationId}/imports/recent`, accessToken);
}

export function getJobRun(accessToken: string, organizationId: string, jobId: string) {
  return apiFetch<JobRun>(`/v1/orgs/${organizationId}/jobs/${jobId}`, accessToken);
}
export function getOperationsFailures(accessToken: string, organizationId: string, limit = 10) {
  return apiFetch<OperationsFailureList>(`/v1/orgs/${organizationId}/operations/failures?limit=${limit}`, accessToken);
}

export function getSyncHealth(accessToken: string, organizationId: string) {
  return apiFetch<SyncHealth>(`/v1/orgs/${organizationId}/operations/sync-health`, accessToken);
}

export function retryOperationsJob(accessToken: string, organizationId: string, jobId: string) {
  return apiFetch<OperationsRetryResult>(`/v1/orgs/${organizationId}/operations/jobs/${jobId}/retry`, accessToken, {
    method: "POST",
  });
}
export function dismissOperationsJob(accessToken: string, organizationId: string, jobId: string) {
  return apiFetch<OperationsJob>(`/v1/orgs/${organizationId}/operations/jobs/${jobId}/dismiss`, accessToken, {
    method: "POST",
  });
}


export function getMembers(accessToken: string, organizationId: string) {
  return apiFetch<Member[]>(`/v1/orgs/${organizationId}/members`, accessToken);
}

export function inviteMember(accessToken: string, organizationId: string, email: string, role: string) {
  return apiFetch<Member>(`/v1/orgs/${organizationId}/members/invite`, accessToken, {
    method: "POST",
    body: JSON.stringify({ email, role }),
  });
}

export function updateMemberRole(accessToken: string, organizationId: string, memberId: string, role: string) {
  return apiFetch<Member>(`/v1/orgs/${organizationId}/members/${memberId}`, accessToken, {
    method: "PATCH",
    body: JSON.stringify({ role }),
  });
}
export function removeMember(accessToken: string, organizationId: string, memberId: string) {
  return apiFetch<void>(`/v1/orgs/${organizationId}/members/${memberId}`, accessToken, {
    method: "DELETE",
  });
}



