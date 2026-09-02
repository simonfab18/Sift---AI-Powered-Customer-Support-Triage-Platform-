import { cx } from "./cx";

const urgencyTone = "border-[#d8d2e4] bg-white/50 text-[#5f5a70] before:bg-[#aaa4ba]";

export function UrgencyRail({ className }: { priority: string; className?: string }) {
  return <span className={cx("block w-1.5 rounded-full bg-[#aaa4ba]/70", className)} aria-hidden="true" />;
}

export function UrgencyBadge({ priority }: { priority: string }) {
  return (
    <span className={cx("inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-semibold capitalize before:h-2 before:w-2 before:rounded-full", urgencyTone)}>
      {priority}
    </span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const styles =
    status === "resolved"
      ? "border-[#d8d2e4] bg-white/50 text-[#5f5a70]"
      : status === "spam"
        ? "border-[#d8d2e4] bg-white/40 text-[#6f6a7c]"
        : status === "draft_created"
          ? "border-[#d8d2e4] bg-white/50 text-[#5f5a70]"
          : "border-[#d8d2e4] bg-white/50 text-[#655f73]";
  return <span className={cx("inline-flex rounded-md border px-2 py-1 text-xs font-semibold capitalize", styles)}>{status.replaceAll("_", " ")}</span>;
}


