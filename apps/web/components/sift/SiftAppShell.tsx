"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { SiftLogo } from "@/components/sift/SiftLogo";
import { getStoredOrganizationId, setStoredOrganizationId } from "@/features/organizations/components/OrganizationManager";
import { getMetricsOverview } from "@/features/tickets/api";
import { getMe } from "@/lib/api-client";
import type { Organization } from "@/lib/api-types";
import { createClient } from "@/lib/supabase/client";

const mainNav = [
  ["Overview", "/app", "O"],
  ["Inbox", "/app/inbox", "I"],
  ["Approvals", "/app/approvals", "A"],
  ["Customers", "/app/customers", "C"],
  ["Analytics", "/app/analytics", "N"],
];

const opsNav = [
  ["Import Gmail", "/app/integrations", "G"],
  ["Workspace", "/app/settings/workspace", "W"],
  ["Team & roles", "/app/team", "T"],
  ["Automation", "/app/automation", "R", "admin"],
  ["Knowledge", "/app/knowledge", "K", "admin"],
];

export function SiftAppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const supabase = createClient();
  const [organization, setOrganization] = useState<Organization | null>(null);
  const [ticketUsage, setTicketUsage] = useState<number | null>(null);

  useEffect(() => {
    async function loadWorkspace() {
      const { data } = await supabase.auth.getSession();
      const accessToken = data.session?.access_token;
      if (!accessToken) return;
      try {
        const me = await getMe(accessToken);
        const stored = getStoredOrganizationId();
        const selected = me.organizations.find((item) => item.id === stored) ?? me.organizations[0] ?? null;
        if (!selected) return;
        setStoredOrganizationId(selected.id);
        setOrganization(selected);
        const metrics = await getMetricsOverview(selected.id, accessToken);
        setTicketUsage(metrics.total_tickets);
      } catch {
        setOrganization(null);
        setTicketUsage(null);
      }
    }
    void loadWorkspace();
  }, [supabase]);

  const workspaceName = organization?.name ?? "No workspace selected";
  const workspaceRole = organization?.role ?? "Sign in to load workspace";
  const canManageWorkspace = workspaceRole === "owner" || workspaceRole === "admin";
  const usageLabel = ticketUsage === null ? "Waiting for data" : `${ticketUsage} conversations`;
  const usageWidth = ticketUsage === null ? "0%" : `${Math.min(100, Math.max(8, ticketUsage))}%`;

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <div className="sidebar-brand">
          <SiftLogo href="/app" dark />
        </div>
        <div className="workspace-card">
          <span className="micro">Workspace</span>
          <strong>{workspaceName}</strong>
          <small>{workspaceRole}</small>
        </div>
        <AppNav title="Main" items={mainNav} pathname={pathname} />
        <AppNav title="Operations" items={opsNav.filter(([, , , required]) => !required || canManageWorkspace)} pathname={pathname} />
        <div className="sidebar-bottom">
          <div className="usage-card">
            <span>{usageLabel}</span>
            <small>loaded from backend metrics</small>
            <div><i style={{ width: usageWidth }} /></div>
          </div>
          <Link className="app-nav-link" href="/app/settings">
            <b>S</b>
            <span>Settings</span>
          </Link>
        </div>
      </aside>
      <div className="app-main">
        <header className="app-topbar">
          <div>
            <span className="breadcrumb">{workspaceName} / Sift</span>
            <strong>Support operations</strong>
          </div>
          <div className="topbar-actions">
            <label className="search-box">
              <span>Search tickets, customers, rules</span>
              <kbd>Ctrl K</kbd>
            </label>
            <Link className="button secondary" href="/app/integrations">
              Import conversations
            </Link>
            <Link className="button primary" href="/app/integrations">
              Connect Gmail
            </Link>
          </div>
        </header>
        <main className="app-content">{children}</main>
      </div>
      <nav className="mobile-tabbar" aria-label="Mobile navigation">
        {[...mainNav.slice(0, 3), ["Import", "/app/integrations", "G"]].map(([label, href, mark]) => (
          <Link key={href} href={href}>
            <b>{mark}</b>
            <span>{label}</span>
          </Link>
        ))}
      </nav>
    </div>
  );
}

function AppNav({ title, items, pathname }: { title: string; items: string[][]; pathname: string }) {
  return (
    <nav className="app-nav" aria-label={title}>
      <span className="micro">{title}</span>
      {items.map(([label, href, mark]) => {
        const active = pathname === href || (href !== "/app" && pathname.startsWith(href));
        return (
          <Link key={href} className={`app-nav-link ${active ? "active" : ""}`} href={href}>
            <b>{mark}</b>
            <span>{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}



