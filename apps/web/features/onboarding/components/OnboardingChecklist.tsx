"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/Button";
import { getStoredOrganizationId } from "@/features/organizations/components/OrganizationManager";
import { getAiTriageUsage, getMetricsOverview, getTickets, getWorkspaceSettings } from "@/features/tickets/api";
import type { AITriageUsage, MetricsOverview, TicketListItem, WorkspaceSettings } from "@/features/tickets/types";
import {
  getGmailConnections,
  getMembers,
  getMe,
  getRecentImports,
} from "@/lib/api-client";
import type { GmailConnection, JobRun, Member, Organization } from "@/lib/api-types";
import { createClient } from "@/lib/supabase/client";

const ONBOARDING_KEY = "support-triage:onboarding-dismissed";

type ChecklistStatus = "done" | "next" | "attention" | "optional";

type ChecklistStep = {
  label: string;
  detail: string;
  done: boolean;
  href: string;
  cta: string;
  status?: ChecklistStatus;
};

function importedCount(job: JobRun) {
  const value = job.job_metadata.imported_count;
  return typeof value === "number" ? value : Number(value ?? 0);
}

function isHealthyConnection(connection: GmailConnection) {
  return connection.status === "active" && connection.sync_status === "active" && connection.watch_status === "active";
}

function workspaceDefaultsAreReady(settings: WorkspaceSettings | null) {
  if (!settings) return false;
  return Boolean(
    settings.default_reply_signature?.trim() &&
      settings.business_timezone?.trim() &&
      settings.first_review_target_minutes > 0 &&
      settings.resolution_target_minutes > 0,
  );
}

function readinessControlsAreReady(settings: WorkspaceSettings | null) {
  if (!settings) return false;
  return Boolean(
    settings.sync_enabled &&
      settings.auto_triage_enabled &&
      settings.draft_creation_enabled &&
      settings.draft_requires_approval &&
      !settings.direct_send_enabled &&
      settings.pilot_feedback_contact?.trim(),
  );
}

function hasAiTriagedTicket(tickets: TicketListItem[]) {
  return tickets.some((ticket) => ticket.triage_status === "triaged");
}

function hasApprovalReadyTicket(tickets: TicketListItem[]) {
  return tickets.some((ticket) => ticket.latest_reply_status === "suggested" || ticket.latest_reply_status === "edited" || ticket.latest_reply_status === "approved");
}

function hasRoutingReady(members: Member[]) {
  return members.some((member) => member.status === "active" && ["owner", "admin", "agent"].includes(member.role));
}

function statusTone(status: ChecklistStatus) {
  if (status === "done") return "border-slate-200 bg-white/30 text-slate-700";
  if (status === "attention") return "border-[#ddd7e6] bg-white/50 text-[#746d80]";
  if (status === "optional") return "border-slate-200 bg-white/30 text-slate-600";
  return "border-[#ddd7e6] bg-white/50 text-[#655f73]";
}

function statusLabel(status: ChecklistStatus) {
  if (status === "done") return "Done";
  if (status === "attention") return "Check";
  if (status === "optional") return "Optional";
  return "Next";
}

function withStatus(step: Omit<ChecklistStep, "status">): ChecklistStep {
  return { ...step, status: step.done ? "done" : "next" };
}

