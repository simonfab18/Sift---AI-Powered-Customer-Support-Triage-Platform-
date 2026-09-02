import Link from "next/link";

import { MarketingNav } from "@/components/sift/MarketingNav";
import { MarketingFooter } from "@/components/sift/MarketingPage";
import { ScrollReveal } from "@/components/sift/ScrollReveal";

type TrustPageKey = "support" | "status" | "privacy" | "terms" | "dataProcessing" | "cookies";

type TrustSection = {
  title: string;
  body: string;
  items?: string[];
};

const pages: Record<TrustPageKey, { eyebrow: string; title: string; body: string; cta?: string; href?: string; sections: TrustSection[] }> = {
  support: {
    eyebrow: "Support",
    title: "Support for the free Gmail-first pilot.",
    body: "Sift is currently a free pilot, so support is focused on setup, Gmail sync reliability, safe AI triage, and approval-to-draft workflows.",
    cta: "Ask a question",
    href: "/contact",
    sections: [
      {
        title: "What to send",
        body: "Include the workspace name, connected Gmail inbox, what you were trying to do, and the exact message shown in the app.",
        items: ["Gmail connection issues", "Import or sync problems", "AI triage quota or classification issues", "Draft approval and Gmail draft creation issues"],
      },
      {
        title: "What support covers now",
        body: "During pilot, support is practical and setup-focused rather than paid SLA support.",
        items: ["Check Gmail settings health", "Review failed import jobs", "Confirm Cloud Run API health", "Escalate with workspace and ticket IDs"],
      },
      {
        title: "Current pilot expectation",
        body: "There is no paid subscription or guaranteed response time yet. Critical issues are login blocked, Gmail sync down, data access concerns, or failed approval-to-draft flows.",
      },
    ],
  },
  status: {
    eyebrow: "Status",
    title: "Current status for a free pilot system.",
    body: "Sift does not yet have an automated public status provider. This page explains the live dependencies and the current manual incident process.",
    sections: [
      {
        title: "Pilot status posture",
        body: "The system is available as a free Gmail-first pilot. Status is monitored through cloud provider health, application checks, Gmail health panels, and user-reported issues.",
        items: ["No paid SLA yet", "Human-approved replies only", "Gemini free-tier limits can pause AI", "Gmail sync health is visible in settings"],
      },
      {
        title: "Core services",
        body: "The app depends on Vercel for frontend hosting, Google Cloud Run for the API, Google Pub/Sub and Scheduler for Gmail jobs, Supabase for auth/database, Gmail APIs, and Gemini for AI triage.",
        items: ["Frontend: Vercel", "Backend: Cloud Run", "Database and auth: Supabase", "Gmail jobs: Pub/Sub and Scheduler", "AI triage: Gemini capped by quota"],
      },
      {
        title: "Incident handling",
        body: "During pilot, incidents are verified through Cloud Run health checks, Google Cloud Error Reporting, Gmail connection health, import job history, and Supabase availability.",
      },
    ],
  },
  privacy: {
    eyebrow: "Privacy",
    title: "Privacy summary for support teams testing Sift.",
    body: "Sift processes support data only to provide Gmail import, AI triage, human review, draft creation, audit, and workspace operations.",
    sections: [
      {
        title: "Data processed",
        body: "The system may process account identity, workspace membership, Gmail message metadata and body content, attachment metadata, generated triage output, reply suggestions, audit events, and operational logs.",
      },
      {
        title: "Controls",
        body: "Gmail drafts are created only after explicit approval. OAuth tokens are encrypted, workspace access is role-based, and organization boundaries are enforced by the backend.",
        items: ["Human approval before Gmail draft creation", "Role-based workspace access", "Tenant isolation checks", "Encrypted Gmail OAuth token storage", "Audit history for important actions"],
      },
      {
        title: "Pilot note",
        body: "This page is product documentation for the pilot and should be reviewed before any public commercial launch.",
      },
    ],
  },
  terms: {
    eyebrow: "Terms",
    title: "Terms direction for the current free pilot.",
    body: "Sift is currently offered as a free pilot tool. Paid billing, formal subscription terms, and service-level commitments are intentionally deferred.",
    sections: [
      {
        title: "Use of the service",
        body: "Users are responsible for connecting only Gmail inboxes they are authorized to access and for reviewing AI-generated replies before acting on them.",
        items: ["No autonomous sending", "No paid subscription in the current pilot", "Human review required for draft creation", "Users control Gmail connection and disconnection"],
      },
      {
        title: "AI output",
        body: "AI triage and reply suggestions can be incomplete or wrong. Agents should review urgency, category, reasoning, and draft text before approval.",
      },
      {
        title: "Pilot note",
        body: "This terms page is a product-readiness placeholder and should be replaced by reviewed legal terms before a public launch.",
      },
    ],
  },
  dataProcessing: {
    eyebrow: "Data processing",
    title: "How support data moves through Sift.",
    body: "This page explains the current data-processing direction for Gmail support triage in staging and pilot environments.",
    sections: [
      {
        title: "Processing flow",
        body: "Gmail OAuth connects an inbox, Gmail push notifications trigger sync, messages become tickets, Gemini can classify and draft suggestions, agents review replies, and approved replies can create Gmail drafts.",
        items: ["Gmail OAuth connection", "Gmail import and history sync", "Ticket creation", "AI triage and suggested replies", "Human approval", "Gmail draft creation"],
      },
      {
        title: "Storage and retention direction",
        body: "Supabase stores workspace, ticket, audit, and job records. Attachment files can be stored in a private Google Cloud Storage bucket when explicitly saved. Owners/admins can download a workspace export from Settings -> Readiness. Owners can request deletion there, which records an audit event and pauses automation; hard deletion remains an operator-reviewed follow-up.",
      },
      {
        title: "Security controls",
        body: "The backend validates Supabase JWTs, organization membership, roles, and Google OIDC tokens for internal task routes.",
      },
    ],
  },
  cookies: {
    eyebrow: "Cookies",
    title: "Cookie use for the Sift website and app.",
    body: "Sift uses only the cookies and browser storage needed for authentication, session continuity, security, and basic product operation during the free pilot.",
    sections: [
      {
        title: "Essential cookies",
        body: "Authentication and session cookies help keep users signed in and protect account access. These are required for the dashboard and cannot be turned off inside the app.",
        items: ["Supabase auth session", "Security/session continuity", "Workspace access state"],
      },
      {
        title: "Product preferences",
        body: "The app may store small local preferences such as selected workspace, saved UI state, and dashboard navigation choices to make the product easier to use.",
      },
      {
        title: "Pilot note",
        body: "Sift does not currently describe paid advertising or cross-site marketing cookies as part of the pilot posture. This should be reviewed before public launch.",
      },
    ],
  },
};

