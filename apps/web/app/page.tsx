import Link from "next/link";

import { MarketingNav } from "@/components/sift/MarketingNav";
import { ScrollReveal } from "@/components/sift/ScrollReveal";
import { MarketingFooter } from "@/components/sift/MarketingPage";

const queueItems = [
  { subject: "Payment failed before launch", name: "Maya Chen", time: "38m left" },
  { subject: "API returning intermittent 500 errors", name: "Elliot Park", time: "1h 12m left" },
  { subject: "Refund requested for annual plan", name: "Nora Williams", time: "2h left" },
  { subject: "Unable to access administrator account", name: "Luis Romero", time: "4h left" },
];

const featureBlocks = [
  {
    label: "Prioritize",
    title: "Bring the right customer conversation to the top.",
    body: "Sift reads Gmail conversations, detects urgency and intent, and keeps your team focused on the replies that matter first.",
    cta: "Explore triage",
    href: "/features",
    tint: "lavender",
  },
  {
    label: "Approve",
    title: "Draft faster while humans stay fully in control.",
    body: "AI prepares a reply with context, but agents approve, edit, and create Gmail drafts only when they are ready.",
    cta: "See approvals",
    href: "/how-it-works",
    tint: "cream",
  },
  {
    label: "Operate",
    title: "Track queue health without opening ten tools.",
    body: "Owners and admins get a clear view of workload, SLA risk, failed jobs, inbox health, and AI quality signals.",
    cta: "View analytics",
    href: "/product",
    tint: "mint",
  },
];

const plans = [
  { id: "free", name: "Free", audience: "Small Gmail pilots", price: "$0", cta: "Start free", featured: false, features: ["1 workspace", "Gmail import", "Human approval", "Basic analytics"] },
  { id: "starter", name: "Starter", audience: "Solo operators", price: "$19", cta: "Choose Starter", featured: false, features: ["3 inboxes", "Saved views", "Reply drafts", "Audit trail"] },
  { id: "team", name: "Team", audience: "Growing support teams", price: "$49", cta: "Choose Team", featured: true, features: ["10 inboxes", "Team roles", "Routing rules", "Priority support"] },
  { id: "business", name: "Business", audience: "Controlled operations", price: "$129", cta: "Talk to us", featured: false, features: ["Advanced controls", "Security review", "Custom limits", "Admin reporting"] },
];

