export function StatCard({ label, value, detail, accent = "slate" }: { label: string; value: string | number; detail?: string; accent?: "slate" | "brand" | "rose" | "amber" | "blue" }) {
  const accentClass =
    accent === "brand"
      ? "before:bg-[#928ba7]"
      : accent === "rose"
        ? "before:bg-[#928ba7]"
        : accent === "amber"
          ? "before:bg-[#aaa4ba]"
          : accent === "blue"
            ? "before:bg-[#bbb6c8]"
            : "before:bg-[#d8d3df]";

  return (
    <div className={`relative border-t border-[#ddd7e6] bg-white/50 px-4 py-4 before:absolute before:left-0 before:top-4 before:h-8 before:w-1 before:rounded-r-full first:border-t-0 sm:border-l sm:border-t-0 sm:first:border-l-0 ${accentClass}`}>
      <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">{label}</p>
      <p className="mt-1 font-display text-2xl font-semibold text-slate-950">{value}</p>
      {detail ? <p className="mt-1 text-xs text-slate-500">{detail}</p> : null}
    </div>
  );
}


