import Link from "next/link";

import { MarketingNav } from "@/components/sift/MarketingNav";
import { ScrollReveal } from "@/components/sift/ScrollReveal";
import { SiftLogo } from "@/components/sift/SiftLogo";

const featureCards = [
  ["Gmail intake", "Connect one or many Gmail inboxes, import unread conversations, and keep every ticket tied to its source inbox.", "Connect OAuth, labels, import rules, and health checks without changing how Gmail is used."],
  ["AI triage", "Classify urgency, category, sentiment, summary, confidence, and reasoning in one structured support review.", "Designed to reduce repeat model calls by keeping classification, summary, and suggested action together."],
  ["Human approval", "Agents review the suggested reply, edit it when needed, then create a Gmail draft only after approval.", "Live sending stays off by default so teams keep control of customer-facing replies."],
  ["Saved queue views", "Save filters by inbox, status, urgency, SLA state, source type, and sorting so teams can reopen their exact operating view.", "Owners, admins, and agents can keep different views for daily review, escalations, and cleanup."],
  ["Workflow health", "Monitor Gmail watch status, sync status, failed jobs, import runs, and retry paths before support work stalls.", "Make degraded sync, paused AI, and failed imports understandable without reading logs."],
  ["Audit trail", "Track approvals, draft creation, setting changes, imports, retries, and administrative actions for review.", "Every important workflow action is visible later for support quality and operational review."],
  ["Attachments", "Show attachment metadata, scan status, and safe download links without sending file contents to AI unless the workspace opts in.", "Attachment AI processing stays off by default for a safer pilot posture."],
  ["Usage controls", "Show workspace AI usage, daily caps, and paused states so a free pilot does not accidentally burn through quota.", "Admins can see when AI is available, paused, or waiting for the next retry window."],
  ["Routing rules", "Prepare assignment and escalation rules around inbox, category, priority, and support ownership.", "Keep Gmail-first workflows organized before expanding to other channels."],
];

const workflowSteps = [
  ["Prepare workspace", "Create the organization, invite the team, confirm roles, and choose the approval-first operating mode."],
  ["Connect Gmail", "A workspace owner connects Gmail through OAuth. Sift stores the connection securely and creates inbox health status."],
  ["Import conversations", "The team imports recent unread mail or queues a background sync. Each message becomes a workspace-scoped ticket."],
  ["Classify with AI", "Sift analyzes the customer message and returns structured urgency, category, sentiment, confidence, and suggested next action."],
  ["Review safely", "Agents see the email context, AI reasoning, SLA state, attachments, and reply suggestion before anything reaches Gmail."],
  ["Approve a draft", "After approval, Sift creates a Gmail draft and records the action in the ticket timeline and audit trail."],
  ["Resolve or route", "Agents resolve, assign, mark spam, or save the view that matches the work they are doing."],
  ["Measure operations", "Owners monitor active tickets, approvals, queue pressure, usage caps, failed jobs, and inbox reliability."],
];

const resourceCards = [
  ["Gmail setup checklist", "Prepare OAuth, Pub/Sub push, inbox labels, and import rules for a cleaner pilot.", "Setup"],
  ["AI quality review", "Use sample refund, billing, access, and product-question emails to test classifications.", "Quality"],
  ["Approval policy guide", "Decide who can approve replies, create drafts, resolve tickets, and change routing settings.", "Policy"],
  ["Pilot readiness checklist", "Confirm usage caps, error reporting, Gmail health, backup posture, and staging verification.", "Readiness"],
  ["SLA review worksheet", "Define what first review and resolution targets mean for your team before a queue gets busy.", "Operations"],
  ["Shared inbox planning", "Map individual Gmail inboxes, Google Groups, and shared support addresses into a clear source model.", "Gmail"],
];

const productScreens = [
  ["Queue control", "Filter tickets, save views, bulk resolve, assign, and retry triage from one focused surface."],
  ["Ticket review", "Read the customer thread, AI classification, SLA state, reply versions, and Gmail draft status."],
  ["Readiness", "Track Gmail health, usage caps, attachment AI opt-in, pilot controls, and known issues."],
];