export default function HomePage() {
  return (
    <main className="landing-page">
      <ScrollReveal />
      <MarketingNav />
      <section className="landing-hero" id="top">
        <FloatingShapes />
        <div className="sift-container landing-hero-grid">
          <div className="landing-hero-copy reveal-up">
            <span className="landing-eyebrow">AI-assisted support operations</span>
            <h1>
              Turn support noise into <span>clear action.</span>
            </h1>
            <p>
              Sift prioritizes incoming conversations, identifies urgency and intent, and prepares accurate replies for your team to approve before they reach Gmail.
            </p>
            <div className="landing-actions">
              <Link className="landing-button primary" href="/signup">Start free</Link>
              <Link className="landing-button secondary" href="/product">Watch product tour</Link>
            </div>
            <p className="landing-reassurance">No credit card required - Human approval by default</p>
            <div className="landing-trust" aria-label="Product guarantees">
              {["Gmail connected", "Human approved", "Multi-tenant", "Encrypted OAuth", "Role based access"].map((item) => <span key={item}>{item}</span>)}
            </div>
          </div>
          <HeroMockup />
        </div>
      </section>

      <section className="landing-section" id="features">
        <div className="sift-container section-split">
          <SectionCopy label="Features" title="Everything your Gmail support queue needs to feel less chaotic." body="Each workflow is built around clarity: what happened, why it matters, what to do next, and who needs to approve it." cta="See all features" href="/features" />
          <InteractivePreview />
        </div>
      </section>

      <section className="landing-section soft-block" id="how-it-works">
        <div className="sift-container">
          <SectionCopy centered label="How it works" title="From inbox noise to approved Gmail draft in one calm flow." body="Connect Gmail, import conversations, let Sift classify the work, then review and approve replies before any draft appears in Gmail." cta="Learn the workflow" href="/how-it-works" />
          <div className="workflow-cards reveal-up">
            {["Connect Gmail", "Import conversations", "AI classifies", "Agent approves", "Draft appears"].map((step, index) => (
              <article key={step}>
                <span>{index + 1}</span>
                <h3>{step}</h3>
                <p>A focused handoff that keeps support moving without removing human judgment.</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {featureBlocks.map((block, index) => (
        <section className={`landing-section story-block ${block.tint}`} key={block.title}>
          <div className={`sift-container section-split ${index % 2 ? "reverse" : ""}`}>
            <SectionCopy label={block.label} title={block.title} body={block.body} cta={block.cta} href={block.href} />
            <StoryVisual index={index} />
          </div>
        </section>
      ))}

      <section className="landing-section pricing-section" id="pricing">
        <div className="sift-container">
          <div className="pricing-header reveal-up">
            <SectionCopy centered label="Pricing" title="Simple plans while you shape the support workflow." body="Start free, prove the Gmail workflow, then grow into team controls when your queue needs them." cta="Compare details" href="/pricing" />
            <div className="billing-toggle" aria-label="Billing period">
              <span>Monthly</span>
              <strong>Yearly - save 20%</strong>
            </div>
          </div>
          <div className="pricing-grid reveal-up">
            {plans.map((plan) => (
              <article className={`pricing-card ${plan.featured ? "featured" : ""}`} key={plan.name}>
                {plan.featured ? <span className="recommended-pill">Recommended</span> : null}
                <h3>{plan.name}</h3>
                <p>{plan.audience}</p>
                <strong>{plan.price}<small>/mo</small></strong>
                <ul>{plan.features.map((feature) => <li key={feature}>{feature}</li>)}</ul>
                <Link className={`landing-button ${plan.featured ? "primary" : "secondary"}`} href={`/signup?plan=${plan.id}`}>{plan.cta}</Link>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="final-cta">
        <div className="cta-shape one" />
        <div className="cta-shape two" />
        <div className="sift-container final-cta-inner reveal-up">
          <span className="landing-eyebrow">Ready when your inbox is</span>
          <h2>Make every support decision clearer before the next busy day.</h2>
          <p>Launch a Gmail-first support workflow with priority triage, human-approved AI replies, and calmer operations.</p>
          <Link className="landing-button primary light" href="/signup">Start free</Link>
        </div>
      </section>

      <MarketingFooter />
    </main>
  );
}

function SectionCopy({ label, title, body, cta, href = "/product", centered = false }: { label: string; title: string; body: string; cta: string; href?: string; centered?: boolean }) {
  return (
    <div className={`section-copy reveal-up ${centered ? "centered" : ""}`}>
      <span className="landing-eyebrow">{label}</span>
      <h2>{title}</h2>
      <p>{body}</p>
      <Link href={href}>{cta} <span>-&gt;</span></Link>
    </div>
  );
}

function FloatingShapes() {
  return (
    <div className="floating-layer" aria-hidden="true">
      <span className="float-shape shape-a" />
      <span className="float-shape shape-b" />
      <span className="float-shape shape-c" />
      <span className="float-badge badge-a">94% confidence</span>
      <span className="float-badge badge-b">SLA safe</span>
    </div>
  );
}

function HeroMockup() {
  return (
    <div className="hero-mockup reveal-up" aria-label="Sift product dashboard preview">
      <div className="mockup-glow" />
      <div className="product-frame landing-frame">
        <div className="mock-toolbar"><strong>Priority queue</strong><span>Gmail Connected</span></div>
        <div className="mock-grid">
          <div className="mock-panel">
            <span className="micro">Live queue</span>
            {queueItems.map((ticket) => (
              <div className="queue-row premium-row" key={ticket.subject}>
                <span className="severity-dot neutral" />
                <div><strong>{ticket.subject}</strong><br /><small>{ticket.name} - {ticket.time}</small></div>
              </div>
            ))}
          </div>
          <div className="mock-panel selected-panel">
            <span className="micro">Selected conversation</span>
            <h3>Payment failed before launch</h3>
            <p>The card was charged twice and the workspace is locked before their launch window.</p>
            <div className="reply-card premium-reply"><strong>Suggested reply</strong><p>Apologize, confirm the billing issue, unlock the workspace, and offer a same-day reconciliation after approval.</p><Link className="landing-button primary compact" href="/dashboard/tickets">Approve Gmail draft</Link></div>
          </div>
          <div className="mock-panel analysis-panel">
            <span className="micro">AI analysis</span>
            <p><strong>Intent</strong><br />Recover payment</p>
            <p><strong>Sentiment</strong><br />Negative</p>
            <p><strong>Confidence</strong><br />94%</p>
          </div>
        </div>
      </div>
      <div className="floating-card mini-card one"><strong>12</strong><span>urgent replies</span></div>
      <div className="floating-card mini-card two"><strong>4m</strong><span>avg review</span></div>
    </div>
  );
}

function InteractivePreview() {
  return (
    <div className="interactive-preview reveal-up">
      <aside>
        <b>Sift</b>
        {["Overview", "Triage", "Approvals", "Analytics"].map((item, index) => <span className={index === 1 ? "active" : ""} key={item}>{item}</span>)}
      </aside>
      <div className="preview-main">
        <div className="preview-metrics">
          <article><span>Open</span><strong>128</strong></article>
          <article><span>Needs approval</span><strong>17</strong></article>
          <article><span>AI confidence</span><strong>92%</strong></article>
        </div>
        <div className="preview-chart"><span style={{ height: "36%" }} /><span style={{ height: "68%" }} /><span style={{ height: "52%" }} /><span style={{ height: "82%" }} /><span style={{ height: "64%" }} /></div>
        <div className="preview-table">
          {queueItems.slice(0, 3).map((item) => <p key={item.subject}><strong>{item.subject}</strong><span>{item.time}</span></p>)}
        </div>
      </div>
    </div>
  );
}

function StoryVisual({ index }: { index: number }) {
  return (
    <div className="story-visual reveal-up">
      <div className="visual-window">
        <div className="visual-toolbar"><span /><span /><span /></div>
        <div className="visual-content">
          <h3>{index === 0 ? "Priority queue" : index === 1 ? "Approval draft" : "Operations pulse"}</h3>
          <p>{index === 0 ? "Critical account lockout - 24m left" : index === 1 ? "Reply ready for human review" : "Gmail healthy - AI budget safe"}</p>
          <div className="visual-bars"><span /><span /><span /><span /></div>
        </div>
      </div>
      <span className="support-card top">New customer risk</span>
      <span className="support-card bottom">Draft ready</span>
    </div>
  );
}