function buildSteps(input: {
  organization: Organization | null;
  connections: GmailConnection[];
  imports: JobRun[];
  tickets: TicketListItem[];
  members: Member[];
  metrics: MetricsOverview | null;
  settings: WorkspaceSettings | null;
  aiUsage: AITriageUsage | null;
}): ChecklistStep[] {
  const activeConnections = input.connections.filter((connection) => connection.status === "active");
  const hasHealthyGmail = activeConnections.some(isHealthyConnection);
  const degradedConnections = activeConnections.filter((connection) => !isHealthyConnection(connection));
  const hasImportedMail =
    input.tickets.length > 0 ||
    input.imports.some((job) => job.status === "succeeded" && importedCount(job) > 0);
  const aiPaused = Boolean(input.aiUsage?.paused_for_today || input.aiUsage?.global_paused_for_today);
  const aiTriaged = hasAiTriagedTicket(input.tickets);
  const draftCreated = Boolean(input.metrics && input.metrics.draft_created_tickets > 0);
  const attachmentAiReviewed = Boolean(input.settings);

  return [
    withStatus({
      label: "Select workspace",
      detail: input.organization ? input.organization.name : "Choose or create the workspace for this support queue.",
      done: Boolean(input.organization),
      href: "/dashboard/organizations",
      cta: "Open workspaces",
    }),
    withStatus({
      label: "Set workspace defaults",
      detail: "Confirm signature, business hours, timezone, and SLA targets.",
      done: workspaceDefaultsAreReady(input.settings),
      href: "/dashboard/settings/workspace",
      cta: "Review defaults",
    }),
    withStatus({
      label: "Connect Gmail",
      detail: activeConnections.length > 0 ? `${activeConnections.length} inbox${activeConnections.length === 1 ? "" : "es"} connected` : "Connect the first support inbox.",
      done: activeConnections.length > 0,
      href: "/dashboard/settings/gmail",
      cta: "Open Gmail settings",
    }),
    {
      label: "Confirm Gmail health",
      detail: hasHealthyGmail ? "At least one inbox has active sync and watch." : degradedConnections.length > 0 ? `${degradedConnections.length} inbox needs sync/watch attention.` : "Reconnect or import if an inbox needs attention.",
      done: hasHealthyGmail,
      href: "/dashboard/settings/gmail",
      cta: "Check inbox health",
      status: hasHealthyGmail ? "done" : activeConnections.length > 0 ? "attention" : "next",
    },
    withStatus({
      label: "Import first conversation",
      detail: hasImportedMail ? "Imported conversations are available in the queue." : "Run an import after Gmail is connected.",
      done: hasImportedMail,
      href: "/dashboard/settings/gmail",
      cta: "Import Gmail",
    }),
    {
      label: "Run AI triage",
      detail: aiTriaged
        ? "At least one ticket has completed AI triage."
        : aiPaused
          ? `AI is paused by quota today; ${input.aiUsage?.used ?? 0}/${input.aiUsage?.daily_limit ?? 0} workspace calls used.`
          : "Open a ticket and regenerate triage, or import a fresh message.",
      done: aiTriaged,
      href: "/dashboard/tickets",
      cta: aiPaused ? "Review queue manually" : "Open queue",
      status: aiTriaged ? "done" : aiPaused ? "attention" : "next",
    },
    withStatus({
      label: "Approve a reply",
      detail: hasApprovalReadyTicket(input.tickets) ? "A reply suggestion is ready for human review." : "Use a suggested reply or response template, then approve it.",
      done: hasApprovalReadyTicket(input.tickets),
      href: "/dashboard/tickets",
      cta: "Review replies",
    }),
    withStatus({
      label: "Create a Gmail draft",
      detail: draftCreated ? "A Gmail draft has been created from an approved reply." : "Create a Gmail draft after approving a reply.",
      done: draftCreated,
      href: "/dashboard/tickets",
      cta: "Open queue",
    }),
    withStatus({
      label: "Invite teammate",
      detail: input.members.length > 1 ? `${input.members.length} members in this workspace` : "Add another owner, admin, or agent.",
      done: input.members.length > 1,
      href: "/dashboard/settings/team",
      cta: "Manage team",
    }),
    withStatus({
      label: "Check routing owner",
      detail: hasRoutingReady(input.members) ? "At least one active teammate can receive routed tickets." : "Add an active owner/admin/agent before using routing rules.",
      done: hasRoutingReady(input.members),
      href: "/dashboard/settings/routing",
      cta: "Review routing",
    }),
    {
      label: "Review attachment AI",
      detail: input.settings?.attachment_ai_processing_enabled ? "Attachment AI processing is explicitly opted in." : "Attachment AI processing is off by default for privacy.",
      done: attachmentAiReviewed,
      href: "/dashboard/settings/readiness",
      cta: "Open readiness",
      status: input.settings?.attachment_ai_processing_enabled ? "done" : "optional",
    },
    {
      label: "Confirm pilot readiness",
      detail: readinessControlsAreReady(input.settings) ? "Pilot controls are in the recommended free-pilot posture." : "Check sync, AI, drafts, approval, direct send, and pilot contact.",
      done: readinessControlsAreReady(input.settings),
      href: "/dashboard/settings/readiness",
      cta: "Open readiness",
      status: readinessControlsAreReady(input.settings) ? "done" : "attention",
    },
  ];
}

