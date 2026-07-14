"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { getStoredOrganizationId } from "@/features/organizations/components/OrganizationManager";
import { getMe } from "@/lib/api-client";
import type { Organization } from "@/lib/api-types";
import { createClient } from "@/lib/supabase/client";
import { getMetricsOverview } from "@/features/tickets/api";
import type { MetricsOverview } from "@/features/tickets/types";
import { cx } from "@/components/ui/cx";

const navItems = [
  { href: "/dashboard", label: "Dashboard", mark: "D", helper: "Overview" },
  { href: "/dashboard/tickets", label: "Triage queue", mark: "Q", helper: "Active tickets", badge: "pending" },
  { href: "/dashboard/analytics", label: "Analytics", mark: "A", helper: "Performance", ownerOnly: true },
  { href: "/dashboard/settings", label: "Settings", mark: "S", helper: "Knowledge & rules", ownerOnly: true },
];

function pageTitle(pathname: string) {
  if (pathname.includes("/tickets/")) return "Ticket detail";
  if (pathname.includes("/analytics")) return "Analytics";
  if (pathname.includes("/tickets")) return "Triage queue";
  if (pathname.includes("/settings/audit")) return "Audit log";
  if (pathname.includes("/settings/team")) return "Team";
  if (pathname.includes("/settings/knowledge")) return "Knowledge";
  if (pathname.includes("/settings/routing")) return "Routing";
  if (pathname.includes("/settings/readiness")) return "Readiness";
  if (pathname.includes("/settings/workspace")) return "Workspace";
  if (pathname.includes("/settings")) return "Settings";
  if (pathname.includes("/organizations")) return "Organizations";
  return "Dashboard";
}

