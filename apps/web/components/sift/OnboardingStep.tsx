import Link from "next/link";

import { SiftLogo } from "@/components/sift/SiftLogo";

const steps = ["welcome", "company", "support", "preferences", "integrations", "team", "complete"];

const content: Record<string, { title: string; body: string; options: string[]; next: string; cta: string }> = {
  welcome: { title: "Let's set up Sift for your support team", body: "Create the workspace where conversations, team roles, rules, and integrations will live.", options: ["Workspace name", "URL preview", "Company logo", "Team size"], next: "/onboarding/company", cta: "Continue" },
  company: { title: "Tell Sift about your company", body: "This helps tune triage language, customer context, and suggested response style.", options: ["SaaS", "E-commerce", "Marketplace", "Agency", "Financial services", "Education"], next: "/onboarding/support", cta: "Save company profile" },
  support: { title: "What does your team handle most often?", body: "Choose the conversations Sift should understand first.", options: ["Billing and payments", "Refunds", "Technical issues", "Account access", "Product questions", "Sales inquiries"], next: "/onboarding/preferences", cta: "Set support profile" },
  preferences: { title: "What should Sift prioritize?", body: "Human approval is required by default. You can tune policy later in settings.", options: ["Payment failures", "Account lockouts", "VIP customers", "Cancellation risk", "Negative sentiment", "SLA breaches"], next: "/onboarding/integrations", cta: "Save preferences" },
  integrations: { title: "Connect your support tools", body: "Gmail is the recommended first step. Other integrations can be connected later.", options: ["Gmail · recommended", "Slack · coming soon", "Webhook · coming soon"], next: "/onboarding/team", cta: "Continue" },
  team: { title: "Invite your team", body: "Add owners, admins, agents, and viewers. You can skip this for now.", options: ["Owner", "Admin", "Agent", "Viewer"], next: "/onboarding/complete", cta: "Send invitations" },
  complete: { title: "Your workspace is ready", body: "Workspace created, preferences saved, and sample support operations are ready to review.", options: ["Workspace created", "Preferences saved", "Gmail can be connected", "Sample conversations available"], next: "/dashboard", cta: "Go to dashboard" },
};

export function OnboardingStep({ step }: { step: keyof typeof content }) {
  const data = content[step];
  const index = steps.indexOf(step);
  const progress = ((index + 1) / steps.length) * 100;
  return (
    <main className="onboarding-shell">
      <section className="wizard">
        <div className="wizard-head">
          <SiftLogo />
          <span className="micro">Step {index + 1} of {steps.length}</span>
        </div>
        <div className="progress"><i style={{ width: `${progress}%` }} /></div>
        <div className="wizard-body">
          <span className="eyebrow">Onboarding</span>
          <h1 style={{ fontSize: 40, lineHeight: 1.12, margin: "10px 0" }}>{data.title}</h1>
          <p style={{ color: "var(--muted)", maxWidth: 620, lineHeight: 1.7 }}>{data.body}</p>
          <div className="option-grid">
            {data.options.map((option) => <label className="option" key={option}><input type="checkbox" /> {option}</label>)}
          </div>
          {step !== "complete" ? <div className="form-grid" style={{ maxWidth: 520 }}><label className="field">Primary detail<input className="input" placeholder="Add details" /></label></div> : null}
          <div className="hero-actions">
            <Link className="button primary" href={data.next}>{data.cta}</Link>
            {step !== "complete" ? <Link className="button ghost" href={data.next}>Skip for now</Link> : <Link className="button secondary" href="/dashboard/tickets">Import sample conversations</Link>}
          </div>
        </div>
      </section>
    </main>
  );
}