const pricingPlans = [
  { id: "free", name: "Free", audience: "Testing Gmail triage", price: "$0", note: "Best for validating the workflow", featured: false, features: ["1 workspace", "1 Gmail inbox", "20 AI triage calls/day", "Human approval", "Basic queue views"] },
  { id: "starter", name: "Starter", audience: "Solo operators", price: "$19", note: "For one person managing more support", featured: false, features: ["3 inboxes", "Saved views", "Draft workflow", "Basic analytics", "Attachment metadata"] },
  { id: "team", name: "Team", audience: "Small support teams", price: "$49", note: "Recommended once agents share work", featured: true, features: ["10 inboxes", "Team roles", "Routing rules", "Audit exports", "Workflow health panel"] },
  { id: "business", name: "Business", audience: "Controlled operations", price: "$129", note: "For stricter controls and review", featured: false, features: ["Advanced controls", "Security review", "Custom limits", "Priority setup", "Admin reporting"] },
];

const comparisonRows = [
  ["Gmail inboxes", "1", "3", "10", "Custom"],
  ["Human approval", "Included", "Included", "Included", "Included"],
  ["Saved views", "Basic", "Included", "Included", "Included"],
  ["Routing rules", "-", "Basic", "Included", "Advanced"],
  ["Audit exports", "-", "-", "Included", "Included"],
  ["Setup support", "Self serve", "Guide", "Priority", "Priority"],
];

const aboutPrinciples = [
  ["Humans stay accountable", "AI helps sort, summarize, and draft, but teams keep approval and customer judgment."],
  ["Gmail-first until it is strong", "The product focuses on making one workflow reliable before expanding to more channels."],
  ["Operations should feel calm", "Owners and admins should know what is healthy, what needs attention, and what changed."],
  ["Security is part of the workflow", "OAuth, roles, audit, tenant isolation, and opt-in processing are treated as product behavior, not hidden plumbing."],
];

const footerColumns = {
  Product: [
    ["Features", "/features"],
    ["How it works", "/how-it-works"],
    ["Pricing", "/pricing"],
    ["Security", "/security"],
  ],
  Company: [
    ["About", "/about"],
    ["Contact", "/contact"],
    ["Status", "/status"],
    ["Careers", "/about"],
  ],
  Resources: [
    ["Guides", "/resources"],
    ["Gmail setup", "/resources"],
    ["Pilot checklist", "/resources"],
    ["Support", "/support"],
  ],
  Legal: [
    ["Privacy", "/privacy"],
    ["Terms", "/terms"],
    ["Data processing", "/data-processing"],
    ["Cookies", "/cookies"],
  ],
};

const pageData = {
  product: {
    eyebrow: "Product",
    title: "A Gmail-first operating system for support triage.",
    body: "See how Sift gives owners, admins, and agents one calm workspace for prioritizing tickets, reviewing AI, approving replies, and monitoring Gmail health.",
    cta: "See all features",
    href: "/features",
    visual: "product",
  },
  features: {
    eyebrow: "Feature library",
    title: "Every control has a job in the support workflow.",
    body: "Explore the Gmail intake, AI review, approval, reliability, audit, and admin controls that make Sift useful before a support queue gets busy.",
    cta: "Learn the workflow",
    href: "/how-it-works",
    visual: "features",
  },
  howItWorks: {
    eyebrow: "Workflow",
    title: "A safe path from customer email to approved Gmail draft.",
    body: "Sift is organized around the real order of work: prepare the workspace, connect Gmail, import, classify, review, approve, resolve, and measure.",
    cta: "Start free",
    href: "/signup",
    visual: "workflow",
  },
  pricing: {
    eyebrow: "Pricing",
    title: "Start free, then upgrade only when the workflow earns it.",
    body: "Sift is still Gmail-first and pilot-friendly. The free plan is for testing, while paid plans show the direction for larger team workflows.",
    cta: "Start free",
    href: "/signup",
    visual: "pricing",
  },
  resources: {
    eyebrow: "Resources",
    title: "Practical guides for setting up a calmer Gmail pilot.",
    body: "Use checklists, review guides, and operating worksheets to prepare Gmail, test AI quality, define roles, and verify reliability.",
    cta: "View product",
    href: "/product",
    visual: "resources",
  },
  about: {
    eyebrow: "About Sift",
    title: "Built for teams that want AI help without losing control.",
    body: "Sift is intentionally focused: make Gmail support clearer, keep humans in charge of replies, and give owners a reliable view of operations.",
    cta: "Contact us",
    href: "/contact",
    visual: "about",
  },
  solutions: {
    eyebrow: "Solutions",
    title: "Gmail support workflows for small, focused teams.",
    body: "Use Sift for SaaS support, e-commerce queues, customer success teams, and internal operations that need human-approved AI replies.",
    cta: "See features",
    href: "/features",
    visual: "features",
  },
  security: {
    eyebrow: "Security",
    title: "Control, audit, and human approval stay at the center.",
    body: "Sift is designed around workspace isolation, encrypted OAuth, role-based access, audit logs, approval gates, and clear data controls.",
    cta: "Review workflow",
    href: "/how-it-works",
    visual: "security",
  },
  contact: {
    eyebrow: "Contact",
    title: "Ask about setup, Gmail, pricing, or pilot readiness.",
    body: "Send a question, request help planning your support workflow, or ask what Sift should support before you connect a real inbox.",
    cta: "Email us",
    href: "mailto:hello@usesift.app?subject=Sift%20question",
    visual: "contact",
  },
};

