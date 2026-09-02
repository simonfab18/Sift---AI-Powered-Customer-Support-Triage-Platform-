import { cx } from "@/components/ui/cx";
import type { MetricsOverview } from "@/features/tickets/types";

const segments = [
  { key: "critical", label: "Critical", tone: "bg-[#ef4444]" },
  { key: "high", label: "High", tone: "bg-[#f59e0b]" },
  { key: "medium", label: "Medium", tone: "bg-[#facc15]" },
  { key: "low", label: "Low", tone: "bg-[#d8d3df]" },
];

export function TriageMeter({ metrics, embedded = false }: { metrics: MetricsOverview; embedded?: boolean }) {
  const activePriority = metrics.by_active_priority ?? metrics.by_priority;
  const activeTotal = Object.values(activePriority).reduce((sum, count) => sum + count, 0);
  const total = Math.max(1, activeTotal);

  return (
    <div className={cx("h-fit", embedded ? "" : "rounded-lg border border-[#ddd7e6] bg-white/60 p-4 shadow-[0_18px_48px_rgba(72,60,96,0.075)] backdrop-blur-xl")}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#777188]">Active urgency</p>
          <h2 className="mt-1 font-display text-lg font-semibold text-[#201b2d]">Triage meter</h2>
          <p className="mt-1 text-xs text-[#777188]">Only active tickets are counted.</p>
        </div>
        <p className="rounded-md border border-[#ddd7e6] bg-white/50 px-2 py-1 font-mono text-xs text-[#655f73]">{activeTotal} ticket{activeTotal === 1 ? "" : "s"}</p>
      </div>
      <div className="mt-4 flex h-2 overflow-hidden rounded-full bg-white/50">
        {segments.map((segment) => {
          const count = activePriority[segment.key] ?? 0;
          return <span key={segment.key} className={segment.tone} style={{ width: `${(count / total) * 100}%` }} />;
        })}
      </div>
      <div className="mt-4 divide-y divide-[#eee9f2] rounded-md border border-[#eee9f2] bg-white/30">
        {segments.map((segment) => (
          <div key={segment.key} className="flex items-center justify-between gap-3 px-3 py-2 text-xs text-[#655f73]">
            <span className="flex items-center gap-2"><span className={`h-2 w-2 rounded-full ${segment.tone}`} />{segment.label}</span>
            <span className="font-mono text-sm text-[#4f4a5f]">{activePriority[segment.key] ?? 0}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
