"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/Button";
import { getStoredOrganizationId } from "@/features/organizations/components/OrganizationManager";
import { getAiTriageUsage, getWorkspaceSettings, updateWorkspaceSettings } from "@/features/tickets/api";
import type { AITriageUsage, WorkspaceSettings } from "@/features/tickets/types";
import { getOrganizationExport, requestOrganizationDeletion } from "@/lib/api-client";
import type { OrganizationDeletionRequest, OrganizationExport } from "@/lib/api-types";
import { createClient } from "@/lib/supabase/client";

const lifecycleMessages = [
  {
    label: "Invite accepted",
    audience: "New teammate",
    body: "Welcome to the workspace. Start by reviewing the dashboard checklist, then open Gmail settings and the triage queue.",
  },
  {
    label: "Gmail connected",
    audience: "Owner/Admin",
    body: "Gmail is connected. Confirm the inbox health card is green, then run the first import and review the imported tickets.",
  },
  {
    label: "Import degraded",
    audience: "Owner/Admin",
    body: "A Gmail inbox needs attention. Run Import now after any current job finishes, reconnect Gmail if it stays degraded, then check Scheduler and Pub/Sub.",
  },
  {
    label: "AI quota limited",
    audience: "Agent",
    body: "AI triage is temporarily capped for the free pilot. Continue reviewing imported tickets manually and retry triage later.",
  },
  {
    label: "Approval reminder",
    audience: "Agent",
    body: "Suggested replies stay in the approval queue until an agent reviews them. Approved replies can create Gmail drafts, but nothing is sent automatically.",
  },
];

const migrationChecklist = [
  "Record current Cloud Run revision, Vercel deployment, migration head, Pub/Sub targets, and Scheduler jobs.",
  "Back up or restore-test the staging database before risky schema changes.",
  "Apply migrations to staging and confirm the Alembic head before deploying dependent code.",
  "Deploy backend and frontend, then smoke health, login, Gmail settings, ticket list, approval, draft, and attachment download flows.",
  "Keep rollback commands and the previous frontend/backend deployments available until smoke checks pass.",
];

const smokeTestChecklist = [
  {
    label: "Gmail inbox health",
    detail: "Confirm every pilot inbox is healthy, then run Import now only when no import is already active.",
    href: "/dashboard/settings/gmail",
    action: "Open Gmail settings",
  },
  {
    label: "Ticket queue review",
    detail: "Send or import one test email, confirm the ticket appears, and verify source inbox filters still work.",
    href: "/dashboard/tickets",
    action: "Open tickets",
  },
  {
    label: "Approval to draft",
    detail: "Review a suggested reply, approve it, create the Gmail draft, and confirm the draft-created state is visible.",
    href: "/dashboard/tickets",
    action: "Review tickets",
  },
  {
    label: "Attachment download",
    detail: "For a message with an allowed attachment, store it and confirm the signed download opens the file.",
    href: "/dashboard/tickets",
    action: "Check attachment",
  },
  {
    label: "Operations posture",
    detail: "Check the dashboard operations panel for degraded inboxes, failed jobs, and retryable work before inviting pilot users.",
    href: "/dashboard",
    action: "Open dashboard",
  },
  {
    label: "Rollback notes",
    detail: "Record the current Cloud Run revision, Vercel deployment, and migration head before changing production-facing resources.",
    href: "/dashboard/settings/readiness",
    action: "Stay here",
  },
];

type PilotReadinessItem = {
  label: string;
  status: "ready" | "attention" | "review";
  detail: string;
};

function readinessTone(status: PilotReadinessItem["status"]) {
  if (status === "ready") return "border-emerald-200 bg-emerald-50 text-emerald-800";
  if (status === "review") return "border-sky-200 bg-sky-50 text-sky-800";
  return "border-amber-200 bg-amber-50 text-amber-900";
}

function readinessLabel(status: PilotReadinessItem["status"]) {
  if (status === "ready") return "Ready";
  if (status === "review") return "Review";
  return "Needs attention";
}

function isValidEmailAddress(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}

function ToggleRow({ label, description, checked, onChange }: { label: string; description: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <label className="flex items-start justify-between gap-4 rounded-md border border-slate-200 bg-slate-50 p-3">
      <span>
        <span className="block text-sm font-medium text-slate-900">{label}</span>
        <span className="mt-1 block text-xs leading-5 text-slate-500">{description}</span>
      </span>
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} className="mt-1 h-4 w-4 rounded border-slate-300" />
    </label>
  );
}