type MarketingPageKey = keyof typeof pageData;

export function MarketingPage({ page }: { page: MarketingPageKey }) {
  const data = pageData[page];
  return (
    <main className="landing-page marketing-detail-page">
      <ScrollReveal />
      <MarketingNav />
      <DetailHero data={data} page={page} />

      {page === "features" ? <FeatureLibrary /> : null}
      {page === "howItWorks" ? <WorkflowSection /> : null}
      {page === "pricing" ? <PricingPageContent /> : null}
      {page === "resources" ? <ResourcesContent /> : null}
      {page === "about" ? <AboutContent /> : null}
      {page === "product" ? <ProductContent /> : null}
      {page === "contact" ? <ContactContent /> : null}
      {page === "solutions" ? <FeatureLibrary compact /> : null}
      {page === "security" ? <SecurityContent /> : null}

      <section className="final-cta detail-cta">
        <div className="sift-container final-cta-inner reveal-up">
          <span className="landing-eyebrow">Sift</span>
          <h2>Ready to make Gmail support easier to operate?</h2>
          <p>Start with a free Gmail-first pilot and keep every AI reply human-approved.</p>
          <Link className="landing-button primary light" href="/signup">Start free</Link>
        </div>
      </section>
      <MarketingFooter />
    </main>
  );
}

function DetailHero({ data, page }: { data: (typeof pageData)[MarketingPageKey]; page: MarketingPageKey }) {
  return (
    <section className={`detail-hero detail-hero-${page}`}>
      <div className="sift-container detail-hero-grid">
        <div className="section-copy reveal-up">
          <span className="landing-eyebrow">{data.eyebrow}</span>
          <h1>{data.title}</h1>
          <p>{data.body}</p>
          <div className="landing-actions">
            <Link className="landing-button primary" href={data.href}>{data.cta}</Link>
            <Link className="landing-button secondary" href={page === "contact" ? "/resources" : "/signup"}>{page === "contact" ? "Browse resources" : "Start free"}</Link>
          </div>
        </div>
        <PageVisual page={page} />
      </div>
    </section>
  );
}

