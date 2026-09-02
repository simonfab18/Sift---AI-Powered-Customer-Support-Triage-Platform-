import { GmailConnectionPanel } from "@/features/gmail/components/GmailConnectionPanel";
import { SettingsNav } from "@/features/settings/components/SettingsNav";

export default function SettingsPage() {
  return (
    <section className="space-y-6">
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">Owner/Admin</p>
        <h2 className="font-display text-3xl font-semibold tracking-tight text-slate-950">Settings</h2>
        <p className="mt-2 max-w-2xl text-slate-600">A structured control room for Gmail, teammates, routing, knowledge, and pilot safety.</p>
      </div>
      <SettingsNav />
      <GmailConnectionPanel />
    </section>
  );
}


