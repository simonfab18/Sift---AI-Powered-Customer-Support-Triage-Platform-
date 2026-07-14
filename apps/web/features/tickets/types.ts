export type TicketListItem = {
  id: string;
  customer_email: string;
  customer_name: string | null;
  gmail_connection_id: string | null;
  gmail_connection_email: string | null;
  gmail_connection_display_name: string | null;
  gmail_connection_inbox_type: string | null;
  gmail_connection_shared_address: string | null;
  gmail_message_id: string | null;
  gmail_thread_id: string | null;
  subject: string;
  status: string;
  category: string;
  priority: string;
  sentiment: string;
  assigned_to_user_id: string | null;
  triage_status: string;
  triage_error_message: string | null;
  first_review_due_at: string | null;
  resolution_due_at: string | null;
  sla_status: string;
  received_at: string;
  updated_at: string;
};

export type TicketAttachment = {
  id: string;
  gmail_connection_id: string | null;
  gmail_message_id: string | null;
  gmail_attachment_id: string | null;
  filename: string | null;
  mime_type: string | null;
  size_bytes: number | null;
  content_disposition: string | null;
  is_inline: boolean;
  policy_status: string;
  storage_status: string;
  scan_status: string;
  stored_at: string | null;
  notes: string | null;
  created_at: string;
};

export type Ticket = TicketListItem & {
  organization_id: string;
  customer_id: string;
  customer: {
    id: string;
    email: string;
    name: string | null;
  };
  message_text: string;
  message_html: string | null;
  active_triage_job_id: string | null;
  triage_attempts: number;
  last_triage_started_at: string | null;
  last_triage_completed_at: string | null;
  created_at: string;
  attachments: TicketAttachment[];
};


export type AttachmentDownloadUrlResponse = {
  attachment_id: string;
  download_url: string;
  expires_in_seconds: number;
};
export type TicketEvent = {
  id: string;
  organization_id: string;
  ticket_id: string;
  actor_user_id: string | null;
  event_type: string;
  event_metadata: Record<string, unknown>;
  created_at: string;
};

export type KnowledgeReference = {
  id: string;
  title: string;
  source_type: string;
  score: number;
  matched_terms: string[];
  excerpt: string;
};

export type AITriageResult = {
  id: string;
  organization_id: string;
  ticket_id: string;
  model_provider: string;
  model_name: string;
  prompt_version: string;
  schema_version: string;
  latency_ms: number | null;
  job_run_id: string | null;
  category: string;
  priority: string;
  sentiment: string;
  summary: string;
  suggested_action: string;
  draft_reply: string;
  confidence_score: number;
  reasoning: string;
  requires_human_review: boolean;
  validation_status: string;
  knowledge_sources: KnowledgeReference[];
  created_at: string;
};


export type AITriageInboxUsage = {
  gmail_connection_id: string | null;
  gmail_email: string | null;
  used: number;
};

export type AITriageUsage = {
  date: string;
  timezone: string;
  daily_limit: number;
  used: number;
  remaining: number | null;
  paused_for_today: boolean;
  resets_at: string;
  per_inbox: AITriageInboxUsage[];
};
export type ReplySuggestion = {
  id: string;
  organization_id: string;
  ticket_id: string;
  ai_triage_result_id: string | null;
  gmail_connection_id: string | null;
  body: string;
  edited_body: string | null;
  status: "suggested" | "edited" | "approved" | "rejected" | "draft_created" | string;
  reply_version: number;
  approved_reply_version: number | null;
  created_by: "ai" | "agent" | string;
  created_by_user_id: string | null;
  approved_by_user_id: string | null;
  approved_at: string | null;
  gmail_draft_id: string | null;
  created_at: string;
  updated_at: string;
};

export type GmailDraft = {
  id: string;
  organization_id: string;
  ticket_id: string;
  reply_suggestion_id: string;
  gmail_draft_id: string;
  gmail_thread_id: string | null;
  created_by_user_id: string;
  created_at: string;
};

export type GmailDraftCreateResponse = {
  approval: ReplySuggestion;
  draft: GmailDraft;
  gmail_draft_id: string;
};


export type GmailSentMessage = {
  id: string;
  organization_id: string;
  ticket_id: string;
  reply_suggestion_id: string;
  gmail_message_id: string;
  gmail_thread_id: string | null;
  reply_version: number;
  sent_by_user_id: string;
  test_mode: boolean;
  sent_at: string;
  created_at: string;
};

export type GmailDirectSendResponse = {
  approval: ReplySuggestion;
  sent_message: GmailSentMessage;
  gmail_message_id: string;
  test_mode: boolean;
};
export type MetricsOverview = {
  total_tickets: number;
  active_tickets: number;
  resolved_tickets: number;
  spam_tickets: number;
  critical_tickets: number;
  high_priority_tickets: number;
  draft_created_tickets: number;
  by_status: Record<string, number>;
  by_priority: Record<string, number>;
};

