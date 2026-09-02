import { SettingsNav } from "@/features/settings/components/SettingsNav";
import { TeamSettings } from "@/features/settings/components/TeamSettings";

export default function TeamSettingsPage() {
  return (
    <section className="space-y-6">
      <div>
        <p className="font-mono text-xs uppercase tracking-wide text-slate-500">Owner/Admin</p>
        <h2 className="font-display text-3xl font-semibold tracking-tight text-slate-900">Team</h2>
        <p className="mt-2 max-w-2xl text-slate-600">Invite teammates and keep roles aligned with responsibilities.</p>
      </div>
      <SettingsNav />
      <TeamSettings />
    </section>
  );
}


