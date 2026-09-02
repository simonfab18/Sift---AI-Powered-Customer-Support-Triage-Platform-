import { GmailConnectionPanel } from "@/features/gmail/components/GmailConnectionPanel";
import { SettingsNav } from "@/features/settings/components/SettingsNav";

export default function GmailSettingsPage() {
  return (
    <section className="space-y-6">
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">Integrations</p>
        <h2 className="font-display text-3xl font-semibold tracking-tight text-slate-950">Gmail</h2>
        <p className="mt-2 max-w-2xl text-slate-600">Connect support inboxes, define source ownership, and monitor imports without leaving the settings workspace.</p>
      </div>
      <SettingsNav />
      <GmailConnectionPanel />
    </section>
  );
}


