export type Organization = {
  id: string;
  name: string;
  slug: string;
  role: string;
  joined_via_invite?: boolean;
};

export type MeResponse = {
  id: string;
  email: string | null;
  organizations: Organization[];
};

export type GmailConnection = {
  id: string;
  organization_id: string;
  connected_by_user_id: string;
  gmail_email: string;
  display_name: string | null;
  inbox_type: string;
  shared_address: string | null;
  channel_notes: string | null;
  google_account_id: string;
  scopes: string;
  status: string;
  token_key_version?: number;
  reauthorization_required_at?: string | null;
  reauthorization_reason?: string | null;
  last_token_error_at?: string | null;
  last_sync_at: string | null;
  gmail_history_id?: string | null;
  watch_expires_at?: string | null;
  last_notification_at?: string | null;
  last_sync_started_at?: string | null;
  last_successful_sync_at?: string | null;
  sync_status?: string;
  sync_error_code?: string | null;
  sync_error_message?: string | null;
  consecutive_sync_failures?: number;
  watch_status?: string;
  watch_error?: string | null;
  disconnected_at?: string | null;
  sync_lock_expires_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type JobRun = {
  id: string;
  organization_id: string;
  job_type: string;
  status: string;
  error_message: string | null;
  error_code?: string | null;
  retryable?: boolean;
  next_retry_at?: string | null;
  duration_ms?: number | null;
  attempts?: number;
  max_attempts?: number;
  job_metadata: Record<string, unknown>;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
};

export type OperationsJob = {
  id: string;
  organization_id: string;
  job_type: string;
  queue_name: string;
  status: string;
  attempts: number;
  max_attempts: number;
  retryable: boolean;
  correlation_id: string | null;
  related_resource_type: string | null;
  related_resource_id: string | null;
  error_class: string | null;
  error_code: string | null;
  error_message: string | null;
  next_retry_at: string | null;
  duration_ms: number | null;
  alert_owner: string | null;
  runbook_url: string | null;
  job_metadata: Record<string, unknown>;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
};

export type OperationsFailureList = {
  jobs: OperationsJob[];
};

export type OperationsRetryResult = {
  original_job: OperationsJob;
  retry_job: OperationsJob;
};

export type SyncConnectionHealth = {
  connection_id: string;
  gmail_email: string;
  status: string;
  sync_status: string | null;
  watch_status: string | null;
  consecutive_sync_failures: number;
  last_successful_sync_at: string | null;
  last_sync_started_at: string | null;
  sync_error_code: string | null;
  sync_error_message: string | null;
  degraded: boolean;
};

export type SyncHealth = {
  active_connections: number;
  degraded_connections: number;
  disconnected_connections: number;
  stale_connections: number;
  connections: SyncConnectionHealth[];
};
export type Member = {
  id: string;
  organization_id: string;
  user_id: string;
  email: string;
  role: string;
  status: string;
  created_at: string;
  invite_email_delivery_status?: string | null;
  invite_email_delivery_detail?: string | null;
  invite_url?: string | null;
  ticket_counts?: Record<string, number>;
};
export type MailImportRule = {
  id: string;
  organization_id: string;
  gmail_connection_id: string;
  support_label_id: string | null;
  processed_label_id: string | null;
  spam_label_id: string | null;
  import_unread_only: boolean;
  routing_direction: string;
  is_active: boolean;
  created_at: string;
};

export type OrganizationExport = {
  organization: Record<string, unknown>;
  generated_at: string;
  generated_by_user_id: string;
  counts: Record<string, number>;
  workspace_settings: Record<string, unknown> | null;
  members: Record<string, unknown>[];
  gmail_connections: Record<string, unknown>[];
  customers: Record<string, unknown>[];
  tickets: Record<string, unknown>[];
  attachments: Record<string, unknown>[];
  reply_approvals: Record<string, unknown>[];
  audit_logs: Record<string, unknown>[];
};

export type OrganizationDeletionRequest = {
  organization_id: string;
  status: string;
  requested_by_user_id: string;
  requested_at: string;
  sync_paused: boolean;
  auto_triage_paused: boolean;
  draft_creation_paused: boolean;
};
