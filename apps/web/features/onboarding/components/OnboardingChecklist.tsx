"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/Button";
import { getStoredOrganizationId } from "@/features/organizations/components/OrganizationManager";
import { getMetricsOverview, getTickets, getWorkspaceSettings } from "@/features/tickets/api";
import type { MetricsOverview, TicketListItem, WorkspaceSettings } from "@/features/tickets/types";
import {
  getGmailConnections,
  getMembers,
  getMe,
  getRecentImports,
} from "@/lib/api-client";
import type { GmailConnection, JobRun, Member, Organization } from "@/lib/api-types";
import { createClient } from "@/lib/supabase/client";

const ONBOARDING_KEY = "support-triage:onboarding-dismissed";

type ChecklistStep = {
  label: string;
  detail: string;
  done: boolean;
  href: string;
  cta: string;
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

function buildSteps(input: {
  organization: Organization | null;
  connections: GmailConnection[];
  imports: JobRun[];
  tickets: TicketListItem[];
  members: Member[];
  metrics: MetricsOverview | null;
  settings: WorkspaceSettings | null;
}): ChecklistStep[] {
  const activeConnections = input.connections.filter((connection) => connection.status === "active");
  const hasHealthyGmail = activeConnections.some(isHealthyConnection);
  const hasImportedMail =
    input.tickets.length > 0 ||
    input.imports.some((job) => job.status === "succeeded" && importedCount(job) > 0);

  return [
    {
      label: "Select workspace",
      detail: input.organization ? input.organization.name : "Choose or create the workspace for this support queue.",
      done: Boolean(input.organization),
      href: "/dashboard/organizations",
      cta: "Open workspaces",
    },
    {
      label: "Set workspace defaults",
      detail: "Confirm signature, business hours, timezone, and SLA targets.",
      done: workspaceDefaultsAreReady(input.settings),
      href: "/dashboard/settings/workspace",
      cta: "Review defaults",
    },
    {
      label: "Connect Gmail",
      detail: activeConnections.length > 0 ? `${activeConnections.length} inbox connected` : "Connect the first support inbox.",
      done: activeConnections.length > 0,
      href: "/dashboard/settings/gmail",
      cta: "Open Gmail settings",
    },
    {
      label: "Confirm Gmail health",
      detail: hasHealthyGmail ? "At least one inbox has active sync and watch." : "Reconnect or import if an inbox needs attention.",
      done: hasHealthyGmail,
      href: "/dashboard/settings/gmail",
      cta: "Check inbox health",
    },
    {
      label: "Import first conversation",
      detail: hasImportedMail ? "Imported conversations are available in the queue." : "Run an import after Gmail is connected.",
      done: hasImportedMail,
      href: "/dashboard/settings/gmail",
      cta: "Import Gmail",
    },
    {
      label: "Review first draft",
      detail: input.metrics && input.metrics.draft_created_tickets > 0 ? "A Gmail draft has been created." : "Approve a suggested reply from a ticket.",
      done: Boolean(input.metrics && input.metrics.draft_created_tickets > 0),
      href: "/dashboard/tickets",
      cta: "Open queue",
    },
    {
      label: "Invite teammate",
      detail: input.members.length > 1 ? `${input.members.length} members in this workspace` : "Add another owner, admin, or agent.",
      done: input.members.length > 1,
      href: "/dashboard/settings/team",
      cta: "Manage team",
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
          setSteps(buildSteps({ organization: null, connections: [], imports: [], tickets: [], members: [], metrics: null, settings: null }));
          return;
        }

        const [connections, imports, tickets, members, metrics, settings] = await Promise.all([
          getGmailConnections(accessToken, organization.id),
          getRecentImports(accessToken, organization.id),
          getTickets(organization.id, accessToken),
          getMembers(accessToken, organization.id),
          getMetricsOverview(organization.id, accessToken),
          getWorkspaceSettings(organization.id, accessToken),
        ]);

        setSteps(buildSteps({ organization, connections, imports, tickets, members, metrics, settings }));
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Failed to load setup progress.");
      } finally {
        setLoading(false);
      }
    }

    void loadChecklist();
  }, [supabase]);

  const progress = useMemo(() => steps.filter((step) => step.done).length, [steps]);
  const percent = steps.length > 0 ? (progress / steps.length) * 100 : 0;

  function dismissOnboarding() {
    window.localStorage.setItem(ONBOARDING_KEY, "true");
    setDismissed(true);
  }

  if (dismissed) return null;

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-900/5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-mono text-xs uppercase tracking-wide text-slate-500">Setup</p>
          <h2 className="mt-1 font-display text-lg font-semibold">Onboarding checklist</h2>
          <p className="mt-1 text-sm text-slate-500">
            {loading ? "Checking workspace setup..." : `${progress} of ${steps.length} complete`}
          </p>
        </div>
        <Button variant="ghost" onClick={dismissOnboarding}>Dismiss</Button>
      </div>

      <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full bg-brand-600 transition-all" style={{ width: `${percent}%` }} />
      </div>

      {message ? <p className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">{message}</p> : null}

      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {steps.map((step) => (
          <Link key={step.label} href={step.href} className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm transition hover:border-slate-300 hover:bg-white">
            <span className={step.done ? "text-teal-700" : "text-slate-500"}>{step.done ? "Done" : "Next"}</span>
            <span className="mt-1 block font-medium text-slate-900">{step.label}</span>
            <span className="mt-1 block min-h-10 text-xs leading-5 text-slate-500">{step.detail}</span>
            <span className="mt-3 inline-flex text-xs font-medium text-teal-700">{step.cta}</span>
          </Link>
        ))}
        {!loading && steps.length === 0 ? (
          <Link href="/dashboard/organizations" className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm font-medium text-teal-700">
            Create your first workspace
          </Link>
        ) : null}
      </div>
    </section>
  );
}
