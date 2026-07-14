import Link from "next/link";

import { MarketingNav } from "@/components/sift/MarketingNav";
import { ChartBars, IntegrationCard, MetricCard, SeverityBadge, StatusPill } from "@/components/sift/SiftComponents";
import { SiftLogo } from "@/components/sift/SiftLogo";
import { chartBars, integrations, metrics, tickets } from "@/lib/mock-data";

const workflow = ["Connect Gmail", "Import conversations", "Sift analyzes", "Agent reviews", "Gmail draft created", "Performance measured"];
const capabilities = ["Gmail connected", "Human approved", "Multi-tenant", "Encrypted OAuth", "Role based access"];

export default function HomePage() {
  return (
    <main className="sift-page">
      <MarketingNav />
      <section className="hero">
        <div className="sift-container hero-grid">
          <div>
            <span className="eyebrow">AI-assisted support operations</span>
            <h1>Turn support noise into clear action.</h1>
            <p>Sift prioritizes incoming conversations, identifies urgency and intent, and prepares accurate replies for your team to approve before they reach Gmail.</p>
            <div className="hero-actions">
              <Link className="button primary" href="/signup">Start free</Link>
              <Link className="button secondary" href="/product">Watch product tour</Link>
            </div>
            <div className="support-note">No credit card required · Human approval by default</div>
            <div className="trust-strip" aria-label="Capabilities">
              {capabilities.map((item) => <span key={item}>{item}</span>)}
            </div>
          </div>
          <ProductPreview />
        </div>
      </section>

      <section className="section">
        <div className="sift-container">
          <div className="section-header">
            <span className="eyebrow">Core workflow</span>
            <h2>One queue. Clear priorities. Faster decisions.</h2>
            <p>Sift brings urgency, sentiment, customer context, and suggested actions into one focused workspace.</p>
          </div>
          <FeatureStory title="See what needs attention first" body="Critical conversations rise automatically based on urgency, customer impact, sentiment, and SLA risk." visual="priority" />
          <FeatureStory title="Understand the reason behind every priority" body="Review intent, category, confidence, and a concise explanation before taking action." visual="analysis" reverse />
          <FeatureStory title="Approve better replies in less time" body="Edit or approve AI-assisted responses, then create a Gmail draft with a complete audit trail." visual="reply" />
        </div>
      </section>

      <section className="section" style={{ background: "white", borderBlock: "1px solid var(--border)" }}>
        <div className="sift-container">
          <div className="section-header">
            <span className="eyebrow">Workflow</span>
            <h2>From inbox noise to approved draft.</h2>
          </div>
          <div className="workflow">
            {workflow.map((step, index) => (
              <article className="workflow-step" key={step}>
                <b>{index + 1}</b>
                <h3>{step}</h3>
                <p style={{ color: "var(--muted)", fontSize: 14 }}>A focused handoff that keeps the team in control.</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="section">
        <div className="sift-container dashboard-grid">
          <div>
            <div className="section-header">
              <span className="eyebrow">Analytics</span>
              <h2>Measure the work behind better support.</h2>
              <p>Track queue volume, first-response time, SLA health, approval rate, and the quality of AI suggestions.</p>
            </div>
            <div className="metrics-grid">{metrics.map((item) => <MetricCard key={item.label} {...item} />)}</div>
          </div>
          <div className="panel">
            <h3>Queue volume trend</h3>
            <ChartBars values={chartBars} />
          </div>
        </div>
      </section>

      <section className="section" style={{ background: "white", borderBlock: "1px solid var(--border)" }}>
        <div className="sift-container feature-story" style={{ borderTop: 0 }}>
          <div>
            <span className="eyebrow">Security</span>
            <h2>Control stays with your team.</h2>
            <p style={{ color: "var(--muted)", lineHeight: 1.7 }}>Workspace isolation, encrypted OAuth storage, role-based access, approval policies, and audit logs help protect support operations.</p>
          </div>
          <div className="panel dark">
            {[
              "Encrypted Gmail OAuth tokens",
              "Workspace-level tenant isolation",
              "Approval policies before drafts",
              "Audit logs and retention controls",
            ].map((item) => <p key={item}>{item}</p>)}
          </div>
        </div>
      </section>

      <section className="section">
        <div className="sift-container">
          <div className="section-header">
            <span className="eyebrow">Integrations</span>
            <h2>Connect the tools your support team already uses.</h2>
          </div>
          <div className="metrics-grid">{integrations.map((item) => <IntegrationCard key={item.name} {...item} />)}</div>
        </div>
      </section>

      <section className="section" style={{ background: "white", borderBlock: "1px solid var(--border)" }}>
        <div className="sift-container">
          <div className="section-header">
            <span className="eyebrow">Pricing preview</span>
            <h2>Simple plans for support operations.</h2>
            <p>Sample pricing shown for frontend testing. Final limits and billing are configured later.</p>
          </div>
          <div className="metrics-grid">
            {[
              ["Starter", "Sample", "Small teams validating Gmail triage."],
              ["Team", "Sample", "Growing queues with approvals and analytics."],
              ["Business", "Sample", "Advanced roles, rules, and controls."],
              ["Enterprise", "Contact", "Security reviews and custom terms."],
            ].map(([name, price, body]) => <article className="panel" key={name}><h3>{name}</h3><strong style={{ fontSize: 32 }}>{price}</strong><p style={{ color: "var(--muted)" }}>{body}</p></article>)}
          </div>
        </div>
      </section>

      <section className="cta-band">
        <div className="sift-container">
          <span className="eyebrow" style={{ color: "#bfc7d8" }}>Sift</span>
          <h2 style={{ fontSize: "clamp(34px, 5vw, 58px)", margin: "10px 0" }}>Make every support decision clearer.</h2>
          <p>Start organizing customer conversations with Sift.</p>
          <div className="hero-actions"><Link className="button primary" href="/signup">Start free</Link><Link className="button secondary" href="/contact">Book a demo</Link></div>
        </div>
      </section>
      <Footer />
    </main>
  );
}

function ProductPreview() {
  return (
    <div className="product-frame" aria-label="Sift product preview">
      <div className="product-frame-inner">
        <div className="mock-toolbar"><strong>Priority queue</strong><StatusPill tone="success">Gmail connected</StatusPill></div>
        <div className="mock-grid">
          <div className="mock-panel">
            <span className="micro">Live queue</span>
            {tickets.slice(0, 4).map((ticket) => (
              <div className="queue-row" key={ticket.id}>
                <span className={`severity-dot ${ticket.severity}`} />
                <div><strong>{ticket.subject}</strong><br /><small>{ticket.customer} · {ticket.sla}</small></div>
              </div>
            ))}
          </div>
          <div className="mock-panel">
            <span className="micro">Selected conversation</span>
            <h3>{tickets[0].subject}</h3>
            <p style={{ color: "var(--muted)", lineHeight: 1.65 }}>{tickets[0].preview}</p>
            <div className="reply-card"><strong>Suggested reply</strong><p>Apologize, confirm the billing issue, unlock the workspace, and offer a same-day reconciliation after approval.</p><Link className="button primary" href="/dashboard/tickets">Approve Gmail draft</Link></div>
          </div>
          <div className="mock-panel">
            <span className="micro">AI analysis</span>
            <div className="analysis-card">
              <p><SeverityBadge severity="critical" /> <StatusPill tone="warning">SLA risk</StatusPill></p>
              <p><strong>Intent</strong><br />Recover payment</p>
              <p><strong>Sentiment</strong><br />Negative</p>
              <p><strong>Confidence</strong><br />94%</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function FeatureStory({ title, body, visual, reverse = false }: { title: string; body: string; visual: string; reverse?: boolean }) {
  const copy = <div><h3 style={{ fontSize: 28, marginBottom: 8 }}>{title}</h3><p style={{ color: "var(--muted)", lineHeight: 1.7 }}>{body}</p></div>;
  const art = <div className="feature-visual"><span className="micro">{visual}</span>{tickets.slice(0, 3).map((ticket) => <div className="queue-row" key={ticket.id}><span className={`severity-dot ${ticket.severity}`} /><div><strong>{ticket.intent}</strong><br /><small>{ticket.category} · {ticket.confidence}% confidence</small></div></div>)}</div>;
  return <div className="feature-story">{reverse ? <>{art}{copy}</> : <>{copy}{art}</>}</div>;
}

function Footer() {
  const columns = ["Product", "Solutions", "Company", "Resources"];
  return <footer className="footer"><div className="sift-container footer-grid"><div><SiftLogo /><p>AI-assisted triage, human-approved replies.</p><small>© Sift · Privacy · Terms · Status · Security</small></div>{columns.map((col) => <div key={col}><strong>{col}</strong><Link href={`/${col.toLowerCase()}`}>{col} overview</Link><Link href="/security">Security</Link><Link href="/contact">Contact</Link></div>)}</div></footer>;
}
