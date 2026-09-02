import { OrganizationManager } from "@/features/organizations/components/OrganizationManager";

export default function OrganizationsPage() {
  return (
    <section className="space-y-6">
      <div>
        <p className="font-mono text-xs uppercase tracking-wide text-slate-500">Workspace</p>
        <h2 className="font-display text-3xl font-semibold tracking-tight text-slate-900">Organizations</h2>
        <p className="mt-2 max-w-2xl text-slate-600">Create or select the workspace that owns tickets, teammates, and Gmail connections.</p>
      </div>
      <OrganizationManager />
    </section>
  );
}

