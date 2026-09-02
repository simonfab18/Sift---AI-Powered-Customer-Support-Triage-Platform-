"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { SiftMark } from "@/components/sift/SiftLogo";
import { cx } from "@/components/ui/cx";
import { getStoredOrganizationId } from "@/features/organizations/components/OrganizationManager";
import { getMetricsOverview } from "@/features/tickets/api";
import type { MetricsOverview } from "@/features/tickets/types";
import { getMe } from "@/lib/api-client";
import type { Organization } from "@/lib/api-types";
import { createClient } from "@/lib/supabase/client";

type NavIconName = "dashboard" | "queue" | "analytics" | "settings";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: "dashboard" as NavIconName, helper: "Command center" },
  { href: "/dashboard/tickets", label: "Triage queue", icon: "queue" as NavIconName, helper: "Tickets & actions", badge: "pending" },
  { href: "/dashboard/analytics", label: "Analytics", icon: "analytics" as NavIconName, helper: "Owner insights", ownerOnly: true },
  { href: "/dashboard/settings", label: "Settings", icon: "settings" as NavIconName, helper: "Gmail, team, rules", ownerOnly: true },
];
function NavIcon({ name }: { name: NavIconName }) {
  const common = "h-5 w-5";
  if (name === "dashboard") {
    return (
      <svg className={common} viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <rect x="4" y="4" width="6.5" height="7" rx="1.6" stroke="currentColor" strokeWidth="2.15" />
        <rect x="13.5" y="4" width="6.5" height="12" rx="1.6" stroke="currentColor" strokeWidth="2.15" />
        <rect x="4" y="14" width="6.5" height="6" rx="1.6" stroke="currentColor" strokeWidth="2.15" />
      </svg>
    );
  }
  if (name === "queue") {
    return (
      <svg className={common} viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M7 6.5h10M7 12h10M7 17.5h6" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
        <path d="M4.5 6.5h.01M4.5 12h.01M4.5 17.5h.01" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
      </svg>
    );
  }
  if (name === "analytics") {
    return (
      <svg className={common} viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M5 19V10.5M12 19V5M19 19v-7" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
        <path d="M4 19.5h16" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
        <path d="M5 10.5l4-3 3 2.5 5-5" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" opacity="0.65" />
      </svg>
    );
  }
  return (
    <svg className={common} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 15.25a3.25 3.25 0 1 0 0-6.5 3.25 3.25 0 0 0 0 6.5Z" stroke="currentColor" strokeWidth="2.15" />
      <path d="M18.4 13.7c.08-.55.08-1.1 0-1.65l1.75-1.35-1.8-3.1-2.1.85a6.8 6.8 0 0 0-1.45-.85L14.48 5h-4.96L9.2 7.6c-.52.22-1 .5-1.45.85l-2.1-.85-1.8 3.1 1.75 1.35a6.06 6.06 0 0 0 0 1.65l-1.75 1.35 1.8 3.1 2.1-.85c.45.35.93.63 1.45.85l.32 2.6h4.96l.32-2.6c.52-.22 1-.5 1.45-.85l2.1.85 1.8-3.1-1.75-1.35Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
    </svg>
  );
}

