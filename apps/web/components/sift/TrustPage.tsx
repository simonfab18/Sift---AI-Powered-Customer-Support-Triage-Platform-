import Link from "next/link";

import { MarketingNav } from "@/components/sift/MarketingNav";
import { SiftLogo } from "@/components/sift/SiftLogo";

type TrustPageKey = "support" | "status" | "privacy" | "terms" | "dataProcessing";

type TrustSection = {
  title: string;
  body: string;
  items?: string[];
};

const pages: Record<TrustPageKey, { eyebrow: string; title: string; body: string; sections: TrustSection[] }> = {
  support: {
    eyebrow: "Support",
    title: "How Sift support is handled during the free pilot.",
    body: "This product is currently a free pilot. Support is focused on setup, Gmail sync reliability, safe triage, and deployment health.",
    sections: [
      {
        title: "What to send",
        body: "Include the workspace name, the connected Gmail inbox, what you were trying to do, and the error message shown in the app.",
        items: ["Gmail connection issues", "Import or sync problems", "AI triage quota or classification issues", "Draft approval and Gmail draft creation issues"],
      },
      {
        title: "Expected response path",
        body: "Pilot support is handled manually. Critical issues are Gmail sync down, login blocked, data access concerns, or failed approval-to-draft flows.",
        items: ["Check the Gmail settings health cards", "Confirm Cloud Run API health", "Review recent import job errors", "Escalate with workspace and ticket IDs"],
      },
    ],
  },
  status: {
    eyebrow: "Status",
    title: "Current service status and operating dependencies.",
    body: "Sift does not yet have an automated public status provider. This page documents the current manual status process for the free pilot.",
    sections: [
      {
        title: "Core services",
        body: "The app depends on Vercel for frontend hosting, Google Cloud Run for the API, Google Pub/Sub and Scheduler for Gmail jobs, Supabase for auth/database, Gmail APIs, and Gemini for AI triage.",
        items: ["Frontend: Vercel", "Backend: Cloud Run", "Database and auth: Supabase", "Gmail jobs: Pub/Sub and Scheduler", "AI triage: Gemini free-tier capped"],
      },
      {
        title: "Incident handling",
        body: "During pilot, incidents are verified through Cloud Run health checks, Google Cloud Error Reporting, Gmail connection health, import job history, and Supabase availability.",
      },
    ],
  },
  privacy: {
    eyebrow: "Privacy",
    title: "Privacy summary for the free pilot.",
    body: "Sift processes support data only to provide Gmail import, AI triage, human review, draft creation, audit, and workspace operations.",
    sections: [
      {
        title: "Data processed",
        body: "The system may process account identity, workspace membership, Gmail message metadata and body content, attachments metadata, generated triage output, reply suggestions, audit events, and operational logs.",
      },
      {
        title: "Controls",
        body: "Gmail drafts are created only after explicit approval. OAuth tokens are encrypted, workspace access is role-based, and organization boundaries are enforced by the backend.",
        items: ["Human approval before Gmail draft creation", "Role-based workspace access", "Tenant isolation checks", "Encrypted Gmail OAuth token storage", "Audit history for important actions"],
      },
      {
        title: "Current pilot note",
        body: "This page is product documentation for the pilot and should be reviewed before any public commercial launch.",
      },
    ],
  },
  terms: {
    eyebrow: "Terms",
    title: "Free pilot terms direction.",
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
        title: "Current pilot note",
        body: "This terms page is a product-readiness placeholder and should be replaced by reviewed legal terms before a public launch.",
      },
    ],
  },
  dataProcessing: {
    eyebrow: "Data processing",
    title: "How support data moves through Sift.",
    body: "This page explains the current data-processing direction for Gmail support triage in staging/pilot environments.",
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
};

const footerLinks = [
  ["Support", "/support"],
  ["Status", "/status"],
  ["Privacy", "/privacy"],
  ["Terms", "/terms"],
  ["Data processing", "/data-processing"],
  ["Security", "/security"],
];

export function TrustPage({ page }: { page: TrustPageKey }) {
  const data = pages[page];

  return (
    <main className="sift-page">
      <MarketingNav />
      <section className="section">
        <div className="sift-container page-title">
          <span className="eyebrow">{data.eyebrow}</span>
          <h1>{data.title}</h1>
          <p>{data.body}</p>
          <div className="hero-actions">
            <Link className="button primary" href="/signup">Start free</Link>
            <Link className="button secondary" href="/dashboard">Open dashboard</Link>
          </div>
        </div>
      </section>
      <section className="section" style={{ background: "white", borderBlock: "1px solid var(--border)" }}>
        <div className="sift-container dashboard-grid">
          {data.sections.map((section) => (
            <article key={section.title} className="panel">
              <h2>{section.title}</h2>
              <p>{section.body}</p>
              {section.items ? (
                <ul style={{ margin: "18px 0 0", paddingLeft: 18, color: "var(--muted)", lineHeight: 1.8 }}>
                  {section.items.map((item) => <li key={item}>{item}</li>)}
                </ul>
              ) : null}
            </article>
          ))}
        </div>
      </section>
      <footer className="footer">
        <div className="sift-container footer-grid">
          <div>
            <SiftLogo />
            <p style={{ marginTop: 12 }}>Free pilot documentation for safe Gmail support triage.</p>
          </div>
          <div>
            <strong>Trust</strong>
            {footerLinks.slice(0, 3).map(([label, href]) => <Link key={href} href={href}>{label}</Link>)}
          </div>
          <div>
            <strong>Legal</strong>
            {footerLinks.slice(3, 5).map(([label, href]) => <Link key={href} href={href}>{label}</Link>)}
          </div>
          <div>
            <strong>Product</strong>
            <Link href="/product">Product</Link>
            <Link href="/resources">Resources</Link>
            <Link href="/contact">Contact</Link>
          </div>
          <div>
            <strong>Access</strong>
            <Link href="/login">Sign in</Link>
            <Link href="/signup">Start free</Link>
          </div>
        </div>
      </footer>
    </main>
  );
}