export function OnboardingChecklist() {
  const supabase = createClient();
  const [steps, setSteps] = useState<ChecklistStep[]>([]);
  const [dismissed, setDismissed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    setDismissed(window.localStorage.getItem(ONBOARDING_KEY) === "true");

    async function loadChecklist() {
      setLoading(true);
      setMessage(null);
      const { data } = await supabase.auth.getSession();
      const accessToken = data.session?.access_token;
      if (!accessToken) {
        setMessage("Sign in to load setup progress.");
        setLoading(false);
        return;
      }

      try {
        const me = await getMe(accessToken);
        const storedOrganizationId = getStoredOrganizationId();
        const organization = me.organizations.find((item) => item.id === storedOrganizationId) ?? me.organizations[0] ?? null;
        if (!organization) {
          setSteps(buildSteps({ organization: null, connections: [], imports: [], tickets: [], members: [], metrics: null, settings: null, aiUsage: null }));
          return;
        }

        const [connections, imports, tickets, members, metrics, settings, aiUsage] = await Promise.all([
          getGmailConnections(accessToken, organization.id),
          getRecentImports(accessToken, organization.id),
          getTickets(organization.id, accessToken),
          getMembers(accessToken, organization.id),
          getMetricsOverview(organization.id, accessToken),
          getWorkspaceSettings(organization.id, accessToken),
          getAiTriageUsage(organization.id, accessToken).catch(() => null),
        ]);

        setSteps(buildSteps({ organization, connections, imports, tickets, members, metrics, settings, aiUsage }));
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Failed to load setup progress.");
      } finally {
        setLoading(false);
      }
    }

    void loadChecklist();
  }, [supabase]);

  const requiredSteps = useMemo(() => steps.filter((step) => step.status !== "optional"), [steps]);
  const progress = useMemo(() => requiredSteps.filter((step) => step.done).length, [requiredSteps]);
  const attentionCount = useMemo(() => steps.filter((step) => step.status === "attention").length, [steps]);
  const percent = requiredSteps.length > 0 ? (progress / requiredSteps.length) * 100 : 0;

  function dismissOnboarding() {
    window.localStorage.setItem(ONBOARDING_KEY, "true");
    setDismissed(true);
  }

  if (dismissed) return null;

  return (
    <section className="rounded-lg border border-white/50 bg-white/60 backdrop-blur-xl p-4 shadow-[0_18px_48px_rgba(72,60,96,0.075)]">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">Pilot setup</p>
          <h2 className="mt-1 font-display text-lg font-semibold text-slate-950">Readiness checklist</h2>
          <p className="mt-1 text-sm text-slate-500">
            {loading ? "Checking workspace setup..." : `${progress} of ${requiredSteps.length} required steps complete${attentionCount ? ` / ${attentionCount} need attention` : ""}`}
          </p>
        </div>
        <Button variant="ghost" onClick={dismissOnboarding}>Dismiss</Button>
      </div>

      <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full bg-brand-600 transition-all" style={{ width: `${percent}%` }} />
      </div>

      {message ? <p className="mt-4 rounded-md border border-[#ddd7e6] bg-white/50 p-3 text-sm text-[#746d80]">{message}</p> : null}

      <div className="mt-4 grid gap-2 lg:grid-cols-2">
        {steps.map((step) => {
          const status = step.status ?? (step.done ? "done" : "next");
          return (
            <Link key={step.label} href={step.href} className={`group grid grid-cols-[auto_1fr_auto] items-center gap-3 rounded-md border bg-white p-3 text-sm transition hover:border-slate-300 hover:bg-white/30 ${statusTone(status)}`}>
              <span className="w-16 rounded-md bg-white/70 px-2 py-1 text-center text-[11px] font-semibold uppercase tracking-wide shadow-[0_10px_24px_rgba(72,60,96,0.06)]">{statusLabel(status)}</span>
              <span className="min-w-0">
                <span className="block font-semibold text-slate-950">{step.label}</span>
                <span className="mt-0.5 block truncate text-xs leading-5 opacity-80">{step.detail}</span>
              </span>
              <span className="text-xs font-semibold text-slate-500 group-hover:text-[#655f73]">Open</span>
            </Link>
          );
        })}
        {!loading && steps.length === 0 ? (
          <Link href="/dashboard/organizations" className="rounded-md border border-slate-200 bg-white/30 p-3 text-sm font-semibold text-[#655f73]">
            Create your first workspace
          </Link>
        ) : null}
      </div>
    </section>
  );
}