function OwnerAdminAccessChecking() {
  return (
    <section className="rounded-xl border border-white/60 bg-white/65 p-6 text-sm text-[#746d80] shadow-[0_22px_60px_rgba(72,60,96,0.075)] backdrop-blur-2xl sm:p-8">
      Checking workspace access...
    </section>
  );
}
function OwnerAdminAccessDenied() {
  return (
    <section className="rounded-xl border border-white/60 bg-white/65 p-6 shadow-[0_22px_60px_rgba(72,60,96,0.075)] backdrop-blur-2xl sm:p-8">
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[#777188]">Owner/Admin only</p>
      <h2 className="mt-2 font-display text-2xl font-semibold tracking-tight text-[#201b2d]">Settings are not available for agent accounts.</h2>
      <p className="mt-3 max-w-2xl text-sm leading-6 text-[#746d80]">
        Agents can work tickets, review replies, and resolve conversations. Gmail setup, routing, team management, analytics, and workspace controls stay with owners and admins.
      </p>
      <div className="mt-5 flex flex-wrap gap-2">
        <Link href="/dashboard/tickets" className="rounded-lg border border-[#d8d0e5] bg-white/75 px-4 py-2 text-sm font-semibold text-[#4e475d] transition hover:bg-white">Open triage queue</Link>
        <Link href="/dashboard" className="rounded-lg border border-white/70 bg-white/45 px-4 py-2 text-sm font-semibold text-[#6a6578] transition hover:bg-white/70">Back to dashboard</Link>
      </div>
    </section>
  );
}

function pageTitle(pathname: string) {
  if (pathname.includes("/tickets/")) return "Ticket detail";
  if (pathname.includes("/analytics")) return "Analytics";
  if (pathname.includes("/tickets")) return "Triage queue";
  if (pathname.includes("/settings/gmail")) return "Gmail";
  if (pathname.includes("/settings/audit")) return "Audit log";
  if (pathname.includes("/settings/team")) return "Team";
  if (pathname.includes("/settings/knowledge")) return "Knowledge";
  if (pathname.includes("/settings/routing")) return "Routing";
  if (pathname.includes("/settings/readiness")) return "Readiness";
  if (pathname.includes("/settings/workspace")) return "Workspace";
  if (pathname.includes("/account")) return "Account";
  if (pathname.includes("/settings/billing")) return "Billing";
  if (pathname.includes("/settings")) return "Settings";
  if (pathname.includes("/organizations")) return "Organizations";
  return "Dashboard";
}

function pageDescription(pathname: string) {
  if (pathname.includes("/tickets/")) return "Review the thread, AI reasoning, approval state, and Gmail draft trail.";
  if (pathname.includes("/tickets")) return "Prioritize, filter, assign, resolve, and save the views your team actually uses.";
  if (pathname.includes("/analytics")) return "Track support volume, SLA performance, Gmail sync, and AI quality signals.";
  if (pathname.includes("/settings/gmail")) return "Connect support inboxes, define source ownership, and monitor imports.";
  if (pathname.includes("/settings/team")) return "Manage teammates, roles, and workspace access.";
  if (pathname.includes("/settings/knowledge")) return "Control the policies, facts, and references AI can use.";
  if (pathname.includes("/settings/routing")) return "Tune assignment rules, priority floors, and approval gates.";
  if (pathname.includes("/settings/readiness")) return "Review pilot controls, lifecycle messaging, data controls, and release checks.";
  if (pathname.includes("/settings/workspace")) return "Set signatures, SLA targets, business hours, and workspace defaults.";
  if (pathname.includes("/settings/audit")) return "Inspect administrative activity and export audit evidence.";
  if (pathname.includes("/account")) return "Manage your profile, email, password, and onboarding context.";
  if (pathname.includes("/settings/billing")) return "Free pilot status, plan notes, and future billing controls.";
  if (pathname.includes("/settings")) return "Configure Gmail, team operations, routing, and pilot controls.";
  if (pathname.includes("/organizations")) return "Choose the workspace you want to operate from.";
  return "A quiet command center for Gmail support triage.";
}

function workspaceInitials(name?: string | null) {
  if (!name) return "SW";
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("") || "SW";
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const supabase = createClient();
  const [organization, setOrganization] = useState<Organization | null>(null);
  const [metrics, setMetrics] = useState<MetricsOverview | null>(null);
  const [sidebarHidden, setSidebarHidden] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [contextLoaded, setContextLoaded] = useState(false);
  const [profile, setProfile] = useState<{ id: string; email: string | null; fullName: string; companyName: string } | null>(null);

  useEffect(() => {
    const savedPreference = window.localStorage.getItem("sift-sidebar-hidden");
    if (savedPreference === "true") setSidebarHidden(true);
  }, []);

  useEffect(() => {
    async function loadContext() {
      const { data } = await supabase.auth.getSession();
      const accessToken = data.session?.access_token;
      if (!accessToken) {
        setContextLoaded(true);
        return;
      }
      const user = data.session?.user;
      const metadata = user?.user_metadata ?? {};
      const firstName = typeof metadata.first_name === "string" ? metadata.first_name : "";
      const lastName = typeof metadata.last_name === "string" ? metadata.last_name : "";
      const metadataFullName = typeof metadata.full_name === "string" ? metadata.full_name : "";
      const fullName = metadataFullName || [firstName, lastName].filter(Boolean).join(" ") || user?.email || "Account";
      const companyName = typeof metadata.company_name === "string" && metadata.company_name ? metadata.company_name : "No company set";
      setProfile({ id: user?.id ?? "", email: user?.email ?? null, fullName, companyName });
      const me = await getMe(accessToken);
      const stored = getStoredOrganizationId();
      const selected = me.organizations.find((item) => item.id === stored) ?? me.organizations[0] ?? null;
      setOrganization(selected);
      if (selected && companyName === "No company set") {
        setProfile((current) => current ? { ...current, companyName: selected.name } : current);
      }
      if (selected) {
        try {
          setMetrics(await getMetricsOverview(selected.id, accessToken));
        } catch {
          setMetrics(null);
        }
      }
      setContextLoaded(true);
    }
    void loadContext();
  }, [pathname, supabase]);

  const role = organization?.role ?? "agent";
  const canSeeOwnerSettings = role === "owner" || role === "admin";
  const restrictedOwnerPath = pathname.startsWith("/dashboard/settings") || pathname.startsWith("/dashboard/analytics");
  const showOwnerAccessLoading = restrictedOwnerPath && !contextLoaded;
  const showOwnerAccessDenied = Boolean(contextLoaded && organization && restrictedOwnerPath && !canSeeOwnerSettings);
  const pendingCount = metrics?.active_tickets ?? 0;
  const visibleNavItems = navItems.filter((item) => !item.ownerOnly || canSeeOwnerSettings);

  function toggleSidebar() {
    setSidebarHidden((current) => {
      const next = !current;
      window.localStorage.setItem("sift-sidebar-hidden", String(next));
      return next;
    });
  }

  async function handleLogout() {
    window.localStorage.removeItem("support-triage:selected-org-id");
    window.localStorage.removeItem("sift-selected-organization-id");
    window.localStorage.removeItem("sift-onboarding-profile");
    setProfileOpen(false);
    await supabase.auth.signOut();
    router.push("/login");
    router.refresh();
  }

  return (
    <div className={cx("min-h-screen bg-transparent text-slate-950 transition-[padding] duration-300 ease-out", sidebarHidden ? "md:pl-28" : "md:pl-72")}>
      <aside className={cx("fixed inset-y-0 left-0 z-30 hidden overflow-hidden border-r border-white/50 bg-white/60 text-slate-950 shadow-[18px_0_60px_rgba(72,60,96,0.08)] backdrop-blur-2xl transition-[width] duration-300 ease-out md:flex md:flex-col", sidebarHidden ? "w-28" : "w-72")}>
        <div className={cx("px-5 py-5 transition-all duration-300", sidebarHidden && "px-4")}>
          <div className="flex items-center justify-between gap-3">
            <Link href="/dashboard" className={cx("flex min-w-0 items-center gap-3", sidebarHidden && "shrink-0")} aria-label="Sift dashboard">
              <SiftMark />
              <span className={cx("overflow-hidden whitespace-nowrap transition-all duration-200", sidebarHidden ? "w-0 opacity-0" : "w-36 opacity-100")}>
                <span className="block font-display text-xl font-semibold tracking-tight">Sift</span>
                <span className="block text-xs text-slate-500">Support operations</span>
              </span>
            </Link>
            <button
              type="button"
              onClick={toggleSidebar}
              aria-label={sidebarHidden ? "Expand sidebar" : "Collapse sidebar"}
              title={sidebarHidden ? "Expand sidebar" : "Collapse sidebar"}
              className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-[#d8d0e5] bg-white/75 text-[#554d66] shadow-[0_10px_24px_rgba(72,60,96,0.08)] transition duration-300 hover:bg-white hover:text-[#201b2d] hover:shadow-[0_14px_30px_rgba(72,60,96,0.12)]"
            >
              {sidebarHidden ? <span aria-hidden="true">&#8250;</span> : <span aria-hidden="true">&#8249;</span>}
            </button>
          </div>
        </div>

        <div className={cx("rounded-lg border border-white/60 bg-white/50 shadow-[0_16px_36px_rgba(72,60,96,0.06)] transition-all duration-300", sidebarHidden ? "mx-3 p-2.5" : "mx-4 p-3")}>
          <div className={cx("flex items-start gap-3", sidebarHidden && "justify-center")}>
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-white/75 text-xs font-semibold text-[#4c4658] shadow-[0_8px_20px_rgba(72,60,96,0.06)]">{workspaceInitials(organization?.name)}</span>
            <div className={cx("min-w-0 flex-1 transition-all duration-200", sidebarHidden && "hidden")}>
              <p className="truncate text-sm font-semibold text-slate-950">{organization?.name ?? "No workspace selected"}</p>
              <p className="mt-0.5 capitalize text-xs text-slate-500">{organization?.role ?? "Choose workspace"}</p>
            </div>
            <span className={cx("rounded-md border border-white/50 bg-white/50 px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-slate-600", sidebarHidden && "hidden")}>Pilot</span>
          </div>
          <Link href="/dashboard/organizations" className={cx("mt-3 inline-flex text-xs font-semibold text-[#655f73] hover:text-[#201b2d]", sidebarHidden && "hidden")}>
            Change workspace
          </Link>
        </div>

        <nav className={cx("flex-1 space-y-1 py-5 transition-all duration-300", sidebarHidden ? "px-2" : "px-3")}>
          {visibleNavItems.map((item) => {
            const active = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cx(
                  "group relative flex items-center gap-3 rounded-lg py-3 text-sm font-semibold transition",
                  sidebarHidden ? "justify-center px-0" : "px-3",
                  active ? "bg-white/70 text-[#201b2d] ring-1 ring-white/70" : "text-[#6a6578] hover:bg-white/40 hover:text-[#201b2d]",
                )}
              >
                <span className={cx("grid h-10 w-10 shrink-0 place-items-center rounded-lg border shadow-[0_8px_20px_rgba(72,60,96,0.05)] transition duration-300", active ? "border-[#cfc7dd] bg-white/80 text-[#2f2939]" : "border-white/60 bg-white/45 text-[#5f596d] group-hover:border-[#d8d0e5] group-hover:bg-white/70 group-hover:text-[#2f2939]")}><NavIcon name={item.icon} /></span>
                <span className={cx("min-w-0 flex-1 overflow-hidden transition-all duration-200", sidebarHidden ? "w-0 opacity-0" : "w-auto opacity-100")}>
                  <span className="block truncate">{item.label}</span>
                  <span className={cx("block truncate text-xs font-normal", active ? "text-[#777188]" : "text-[#9b94a5]")}>{item.helper}</span>
                </span>
                {item.badge && pendingCount > 0 ? (
                  <span className={cx("rounded-full font-mono text-xs transition-all", sidebarHidden ? "absolute right-0 top-1 px-1.5 py-0 text-[10px]" : "px-2 py-0.5", active ? "bg-white text-slate-950" : "bg-slate-100 text-slate-700")}>{pendingCount}</span>
                ) : null}
              </Link>
            );
          })}
        </nav>

        <div className={cx("border-t border-white/50 p-4 transition-opacity duration-200", sidebarHidden && "pointer-events-none opacity-0")}>
          <div className="rounded-lg border border-white/60 bg-white/50 p-4 shadow-[0_16px_36px_rgba(72,60,96,0.06)]">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">Operating mode</p>
            <p className="mt-2 font-display text-sm font-semibold text-slate-950">Approval first</p>
            <p className="mt-2 text-xs leading-5 text-slate-600">AI drafts stay human-reviewed. Live sending remains off for the free pilot.</p>
          </div>
        </div>
      </aside>

      <header className="sticky top-0 z-20 border-b border-white/50 bg-white/[0.62] px-4 py-4 shadow-[0_10px_34px_rgba(72,60,96,0.055)] backdrop-blur-xl md:px-8">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
          <div className="flex min-w-0 items-start gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2 md:hidden">
                <SiftMark />
                <span className="font-display text-base font-semibold">Sift</span>
              </div>
              <p className="mt-2 hidden text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500 md:block">{organization?.slug ?? "workspace"}</p>
              <h1 className="mt-1 truncate font-display text-2xl font-semibold tracking-tight text-slate-950 md:text-3xl">{pageTitle(pathname)}</h1>
              <p className="mt-1 hidden max-w-3xl text-sm leading-6 text-slate-600 sm:block">{pageDescription(pathname)}</p>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {pendingCount > 0 ? <Link href="/dashboard/tickets" className="hidden rounded-md border border-[#ddd7e6] bg-white/50 px-3 py-1.5 text-sm font-semibold text-[#5f5a70] sm:inline-flex">{pendingCount} active</Link> : null}
            <div className="relative">
              <button
                type="button"
                onClick={() => setProfileOpen((open) => !open)}
                aria-label="Open account menu"
                className="grid h-11 w-11 place-items-center rounded-full border border-white/70 bg-white/70 font-display text-sm font-semibold text-[#4e475d] shadow-[0_12px_30px_rgba(72,60,96,0.09)] transition duration-300 hover:scale-[1.02] hover:bg-white"
              >
                {workspaceInitials(profile?.fullName || profile?.email || "Account")}
              </button>
              {profileOpen ? (
                <div className="absolute right-0 mt-3 w-80 rounded-xl border border-white/70 bg-white/95 p-3 text-sm shadow-[0_24px_70px_rgba(72,60,96,0.16)] backdrop-blur-xl">
                  <div className="rounded-lg bg-[#f7f4fb] p-3">
                    <p className="truncate font-display text-base font-semibold text-slate-950">{profile?.fullName ?? "Account"}</p>
                    <p className="mt-1 truncate text-xs text-slate-500">{profile?.email ?? "No email loaded"}</p>
                    <p className="mt-2 truncate text-xs font-medium text-[#6a6578]">{profile?.companyName ?? organization?.name ?? "No company set"}</p>
                    <p className="mt-2 break-all font-mono text-[11px] text-slate-400">Person ID: {profile?.id || "Not loaded"}</p>
                  </div>
                  <div className="mt-2 grid gap-1">
                    <Link href="/dashboard/account" onClick={() => setProfileOpen(false)} className="rounded-lg px-3 py-2 font-semibold text-slate-700 transition hover:bg-[#f7f4fb]">Account</Link>
                    <Link href="/dashboard/settings/billing" onClick={() => setProfileOpen(false)} className="rounded-lg px-3 py-2 font-semibold text-slate-700 transition hover:bg-[#f7f4fb]">Billing</Link>
                    <button type="button" onClick={() => void handleLogout()} className="rounded-lg px-3 py-2 text-left font-semibold text-slate-700 transition hover:bg-[#f7f4fb]">Logout</button>
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-7xl px-4 py-5 pb-24 sm:px-6 md:px-8 md:py-8 md:pb-8">
        {showOwnerAccessLoading ? <OwnerAdminAccessChecking /> : showOwnerAccessDenied ? <OwnerAdminAccessDenied /> : children}
      </main>

      <div className="fixed inset-x-0 bottom-0 z-40 border-t border-slate-200 bg-white/95 px-2 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden">
        <div className="mx-auto grid max-w-md" style={{ gridTemplateColumns: `repeat(${visibleNavItems.length}, minmax(0, 1fr))` }}>
          {visibleNavItems.map((item) => {
            const active = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
            return (
              <Link key={item.href} href={item.href} className={cx("relative rounded-lg px-2 py-3 text-center text-xs font-semibold", active ? "text-[#655f73]" : "text-slate-500")}>
                <span className={cx("mx-auto mb-1 grid h-7 w-7 place-items-center rounded-md", active ? "bg-[#756f9f] text-white" : "bg-slate-100 text-slate-500")}><NavIcon name={item.icon} /></span>
                <span className="block truncate">{item.label}</span>
                {item.badge && pendingCount > 0 ? <span className="absolute right-4 top-2 rounded-full bg-[#756f9f] px-1.5 text-[10px] text-white">{pendingCount}</span> : null}
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}