function PageVisual({ page }: { page: MarketingPageKey }) {
  const labels: Record<string, string[]> = {
    features: ["Inbox health", "AI triage", "Approval gate"],
    howItWorks: ["Connect", "Classify", "Approve"],
    pricing: ["Free pilot", "Team controls", "Usage caps"],
    resources: ["Checklist", "Review guide", "SLA worksheet"],
    about: ["Human first", "Gmail first", "Calm operations"],
    contact: ["Question", "Setup help", "Pilot review"],
    product: ["Queue", "Ticket", "Readiness"],
    solutions: ["SaaS", "E-commerce", "Operations"],
    security: ["OAuth", "Roles", "Audit"],
  };
  const items = labels[page] ?? labels.product;
  return (
    <div className="detail-mockup reveal-up">
      <div className="landing-frame detail-frame page-visual-frame">
        <div className="mock-toolbar"><strong>{page === "contact" ? "Contact desk" : "Sift workspace"}</strong><span>{page === "pricing" ? "Plan view" : "Live preview"}</span></div>
        <div className="page-visual-body">
          {items.map((item, index) => (
            <article key={item}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <strong>{item}</strong>
              <p>{page === "contact" ? "Send a question and get routed to the right setup path." : "A focused part of the Gmail-first support workflow."}</p>
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}

function FeatureLibrary({ compact = false }: { compact?: boolean }) {
  const cards = compact ? featureCards.slice(0, 6) : featureCards;
  return (
    <>
      <section className="landing-section detail-intro-band">
        <div className="sift-container detail-section-heading reveal-up">
          <span className="landing-eyebrow">Feature map</span>
          <h2>Built around the moments where support work usually gets unclear.</h2>
          <p>Each feature is meant to answer one operational question: what arrived, how urgent it is, who owns it, what AI suggested, whether it is safe to draft, and what changed.</p>
        </div>
      </section>
      <section className="landing-section compact-top">
        <div className="sift-container feature-library expanded">
          {cards.map(([title, body, detail]) => <FeatureCard key={title} title={title} body={body} detail={detail} />)}
        </div>
      </section>
      <section className="landing-section soft-block">
        <div className="sift-container detail-two-column">
          <DetailPanel title="For owners" body="See whether the queue is healthy, how much AI is being used, which tickets need approval, and where Gmail sync needs attention." />
          <DetailPanel title="For agents" body="Open a saved view, review the conversation and AI reasoning, edit the suggested reply, approve a Gmail draft, then resolve or route the ticket." />
        </div>
      </section>
    </>
  );
}

function WorkflowSection() {
  return (
    <>
      <section className="landing-section soft-block">
        <div className="sift-container workflow-detail">
          {workflowSteps.map(([title, body], index) => (
            <article className="workflow-detail-step reveal-up" key={title}>
              <span>{index + 1}</span>
              <div>
                <h2>{title}</h2>
                <p>{body}</p>
              </div>
              <MiniScreenshot label={title} />
            </article>
          ))}
        </div>
      </section>
      <section className="landing-section">
        <div className="sift-container detail-two-column three">
          <DetailPanel title="Owner flow" body="Set the workspace, confirm Gmail health, monitor quota, and review queue pressure before the day gets busy." />
          <DetailPanel title="Admin flow" body="Tune routing, saved views, readiness settings, team roles, and operational guardrails." />
          <DetailPanel title="Agent flow" body="Work the queue, review AI, approve drafts, update ticket status, and keep customer replies moving." />
        </div>
      </section>
    </>
  );
}

function ProductContent() {
  return (
    <section className="landing-section">
      <div className="sift-container product-content-grid">
        {productScreens.map(([title, body], index) => (
          <article className="product-content-card reveal-up" key={title}>
            <MiniScreenshot label={title} wide />
            <span className="landing-eyebrow">Screen {index + 1}</span>
            <h2>{title}</h2>
            <p>{body}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function PricingPageContent() {
  return (
    <>
      <section className="landing-section pricing-section">
        <div className="sift-container">
          <div className="pricing-header reveal-up">
            <span className="landing-eyebrow">Plans</span>
            <h2>Choose the smallest plan that fits the current workflow.</h2>
            <p>For now, Sift is free-pilot friendly. Paid plan cards explain the intended upgrade path when more inboxes, roles, and reporting are needed.</p>
            <div className="billing-toggle" aria-label="Billing period"><span>Monthly</span><strong>Yearly - save 20%</strong></div>
          </div>
          <PricingSelector />
        </div>
      </section>
      <section className="landing-section soft-block">
        <div className="sift-container comparison-wrap reveal-up">
          <h2>Compare plan controls</h2>
          <div className="comparison-table" role="table" aria-label="Pricing comparison">
            <div className="comparison-row heading"><span>Feature</span><span>Free</span><span>Starter</span><span>Team</span><span>Business</span></div>
            {comparisonRows.map((row) => <div className="comparison-row" key={row[0]}>{row.map((cell) => <span key={cell}>{cell}</span>)}</div>)}
          </div>
        </div>
      </section>
      <section className="landing-section">
        <div className="sift-container faq-grid">
          <DetailPanel title="Can I use Sift for free?" body="Yes. The current system is designed for a Gmail-first free pilot while core workflows are still being hardened." />
          <DetailPanel title="Does Sift send emails automatically?" body="No. Gmail drafts are created only after human approval, and live direct sending remains off unless explicitly changed later." />
          <DetailPanel title="What uses AI quota?" body="Triage and reply generation use AI. The product shows usage and pause states so teams understand when quota is available." />
        </div>
      </section>
    </>
  );
}

function ResourcesContent() {
  return (
    <>
      <section className="landing-section soft-block">
        <div className="sift-container detail-section-heading reveal-up">
          <span className="landing-eyebrow">Resource library</span>
          <h2>Use these before connecting a busy inbox.</h2>
          <p>The goal is to help a small team prepare the operating rules first, then test Sift with real Gmail messages in a safer order.</p>
        </div>
      </section>
      <section className="landing-section compact-top">
        <div className="sift-container resource-library">
          {resourceCards.map(([title, body, type]) => <ResourceCard key={title} title={title} body={body} type={type} />)}
        </div>
      </section>
      <section className="landing-section soft-block resource-playbooks">
        <div className="sift-container detail-two-column">
          <DetailPanel title="Guides" body="Step-by-step notes for setting up Sift, preparing a workspace, testing AI triage, reviewing drafts, and deciding what belongs in the first pilot." />
          <DetailPanel title="Gmail setup" body="Use this checklist to confirm OAuth, redirect URLs, connected inboxes, Gmail labels, Pub/Sub push, import rules, and watch health before importing real customer mail." />
          <DetailPanel title="Pilot checklist" body="Before a real queue gets busy, confirm usage caps, Gmail health, workspace roles, approval behavior, draft creation, backup posture, and known issues." />
          <DetailPanel title="Support" body="If something fails, gather workspace name, Gmail inbox, ticket ID, action attempted, visible error message, and whether the problem is login, import, triage, approval, or draft creation." />
        </div>
      </section>
    </>
  );
}

function AboutContent() {
  return (
    <>
      <section className="landing-section">
        <div className="sift-container about-story reveal-up">
          <span className="landing-eyebrow">Why Sift exists</span>
          <h2>Support teams do not need more noise. They need a clearer next action.</h2>
          <p>Sift is being built around the messy middle of customer support: a shared inbox, unclear urgency, repeated questions, approval risk, quota limits, and the need to keep a real human accountable for every customer-facing answer.</p>
        </div>
      </section>
      <section className="landing-section soft-block">
        <div className="sift-container about-grid expanded">
          {aboutPrinciples.map(([title, body]) => <DetailPanel key={title} title={title} body={body} />)}
        </div>
      </section>
    </>
  );
}

function ContactContent() {
  return (
    <section className="landing-section">
      <div className="sift-container contact-grid">
        <div className="contact-copy reveal-up">
          <span className="landing-eyebrow">Contact</span>
          <h2>Send a question or describe the support workflow you want to test.</h2>
          <p>Ask about Gmail setup, OAuth redirect URLs, AI quota, pricing, pilot readiness, workflow design, or whether Sift fits your inbox.</p>
          <div className="contact-methods">
            <a href="mailto:hello@usesift.app?subject=Sift%20question">hello@usesift.app</a>
            <a href="mailto:support@usesift.app?subject=Sift%20support%20request">support@usesift.app</a>
          </div>
        </div>
        <form className="contact-form reveal-up" action="mailto:hello@usesift.app" method="post" encType="text/plain">
          <label>
            Name
            <input name="name" placeholder="Your name" />
          </label>
          <label>
            Email
            <input name="email" type="email" placeholder="you@example.com" required />
          </label>
          <label>
            Topic
            <select name="topic" defaultValue="">
              <option value="" disabled>Choose a topic</option>
              <option>Gmail setup</option>
              <option>Pricing</option>
              <option>AI triage</option>
              <option>Pilot readiness</option>
              <option>General question</option>
            </select>
          </label>
          <label>
            Question
            <textarea name="message" placeholder="Tell us what you want to ask or test." rows={6} required />
          </label>
          <button className="landing-button primary" type="submit">Send question</button>
        </form>
      </div>
    </section>
  );
}

function SecurityContent() {
  return (
    <section className="landing-section soft-block">
      <div className="sift-container detail-two-column three">
        <DetailPanel title="Access control" body="Supabase authentication, workspace roles, and organization authorization protect normal application routes." />
        <DetailPanel title="Gmail safety" body="OAuth credentials, Pub/Sub webhooks, and draft creation are treated as controlled integration workflows." />
        <DetailPanel title="Audit visibility" body="Approvals, draft creation, settings changes, retries, and imports are recorded for operational review." />
      </div>
    </section>
  );
}

function PricingSelector() {
  return (
    <div className="selectable-pricing-grid">
      {pricingPlans.map((plan) => (
        <label className="selectable-plan" key={plan.id}>
          <input type="radio" name="selected-plan" defaultChecked={plan.featured} />
          <article className={`pricing-card ${plan.featured ? "featured" : ""}`}>
            {plan.featured ? <span className="recommended-pill">Recommended</span> : null}
            <h3>{plan.name}</h3>
            <p>{plan.audience}</p>
            <strong>{plan.price}<small>/mo</small></strong>
            <p className="plan-note">{plan.note}</p>
            <ul>{plan.features.map((feature) => <li key={feature}>{feature}</li>)}</ul>
            <Link className={`landing-button ${plan.featured ? "primary" : "secondary"}`} href={`/signup?plan=${plan.id}`}>Select {plan.name}</Link>
          </article>
        </label>
      ))}
    </div>
  );
}

function FeatureCard({ title, body, detail }: { title: string; body: string; detail?: string }) {
  return (
    <article className="feature-card reveal-up">
      <MiniScreenshot label={title} />
      <h2>{title}</h2>
      <p>{body}</p>
      {detail ? <small>{detail}</small> : null}
      <Link href="/signup">Try it <span>-&gt;</span></Link>
    </article>
  );
}

function ResourceCard({ title, body, type }: { title: string; body: string; type: string }) {
  return (
    <article className="resource-card reveal-up">
      <span>{type}</span>
      <h2>{title}</h2>
      <p>{body}</p>
      <Link href="/contact">Ask about this <span>-&gt;</span></Link>
    </article>
  );
}

function DetailPanel({ title, body }: { title: string; body: string }) {
  return <article className="detail-panel reveal-up"><h2>{title}</h2><p>{body}</p></article>;
}

function MiniScreenshot({ label, wide = false }: { label: string; wide?: boolean }) {
  return (
    <div className={`mini-screenshot ${wide ? "wide" : ""}`}>
      <div className="visual-toolbar"><span /><span /><span /></div>
      <div className="mini-shot-body">
        <strong>{label}</strong>
        <p>Realistic workspace preview</p>
        <div className="mini-bars"><span /><span /><span /><span /></div>
      </div>
    </div>
  );
}

export function MarketingFooter() {
  return (
    <footer className="landing-footer">
      <div className="sift-container footer-top">
        <div className="footer-brand">
          <SiftLogo />
          <p>AI-assisted Gmail triage, human-approved replies, and calm support operations.</p>
          <form className="newsletter">
            <input aria-label="Email address" placeholder="Email for product updates" />
            <button type="button">Join</button>
          </form>
        </div>
        {Object.entries(footerColumns).map(([column, links]) => (
          <div className="footer-column" key={column}>
            <strong>{column}</strong>
            {links.map(([label, href]) => <Link href={href} key={label}>{label}</Link>)}
          </div>
        ))}
      </div>
      <div className="sift-container footer-bottom">
        <span>(c) 2026 Sift. All rights reserved.</span>
        <span>LinkedIn - X - YouTube</span>
      </div>
    </footer>
  );
}