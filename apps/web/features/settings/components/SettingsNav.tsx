import Link from "next/link";

const settings = [
  { href: "/dashboard/settings", label: "Integrations", description: "Gmail connection and import controls", mark: "G" },
  { href: "/dashboard/settings/team", label: "Team", description: "Roles, owners, admins, and agents", mark: "T" },
  { href: "/dashboard/settings/workspace", label: "Workspace", description: "Signatures, SLA targets, and hours", mark: "W" },
  { href: "/dashboard/settings/knowledge", label: "Knowledge", description: "Policies, FAQs, facts, and sources", mark: "K" },
  { href: "/dashboard/settings/routing", label: "Routing", description: "Assignment and approval rules", mark: "R" },
  { href: "/dashboard/settings/audit", label: "Audit", description: "Activity review and exports", mark: "A" },
  { href: "/dashboard/settings/readiness", label: "Readiness", description: "Pilot controls and release checks", mark: "P" },
  { href: "/dashboard/settings/billing", label: "Billing", description: "Free pilot status and future plan controls", mark: "B" },
  { href: "/dashboard/account", label: "Account", description: "Profile, email, password, and personal context", mark: "U" },
];

export function SettingsNav() {
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      {settings.map((item) => (
        <Link key={item.href} href={item.href} className="group grid grid-cols-[auto_1fr] gap-3 rounded-lg border border-white/50 bg-white/60 backdrop-blur-xl p-4 shadow-[0_18px_48px_rgba(72,60,96,0.075)] transition hover:border-slate-300 hover:bg-white/30">
          <span className="grid h-10 w-10 place-items-center rounded-md border border-slate-200 bg-white/30 font-display text-sm font-semibold text-slate-700 group-hover:border-[#d8d2e4] group-hover:bg-white/60 group-hover:text-[#5f5a70]">{item.mark}</span>
          <span className="min-w-0">
            <span className="block font-display text-base font-semibold text-slate-950">{item.label}</span>
            <span className="mt-1 block text-sm leading-5 text-slate-500">{item.description}</span>
          </span>
        </Link>
      ))}
    </div>
  );
}