export function TrustPage({ page }: { page: TrustPageKey }) {
  const data = pages[page];

  return (
    <main className="landing-page trust-detail-page">
      <ScrollReveal />
      <MarketingNav />
      <section className="detail-hero trust-hero">
        <div className="sift-container detail-hero-grid">
          <div className="section-copy reveal-up">
            <span className="landing-eyebrow">{data.eyebrow}</span>
            <h1>{data.title}</h1>
            <p>{data.body}</p>
            <div className="landing-actions">
              <Link className="landing-button primary" href={data.href ?? "/signup"}>{data.cta ?? "Start free"}</Link>
              <Link className="landing-button secondary" href="/contact">Ask a question</Link>
            </div>
          </div>
          <div className="trust-summary-card reveal-up">
            <span>Free pilot</span>
            <strong>Human approval, Gmail-first scope, and transparent operating limits.</strong>
            <p>These pages explain the current product posture while Sift is still being improved before a broader launch.</p>
          </div>
        </div>
      </section>
      <section className="landing-section compact-top">
        <div className="sift-container trust-card-grid">
          {data.sections.map((section) => (
            <article key={section.title} className="detail-panel trust-panel reveal-up">
              <h2>{section.title}</h2>
              <p>{section.body}</p>
              {section.items ? <ul>{section.items.map((item) => <li key={item}>{item}</li>)}</ul> : null}
            </article>
          ))}
        </div>
      </section>
      <MarketingFooter />
    </main>
  );
}