export type SavedView = {
  id: string;
  organization_id: string;
  user_id: string;
  name: string;
  filters: Record<string, string>;
  created_at: string;
  updated_at: string;
};

export type BulkActionResult = {
  ticket_id: string;
  success: boolean;
  ticket: Ticket | null;
  error: string | null;
};

export type BulkActionResponse = {
  action: string;
  results: BulkActionResult[];
};

export type ResponseTemplate = {
  id: string;
  organization_id: string;
  name: string;
  body: string;
  category_tags: string[];
  created_by_user_id: string;
  updated_by_user_id: string | null;
  version: number;
  archived_at: string | null;
  created_at: string;
  updated_at: string;
};

export type TemplateInsertResult = {
  template: ResponseTemplate;
  suggestion: ReplySuggestion;
};

export type InternalNote = {
  id: string;
  organization_id: string;
  ticket_id: string;
  body: string;
  created_by_user_id: string;
  updated_by_user_id: string | null;
  version: number;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
};

export type InternalNoteEdit = {
  id: string;
  organization_id: string;
  note_id: string;
  edited_by_user_id: string;
  previous_body: string;
  new_body: string;
  version: number;
  created_at: string;
};

export type InternalNoteMention = {
  id: string;
  organization_id: string;
  note_id: string;
  mentioned_user_id: string;
  created_at: string;
};

export type CollaborationLock = {
  id: string;
  organization_id: string;
  ticket_id: string;
  resource_type: string;
  resource_id: string;
  locked_by_user_id: string;
  mode: string;
  expires_at: string;
  created_at: string;
  updated_at: string;
};

export type KnowledgeSource = {
  id: string;
  organization_id: string;
  title: string;
  body: string;
  source_type: string;
  status: string;
  owner_user_id: string;
  effective_from: string | null;
  effective_until: string | null;
  source_metadata: Record<string, unknown>;
  archived_at: string | null;
  created_at: string;
  updated_at: string;
};

export type RoutingRule = {
  id: string;
  organization_id: string;
  name: string;
  priority_order: number;
  is_active: boolean;
  conditions: Record<string, unknown>;
  actions: Record<string, unknown>;
  created_by_user_id: string;
  updated_by_user_id: string | null;
  created_at: string;
  updated_at: string;
};

export type RoutingRuleTestResult = {
  matched: boolean;
  matched_conditions: string[];
  actions_preview: Record<string, unknown>;
};

export type RoutingRuleExecution = {
  id: string;
  organization_id: string;
  routing_rule_id: string;
  ticket_id: string;
  matched: boolean;
  actions_applied: Record<string, unknown>;
  created_at: string;
};

export type WorkspaceSettings = {
  id: string;
  organization_id: string;
  default_reply_signature: string;
  auto_triage_enabled: boolean;
  draft_requires_approval: boolean;
  sync_enabled: boolean;
  draft_creation_enabled: boolean;
  direct_send_enabled: boolean;
  attachment_ai_processing_enabled: boolean;
  pilot_feedback_contact: string | null;
  business_timezone: string;
  business_hours: Record<string, { start?: string; end?: string }>;
  first_review_target_minutes: number;
  resolution_target_minutes: number;
  created_at: string;
  updated_at: string;
};

export type AgentWorkload = {
  user_id: string;
  open_tickets: number;
  total_assigned_tickets: number;
};

export type SupportPerformanceAnalytics = {
  ticket_volume: number;
  by_category: Record<string, number>;
  by_priority: Record<string, number>;
  first_review_time_avg_minutes: number | null;
  resolution_time_avg_minutes: number | null;
  approval_wait_time_avg_minutes: number | null;
  sla_attainment_rate: number | null;
  agent_workload: AgentWorkload[];
  reopen_rate: number;
  reopened_tickets: number;
};

export type AIQualityAnalytics = {
  triage_completion_rate: number;
  confidence_distribution: Record<string, number>;
  average_confidence_score: number | null;
  agent_category_corrections: number;
  agent_priority_corrections: number;
  reply_approval_rate: number;
  average_change_level: string;
  rejected_suggestion_reasons: Record<string, number>;
  provider_latency_avg_ms: number | null;
  provider_failure_rate: number;
};

export type GmailSyncAnalytics = {
  notifications_received: number;
  incremental_sync_success: number;
  fallback_recoveries: number;
  reconciliation_count: number;
  duplicate_skip_count: number;
  sync_latency_avg_ms: number | null;
  watch_renewal_success: number;
  reauthorization_count: number;
  by_status: Record<string, number>;
};

export type AdminAnalytics = {
  support: SupportPerformanceAnalytics;
  ai_quality: AIQualityAnalytics;
  gmail_sync: GmailSyncAnalytics;
  notes: string[];
};

export type AuditLog = {
  id: string;
  organization_id: string;
  actor_user_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  ip_address: string | null;
  user_agent: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
};
