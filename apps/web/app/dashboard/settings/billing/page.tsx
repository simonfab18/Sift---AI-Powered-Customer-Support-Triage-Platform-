import { SettingsNav } from "@/features/settings/components/SettingsNav";

export default function BillingSettingsPage() {
  return (
    <section className="space-y-6">
      <div>
        <p className="font-mono text-xs uppercase tracking-wide text-slate-500">Free pilot</p>
        <h2 className="font-display text-3xl font-semibold tracking-tight text-slate-900">Billing</h2>
        <p className="mt-2 max-w-2xl text-slate-600">Sift is currently free to use while the Gmail-first pilot is being hardened.</p>
      </div>
      <SettingsNav />
      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <section className="rounded-lg border border-white/60 bg-white/60 p-6 shadow-[0_18px_48px_rgba(72,60,96,0.075)] backdrop-blur-xl">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Current plan</p>
          <h3 className="mt-3 font-display text-2xl font-semibold text-slate-950">Free pilot status</h3>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">There is no paid subscription, invoice, or payment method required right now. Usage limits exist only to protect the free pilot and Gemini quota.</p>
          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            <div className="rounded-md border border-white/60 bg-white/50 p-4"><span className="text-xs text-slate-500">Billing</span><strong className="mt-1 block">Off</strong></div>
            <div className="rounded-md border border-white/60 bg-white/50 p-4"><span className="text-xs text-slate-500">Payment method</span><strong className="mt-1 block">Not needed</strong></div>
            <div className="rounded-md border border-white/60 bg-white/50 p-4"><span className="text-xs text-slate-500">Live sending</span><strong className="mt-1 block">Disabled</strong></div>
          </div>
        </section>
        <aside className="rounded-lg border border-white/60 bg-white/60 p-6 shadow-[0_18px_48px_rgba(72,60,96,0.075)] backdrop-blur-xl">
          <h3 className="font-display text-lg font-semibold text-slate-950">What changes later?</h3>
          <p className="mt-2 text-sm leading-6 text-slate-600">When Sift moves beyond the free pilot, billing will show plan limits, invoices, payment method, and upgrade controls here.</p>
        </aside>
      </div>
    </section>
  );
}