function pageDescription(pathname: string) {
  if (pathname.includes("/tickets/")) return "Review the thread, AI reasoning, and approved Gmail draft state.";
  if (pathname.includes("/tickets")) return "Search, sort, and prioritize support tickets by urgency.";
  if (pathname.includes("/analytics")) return "Measure support performance, AI quality, Gmail sync, and workload.";
  if (pathname.includes("/settings/team")) return "Manage teammates and workspace access.";
  if (pathname.includes("/settings/knowledge")) return "Manage the sources AI can reference for replies.";
  if (pathname.includes("/settings/routing")) return "Configure rule-based assignment, approval, and priority handling.";
  if (pathname.includes("/settings/readiness")) return "Review pilot controls, lifecycle messaging, data-control direction, and release checks.";
  if (pathname.includes("/settings/workspace")) return "Tune workspace details, signatures, SLA targets, and business hours.";
  if (pathname.includes("/settings/audit")) return "Filter, inspect, and export administrative activity.";
  if (pathname.includes("/settings")) return "Connect Gmail and configure team operations.";
  if (pathname.includes("/organizations")) return "Choose or create the workspace you want to operate from.";
  return "A calm command center for Gmail support triage.";
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const supabase = createClient();
  const [organization, setOrganization] = useState<Organization | null>(null);
  const [metrics, setMetrics] = useState<MetricsOverview | null>(null);

  useEffect(() => {
    async function loadContext() {
      const { data } = await supabase.auth.getSession();
      const accessToken = data.session?.access_token;
      if (!accessToken) return;
      const me = await getMe(accessToken);
      const stored = getStoredOrganizationId();
      const selected = me.organizations.find((item) => item.id === stored) ?? me.organizations[0] ?? null;
      setOrganization(selected);
      if (selected) {
        try {
          setMetrics(await getMetricsOverview(selected.id, accessToken));
        } catch {
          setMetrics(null);
        }
      }
    }
    void loadContext();
  }, [pathname, supabase]);

  const role = organization?.role ?? "agent";
  const canSeeOwnerSettings = role === "owner" || role === "admin";
  const pendingCount = metrics?.active_tickets ?? 0;
  const visibleNavItems = navItems.filter((item) => !item.ownerOnly || canSeeOwnerSettings);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 md:pl-72">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-72 border-r border-slate-200 bg-white md:flex md:flex-col">
        <div className="px-5 py-5">
          <Link href="/dashboard" className="flex items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-lg bg-slate-900 font-display text-sm font-semibold text-white">TL</span>
            <span>
              <span className="block font-display text-lg font-semibold tracking-tight text-slate-900">TriageLab</span>
              <span className="block text-xs text-slate-500">Support operations</span>
            </span>
          </Link>
        </div>

        <div className="mx-4 rounded-lg border border-slate-200 bg-slate-50 p-3">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-slate-900">{organization?.name ?? "No workspace"}</p>
              <p className="mt-0.5 capitalize text-xs text-slate-500">{organization?.role ?? "Select workspace"}</p>
            </div>
            <span className="rounded-md bg-teal-50 px-2 py-1 text-xs font-medium text-teal-700">Live</span>
          </div>
          <Link href="/dashboard/organizations" className="mt-3 inline-flex text-xs font-medium text-teal-700 hover:text-teal-800">
            Change workspace
          </Link>
        </div>

        <nav className="flex-1 space-y-1 px-3 py-5">
          {visibleNavItems.map((item) => {
            const active = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cx(
                  "group flex items-center gap-3 rounded-lg px-3 py-3 text-sm font-medium transition",
                  active ? "bg-slate-900 text-white shadow-sm" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
                )}
              >
                <span className={cx("grid h-9 w-9 shrink-0 place-items-center rounded-md border font-display text-xs", active ? "border-white/20 bg-white/10" : "border-slate-200 bg-white text-slate-500 group-hover:text-slate-900")}>{item.mark}</span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate">{item.label}</span>
                  <span className={cx("block truncate text-xs font-normal", active ? "text-slate-300" : "text-slate-400")}>{item.helper}</span>
                </span>
                {item.badge && pendingCount > 0 ? (
                  <span className={cx("rounded-full px-2 py-0.5 font-mono text-xs", active ? "bg-white text-slate-900" : "bg-teal-50 text-teal-700")}>{pendingCount}</span>
                ) : null}
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-slate-200 p-4">
          <div className="rounded-lg bg-slate-900 p-4 text-white">
            <p className="font-display text-sm font-semibold">Approval first</p>
            <p className="mt-2 text-xs leading-5 text-slate-300">AI can suggest. Agents stay in control before Gmail drafts are created.</p>
          </div>
        </div>
      </aside>

      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 px-4 py-4 backdrop-blur md:px-8">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2 md:hidden">
              <span className="grid h-8 w-8 place-items-center rounded-md bg-slate-900 font-display text-xs font-semibold text-white">TL</span>
              <span className="font-display text-base font-semibold">TriageLab</span>
            </div>
            <p className="mt-2 hidden font-mono text-xs text-slate-500 md:block">{organization?.slug ?? "workspace"}</p>
            <h1 className="mt-1 truncate font-display text-2xl font-semibold tracking-tight text-slate-900 md:text-3xl">{pageTitle(pathname)}</h1>
            <p className="mt-1 hidden text-sm text-slate-500 sm:block">{pageDescription(pathname)}</p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {pendingCount > 0 ? <Link href="/dashboard/tickets" className="hidden rounded-full bg-teal-50 px-3 py-1.5 text-sm font-medium text-teal-700 sm:inline-flex">{pendingCount} pending</Link> : null}
            <Link href="/login" className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 hover:bg-slate-50">
              Account
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-7xl px-4 py-5 pb-24 sm:px-6 md:px-8 md:py-8 md:pb-8">{children}</main>

      <div className="fixed inset-x-0 bottom-0 z-40 border-t border-slate-200 bg-white/95 px-2 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden">
        <div className="mx-auto grid max-w-md" style={{ gridTemplateColumns: `repeat(${visibleNavItems.length}, minmax(0, 1fr))` }}>
          {visibleNavItems.map((item) => {
            const active = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
            return (
              <Link key={item.href} href={item.href} className={cx("relative rounded-lg px-2 py-3 text-center text-xs font-medium", active ? "text-slate-900" : "text-slate-500")}>
                <span className={cx("mx-auto mb-1 grid h-7 w-7 place-items-center rounded-md font-display text-xs", active ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-500")}>{item.mark}</span>
                <span className="block truncate">{item.label}</span>
                {item.badge && pendingCount > 0 ? <span className="absolute right-4 top-2 rounded-full bg-teal-600 px-1.5 text-[10px] text-white">{pendingCount}</span> : null}
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}

