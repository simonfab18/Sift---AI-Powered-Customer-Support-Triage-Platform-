import Link from "next/link";

import type { Severity, IntegrationStatus } from "@/lib/mock-data";

export function SeverityBadge({ severity }: { severity: Severity }) {
  return <span className={`badge ${severity}`}>{severity}</span>;
}

export function StatusPill({ children, tone = "neutral" }: { children: React.ReactNode; tone?: string }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

export function MetricCard({ label, value, change, tone }: { label: string; value: string; change: string; tone: string }) {
  return (
    <article className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
      <small className={tone}>{change}</small>
    </article>
  );
}

export function ChartBars({ values }: { values: number[] }) {
  return (
    <div className="chart-bars" aria-label="Ticket volume trend">
      {values.map((value, index) => (
        <span key={`${value}-${index}`} style={{ height: `${value}%` }} />
      ))}
    </div>
  );
}

export function EmptyState({ title, body, action, href }: { title: string; body: string; action: string; href: string }) {
  return (
    <section className="empty-state">
      <div className="empty-icon" />
      <h2>{title}</h2>
      <p>{body}</p>
      <Link className="button primary" href={href}>
        {action}
      </Link>
    </section>
  );
}

export function IntegrationCard({ name, description, status }: { name: string; description: string; status: IntegrationStatus }) {
  const tone = status === "connected" ? "success" : status === "needs setup" ? "warning" : "neutral";
  return (
    <article className="integration-card">
      <div className="integration-icon">{name.slice(0, 1)}</div>
      <div>
        <h3>{name}</h3>
        <p>{description}</p>
      </div>
      <StatusPill tone={tone}>{status}</StatusPill>
    </article>
  );
}



