export type Organization = {
  id: string;
  name: string;
  slug: string;
  role: string;
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
  job_metadata: Record<string, unknown>;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
};

export type Member = {
  id: string;
  organization_id: string;
  user_id: string;
  email: string;
  role: string;
  status: string;
  created_at: string;
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
