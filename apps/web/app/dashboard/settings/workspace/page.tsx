import { SettingsNav } from "@/features/settings/components/SettingsNav";
import { WorkspaceSettings } from "@/features/settings/components/WorkspaceSettings";

export default function WorkspaceSettingsPage() {
  return (
    <section className="space-y-6">
      <div>
        <p className="font-mono text-xs uppercase tracking-wide text-slate-500">Workspace</p>
        <h2 className="font-display text-3xl font-semibold tracking-tight text-slate-900">Preferences</h2>
        <p className="mt-2 max-w-2xl text-slate-600">Configure reply defaults and workspace behavior for the pilot.</p>
      </div>
      <SettingsNav />
      <WorkspaceSettings />
    </section>
  );
}