export function ReleaseReadinessSettings() {
  const supabase = createClient();
  const [settings, setSettings] = useState<WorkspaceSettings | null>(null);
  const [syncEnabled, setSyncEnabled] = useState(true);
  const [autoTriageEnabled, setAutoTriageEnabled] = useState(true);
  const [draftCreationEnabled, setDraftCreationEnabled] = useState(true);
  const [draftRequiresApproval, setDraftRequiresApproval] = useState(true);
  const [directSendEnabled, setDirectSendEnabled] = useState(false);
  const [attachmentAiProcessingEnabled, setAttachmentAiProcessingEnabled] = useState(false);
  const [pilotFeedbackContact, setPilotFeedbackContact] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [aiUsage, setAiUsage] = useState<AITriageUsage | null>(null);
  const [exportData, setExportData] = useState<OrganizationExport | null>(null);
  const [deletionRequest, setDeletionRequest] = useState<OrganizationDeletionRequest | null>(null);
  const [deletionReason, setDeletionReason] = useState("");
  const [exporting, setExporting] = useState(false);
  const [requestingDeletion, setRequestingDeletion] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  async function getContext() {
    const organizationId = getStoredOrganizationId();
    const { data } = await supabase.auth.getSession();
    const accessToken = data.session?.access_token;
    if (!organizationId || !accessToken) return null;
    return { organizationId, accessToken };
  }

  async function loadSettings() {
    setLoading(true);
    setMessage(null);
    const context = await getContext();
    if (!context) {
      setMessage("Select a workspace and sign in before reviewing release readiness.");
      setLoading(false);
      return;
    }

    try {
      const [loaded, usage] = await Promise.all([
        getWorkspaceSettings(context.organizationId, context.accessToken),
        getAiTriageUsage(context.organizationId, context.accessToken),
      ]);
      setSettings(loaded);
      setSyncEnabled(loaded.sync_enabled);
      setAutoTriageEnabled(loaded.auto_triage_enabled);
      setDraftCreationEnabled(loaded.draft_creation_enabled);
      setDraftRequiresApproval(loaded.draft_requires_approval);
      setDirectSendEnabled(loaded.direct_send_enabled);
      setAttachmentAiProcessingEnabled(loaded.attachment_ai_processing_enabled);
      setPilotFeedbackContact(loaded.pilot_feedback_contact ?? "");
      setAiUsage(usage);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to load readiness settings.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadSettings();
  }, []);

  const disabledCount = useMemo(
    () => [syncEnabled, autoTriageEnabled, draftCreationEnabled, draftRequiresApproval].filter((enabled) => !enabled).length,
    [syncEnabled, autoTriageEnabled, draftCreationEnabled, draftRequiresApproval],
  );

  const pilotContactInvalid = Boolean(pilotFeedbackContact.trim()) && !isValidEmailAddress(pilotFeedbackContact);

  const pilotReadinessItems = useMemo<PilotReadinessItem[]>(() => [
    {
      label: "Gmail sync",
      status: syncEnabled ? "ready" : "attention",
      detail: syncEnabled ? "Imports, push sync, and fallback sync are allowed for this workspace." : "Turn Gmail sync on before using a pilot support inbox.",
    },
    {
      label: "AI triage",
      status: autoTriageEnabled && !aiUsage?.paused_for_today ? "ready" : autoTriageEnabled ? "review" : "attention",
      detail: !autoTriageEnabled
        ? "Automatic AI triage is paused for this workspace."
        : aiUsage?.paused_for_today
          ? "AI is paused for today by the free pilot cap; agents can still review tickets manually."
          : "Automatic triage is allowed while free-tier quota is available.",
    },
    {
      label: "Approval and drafts",
      status: draftCreationEnabled && draftRequiresApproval ? "ready" : "attention",
      detail: draftCreationEnabled && draftRequiresApproval
        ? "Approved replies can create Gmail drafts, and human approval remains required."
        : "Keep draft creation enabled and approval required for the pilot workflow.",
    },
    {
      label: "Direct send posture",
      status: directSendEnabled ? "review" : "ready",
      detail: directSendEnabled ? "Direct send is enabled. Confirm this is only for approved smoke testing." : "Live sending stays off; agents create drafts instead.",
    },
    {
      label: "Pilot contact",
      status: pilotFeedbackContact.trim() && !pilotContactInvalid ? "ready" : "attention",
      detail: !pilotFeedbackContact.trim()
        ? "Add a support contact so pilot users know where to report issues."
        : pilotContactInvalid
          ? "Enter a valid email address for the pilot support contact."
          : `Pilot support contact is ${pilotFeedbackContact.trim()}.`,
    },
    {
      label: "Attachment AI",
      status: attachmentAiProcessingEnabled ? "review" : "ready",
      detail: attachmentAiProcessingEnabled ? "Attachment AI processing is opted in for future AI features." : "Stored attachment contents are not available to AI processing.",
    },
    {
      label: "Data controls",
      status: "ready",
      detail: "Owner/admin export and deletion-request controls are available from this page.",
    },
  ], [aiUsage?.paused_for_today, attachmentAiProcessingEnabled, autoTriageEnabled, directSendEnabled, draftCreationEnabled, draftRequiresApproval, pilotContactInvalid, pilotFeedbackContact, syncEnabled]);

  const pilotAttentionCount = pilotReadinessItems.filter((item) => item.status === "attention").length;
  const pilotReviewCount = pilotReadinessItems.filter((item) => item.status === "review").length;
  async function saveFlags() {
    const context = await getContext();
    if (!context) {
      setMessage("Select a workspace and sign in before saving release controls.");
      return;
    }

    if (pilotContactInvalid) {
      setMessage("Enter a valid email address for the pilot support contact.");
      return;
    }

    setSaving(true);
    setMessage(null);
    try {
      const updated = await updateWorkspaceSettings(context.organizationId, context.accessToken, {
        sync_enabled: syncEnabled,
        auto_triage_enabled: autoTriageEnabled,
        draft_creation_enabled: draftCreationEnabled,
        draft_requires_approval: draftRequiresApproval,
        direct_send_enabled: directSendEnabled,
        attachment_ai_processing_enabled: attachmentAiProcessingEnabled,
        pilot_feedback_contact: pilotFeedbackContact.trim() || null,
      });
      setSettings(updated);
      setMessage("Release controls saved.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to save release controls.");
    } finally {
      setSaving(false);
    }
  }
  async function downloadOrganizationExport() {
    const context = await getContext();
    if (!context) {
      setMessage("Select a workspace and sign in before exporting organization data.");
      return;
    }

    setExporting(true);
    setMessage(null);
    try {
      const exported = await getOrganizationExport(context.accessToken, context.organizationId);
      setExportData(exported);
      const blob = new Blob([JSON.stringify(exported, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `sift-organization-export-${context.organizationId}.json`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setMessage("Organization export generated.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to export organization data.");
    } finally {
      setExporting(false);
    }
  }

  async function submitDeletionRequest() {
    const context = await getContext();
    if (!context) {
      setMessage("Select a workspace and sign in before requesting deletion.");
      return;
    }
    if (!deletionReason.trim()) {
      setMessage("Add a short reason before requesting deletion.");
      return;
    }

    setRequestingDeletion(true);
    setMessage(null);
    try {
      const request = await requestOrganizationDeletion(context.accessToken, context.organizationId, deletionReason.trim());
      setDeletionRequest(request);
      setSyncEnabled(false);
      setAutoTriageEnabled(false);
      setDraftCreationEnabled(false);
      setMessage("Deletion request recorded. Gmail sync, AI triage, and draft creation are paused for this workspace.");
      await loadSettings();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to request organization deletion.");
    } finally {
      setRequestingDeletion(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-6 xl:grid-cols-[1fr_360px]">
        <section className="rounded-lg border border-slate-200 bg-white p-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="font-display text-lg font-semibold">Feature flags</h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">Workspace-level controls for operating the free pilot safely.</p>
            </div>
            <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">
              {disabledCount === 0 ? "All enabled" : `${disabledCount} limited`}
            </span>
          </div>
          {loading ? <p className="mt-4 text-sm text-slate-500">Loading release controls...</p> : null}
          <div className="mt-4 space-y-3">
            <ToggleRow label="Gmail sync" description="Allow Gmail import, history sync, and fallback sync for this workspace." checked={syncEnabled} onChange={setSyncEnabled} />
            <ToggleRow label="Automatic AI triage" description="Allow imported tickets to queue AI triage automatically when provider quota is available." checked={autoTriageEnabled} onChange={setAutoTriageEnabled} />
            <ToggleRow label="Gmail draft creation" description="Allow approved suggestions to create Gmail drafts." checked={draftCreationEnabled} onChange={setDraftCreationEnabled} />
            <ToggleRow label="Approval required" description="Keep humans in control before any Gmail draft is created." checked={draftRequiresApproval} onChange={setDraftRequiresApproval} />
            <ToggleRow label="Direct Gmail send" description="Allow approved replies to be sent from Sift after explicit final confirmation. Keep off during the free pilot unless you are smoke-testing send controls." checked={directSendEnabled} onChange={setDirectSendEnabled} />
            <ToggleRow label="Attachment AI processing" description="Allow future AI features to inspect stored attachment contents. Keep off unless the workspace owner has explicitly opted in." checked={attachmentAiProcessingEnabled} onChange={setAttachmentAiProcessingEnabled} />
          </div>
          <label className="mt-4 block text-sm font-medium text-slate-700" htmlFor="pilot-feedback-contact">Pilot support contact</label>
          <input id="pilot-feedback-contact" type="email" inputMode="email" value={pilotFeedbackContact} onChange={(event) => setPilotFeedbackContact(event.target.value)} placeholder="support@example.com" className={`mt-2 w-full rounded-md border px-3 py-2 text-sm outline-none ${pilotContactInvalid ? "border-amber-400 focus:border-amber-600" : "border-slate-300 focus:border-slate-900"}`} />
          {pilotContactInvalid ? <p className="mt-2 text-xs font-medium text-amber-700">Enter a valid support email before saving.</p> : null}
          <Button type="button" variant="primary" className="mt-5" onClick={() => void saveFlags()} disabled={saving || pilotContactInvalid}>{saving ? "Saving..." : "Save release controls"}</Button>
          {message ? <p className="mt-4 text-sm text-slate-600">{message}</p> : null}
        </section>

        <aside className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="font-display text-lg font-semibold">Current posture</h2>
          <dl className="mt-4 space-y-3 text-sm">
            <div><dt className="text-slate-500">Last saved</dt><dd className="font-medium">{settings ? new Date(settings.updated_at).toLocaleString() : "Not loaded"}</dd></div>
            <div><dt className="text-slate-500">Billing</dt><dd className="font-medium">Free pilot only</dd></div>
            <div>
              <dt className="text-slate-500">AI quota</dt>
              <dd className="font-medium">{aiUsage ? `${aiUsage.used}/${aiUsage.daily_limit || "unlimited"} today` : "App-side Gemini cap"}</dd>
              {aiUsage?.paused_for_today ? <p className="mt-1 text-xs font-medium text-amber-700">AI paused for today. It resets {new Date(aiUsage.resets_at).toLocaleString()}.</p> : null}
            </div>
            <div><dt className="text-slate-500">Send policy</dt><dd className="font-medium">{directSendEnabled ? "Direct send allowed with confirmation" : "Draft only, no direct send"}</dd></div>
            <div><dt className="text-slate-500">Attachment AI</dt><dd className="font-medium">{attachmentAiProcessingEnabled ? "Opted in" : "Not allowed"}</dd></div>
          </dl>
        </aside>
      </div>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="font-display text-lg font-semibold">Pilot launch checklist</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">A workspace-level safety check before pointing a real Gmail support inbox at the pilot.</p>
          </div>
          <span className={`w-fit rounded-md px-2 py-1 text-xs font-medium ${pilotAttentionCount > 0 ? "bg-amber-100 text-amber-800" : pilotReviewCount > 0 ? "bg-sky-100 text-sky-800" : "bg-emerald-100 text-emerald-700"}`}>
            {pilotAttentionCount > 0 ? `${pilotAttentionCount} attention` : pilotReviewCount > 0 ? `${pilotReviewCount} review` : "Pilot-ready"}
          </span>
        </div>
        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          {pilotReadinessItems.map((item) => (
            <article key={item.label} className={`rounded-md border p-4 text-sm ${readinessTone(item.status)}`}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-medium">{item.label}</h3>
                <span className="rounded-md bg-white/80 px-2 py-1 text-xs font-medium">{readinessLabel(item.status)}</span>
              </div>
              <p className="mt-2 leading-6">{item.detail}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="font-display text-lg font-semibold">Pilot smoke test</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">Run these checks after deploys or configuration changes before using a real support inbox.</p>
          </div>
          <span className="w-fit rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">Manual check</span>
        </div>
        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          {smokeTestChecklist.map((item) => (
            <article key={item.label} className="rounded-md border border-slate-200 bg-slate-50 p-4 text-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-medium text-slate-900">{item.label}</h3>
                <Link href={item.href} className="rounded-md bg-white px-2 py-1 text-xs font-medium text-teal-700 ring-1 ring-inset ring-slate-200">{item.action}</Link>
              </div>
              <p className="mt-2 leading-6 text-slate-600">{item.detail}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="font-display text-lg font-semibold">Lifecycle communications</h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">Reusable pilot messages for onboarding, degraded sync, quota limits, and approval reminders.</p>
        {aiUsage ? (
          <div className={aiUsage.paused_for_today ? "mt-4 rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900" : "mt-4 rounded-md border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900"}>
            <p className="font-medium">{aiUsage.paused_for_today ? "AI paused for today" : "AI usage available today"}</p>
            <p className="mt-1">{aiUsage.daily_limit > 0 ? `${aiUsage.remaining} of ${aiUsage.daily_limit} daily free triage runs remain. Resets ${new Date(aiUsage.resets_at).toLocaleString()}.` : "The app-side daily cap is disabled for this environment."}</p>
            {aiUsage.per_inbox.length > 0 ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {aiUsage.per_inbox.map((inbox) => <span key={inbox.gmail_connection_id ?? "manual"} className="rounded-md bg-white px-2 py-1 text-xs text-slate-600">{inbox.gmail_email ?? "Manual tickets"}: {inbox.used}</span>)}
              </div>
            ) : null}
          </div>
        ) : null}
        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          {lifecycleMessages.map((item) => (
            <article key={item.label} className="rounded-md border border-slate-200 bg-slate-50 p-4 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="font-medium text-slate-900">{item.label}</h3>
                <span className="rounded-md bg-white px-2 py-1 text-xs text-slate-500">{item.audience}</span>
              </div>
              <p className="mt-2 leading-6 text-slate-600">{item.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <div className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="font-display text-lg font-semibold">Export and deletion controls</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">Owners and admins can export workspace data. Owners can request deletion, which records an audit event and pauses Gmail sync, AI triage, and draft creation without hard-deleting records.</p>
          <div className="mt-4 flex flex-wrap gap-2 text-sm">
            <Button type="button" variant="outline" onClick={() => void downloadOrganizationExport()} disabled={exporting}>{exporting ? "Exporting..." : "Download export"}</Button>
            <Link className="rounded-md border border-slate-300 px-3 py-2 font-medium text-slate-700" href="/data-processing">Data processing</Link>
            <Link className="rounded-md border border-slate-300 px-3 py-2 font-medium text-slate-700" href="/privacy">Privacy</Link>
          </div>
          {exportData ? <p className="mt-3 text-xs text-slate-500">Last export: {exportData.counts.tickets ?? 0} tickets, {exportData.counts.gmail_connections ?? 0} Gmail inboxes, generated {new Date(exportData.generated_at).toLocaleString()}.</p> : null}
          <div className="mt-5 border-t border-slate-200 pt-4">
            <label className="block text-sm font-medium text-slate-700" htmlFor="deletion-reason">Deletion request reason</label>
            <textarea id="deletion-reason" value={deletionReason} onChange={(event) => setDeletionReason(event.target.value)} rows={3} className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-slate-900" placeholder="Why should this workspace be queued for deletion?" />
            <Button type="button" variant="outline" className="mt-3" onClick={() => void submitDeletionRequest()} disabled={requestingDeletion}>{requestingDeletion ? "Requesting..." : "Request deletion"}</Button>
            {deletionRequest ? <p className="mt-3 text-xs text-amber-700">Deletion request recorded at {new Date(deletionRequest.requested_at).toLocaleString()}. Workspace automation is paused.</p> : null}
          </div>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="font-display text-lg font-semibold">Controlled migration checklist</h2>
          <ol className="mt-4 list-decimal space-y-2 pl-5 text-sm leading-6 text-slate-600">
            {migrationChecklist.map((item) => <li key={item}>{item}</li>)}
          </ol>
        </div>
      </section>
    </div>
  );
}
