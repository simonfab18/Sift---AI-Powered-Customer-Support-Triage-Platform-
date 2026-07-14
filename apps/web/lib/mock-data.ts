export type Severity = "critical" | "high" | "medium" | "low";
export type IntegrationStatus = "connected" | "coming soon" | "needs setup";

export const tickets = [
  {
    id: "SFT-1042",
    customer: "Maya Chen",
    company: "Northstar Labs",
    subject: "Payment failed before launch",
    severity: "critical" as Severity,
    category: "Billing",
    sentiment: "Negative",
    intent: "Recover payment",
    confidence: 94,
    sla: "38m left",
    assignee: "Simon",
    status: "Needs approval",
    tier: "VIP",
    preview: "The card was charged twice and the workspace is locked before their launch window.",
  },
  {
    id: "SFT-1039",
    customer: "Elliot Park",
    company: "Cinder Commerce",
    subject: "API returning intermittent 500 errors",
    severity: "high" as Severity,
    category: "Technical",
    sentiment: "Concerned",
    intent: "Escalate incident",
    confidence: 89,
    sla: "1h 12m left",
    assignee: "Ari",
    status: "Draft ready",
    tier: "Team",
    preview: "Production checkout requests fail during peak traffic and need an engineering escalation.",
  },
  {
    id: "SFT-1035",
    customer: "Nora Williams",
    company: "Parcelly",
    subject: "Refund requested for annual plan",
    severity: "high" as Severity,
    category: "Refund",
    sentiment: "Negative",
    intent: "Retain customer",
    confidence: 86,
    sla: "2h left",
    assignee: "Jamie",
    status: "Reviewing",
    tier: "Business",
    preview: "Customer wants to cancel before renewal because usage has dropped across their team.",
  },
  {
    id: "SFT-1028",
    customer: "Luis Romero",
    company: "BrightDesk",
    subject: "Unable to access administrator account",
    severity: "medium" as Severity,
    category: "Account access",
    sentiment: "Neutral",
    intent: "Restore access",
    confidence: 91,
    sla: "4h left",
    assignee: "Priya",
    status: "Assigned",
    tier: "Starter",
    preview: "Admin MFA reset is needed after a phone change.",
  },
  {
    id: "SFT-1021",
    customer: "Sam Taylor",
    company: "Kite Studio",
    subject: "Feature request for team permissions",
    severity: "low" as Severity,
    category: "Feedback",
    sentiment: "Positive",
    intent: "Capture feedback",
    confidence: 82,
    sla: "Tomorrow",
    assignee: "Morgan",
    status: "Triaged",
    tier: "Starter",
    preview: "They want custom roles for finance-only invoice access.",
  },
];

export const metrics = [
  { label: "Median first response", value: "18m", change: "32% faster", tone: "success" },
  { label: "Tickets triaged", value: "428", change: "+74 this week", tone: "info" },
  { label: "Approval rate", value: "87%", change: "12 edits avoided", tone: "success" },
  { label: "SLA risk", value: "6", change: "3 critical", tone: "warning" },
];

export const chartBars = [34, 48, 38, 62, 56, 74, 68, 82, 71, 88, 76, 94];

export const activity = [
  "Sift detected cancellation risk for Northstar Labs.",
  "Ari approved a Gmail draft for SFT-1039.",
  "Billing rule escalated 7 payment failures.",
  "Knowledge sync found 4 low-confidence questions.",
];

export const integrations = [
  { name: "Gmail", category: "Email", status: "connected" as IntegrationStatus, description: "Import conversations and create approved drafts." },
  { name: "Google Workspace", category: "Email", status: "needs setup" as IntegrationStatus, description: "Directory and shared mailbox support." },
  { name: "Slack", category: "Collaboration", status: "coming soon" as IntegrationStatus, description: "Notify channels when critical tickets change." },
  { name: "Webhooks", category: "Developer tools", status: "coming soon" as IntegrationStatus, description: "Send triage events to your own systems." },
  { name: "Supabase", category: "Data", status: "connected" as IntegrationStatus, description: "Workspace data, roles, and audit events." },
  { name: "API", category: "Developer tools", status: "coming soon" as IntegrationStatus, description: "Programmatic access for support workflows." },
];

export const automationRules = [
  { name: "Escalate payment failures", trigger: "Conversation imported", conditions: "Category is Billing, sentiment is Negative", action: "Set critical, notify owner", status: "Active", lastRun: "8m ago" },
  { name: "Flag VIP cancellations", trigger: "Analysis completes", conditions: "Tier is VIP, intent contains Cancel", action: "Assign retention lead", status: "Active", lastRun: "32m ago" },
  { name: "Prioritize security issues", trigger: "Priority changes", conditions: "Keywords include security or breach", action: "Require admin approval", status: "Draft", lastRun: "Never" },
  { name: "Assign billing questions", trigger: "Conversation imported", conditions: "Category is Billing", action: "Assign billing queue", status: "Active", lastRun: "1h ago" },
];

export const customers = [
  { name: "Maya Chen", company: "Northstar Labs", tier: "VIP", open: 2, last: "14m ago", sentiment: "Negative", health: "At risk" },
  { name: "Elliot Park", company: "Cinder Commerce", tier: "Team", open: 1, last: "42m ago", sentiment: "Concerned", health: "Watch" },
  { name: "Nora Williams", company: "Parcelly", tier: "Business", open: 3, last: "1h ago", sentiment: "Negative", health: "At risk" },
  { name: "Luis Romero", company: "BrightDesk", tier: "Starter", open: 1, last: "3h ago", sentiment: "Neutral", health: "Healthy" },
];

export const knowledgeSources = [
  { name: "Billing policy", status: "Synced", usage: "138 suggestions", gaps: 2 },
  { name: "API docs", status: "Processing", usage: "76 suggestions", gaps: 5 },
  { name: "Saved responses", status: "Synced", usage: "214 suggestions", gaps: 1 },
  { name: "Refund guidelines", status: "Needs attention", usage: "58 suggestions", gaps: 7 },
];
