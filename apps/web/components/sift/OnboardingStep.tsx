"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { SiftLogo } from "@/components/sift/SiftLogo";
import { setStoredOrganizationId } from "@/features/organizations/components/OrganizationManager";
import { createOrganization, getMe } from "@/lib/api-client";
import { createClient } from "@/lib/supabase/client";

type OnboardingAnswers = {
  purpose: string;
  companyName: string;
  teamSize: string;
  industry: string;
  supportVolume: string;
  mainWork: string[];
};

const questions = [
  {
    key: "purpose" as const,
    eyebrow: "Purpose",
    title: "What do you want Sift to help with first?",
    body: "This helps shape the first workspace, dashboard language, and setup checklist.",
    type: "single",
    options: ["Customer support", "Billing and refunds", "Account access", "Product questions", "Internal operations"],
  },
  {
    key: "companyName" as const,
    eyebrow: "Company",
    title: "What is your company or workspace name?",
    body: "We will create your first Sift workspace from this name so you do not need to create an organization manually.",
    type: "text",
    placeholder: "Example: Coco Technology",
  },
  {
    key: "teamSize" as const,
    eyebrow: "Team size",
    title: "How many people work on support?",
    body: "A solo owner, small team, and larger support group need different defaults.",
    type: "single",
    options: ["Just me", "2-5 people", "6-15 people", "16-50 people", "50+ people"],
  },
  {
    key: "industry" as const,
    eyebrow: "Industry",
    title: "What kind of business is this for?",
    body: "Sift can use this context later for triage examples, routing, and response tone.",
    type: "single",
    options: ["SaaS", "E-commerce", "Marketplace", "Agency", "Education", "Other"],
  },
  {
    key: "supportVolume" as const,
    eyebrow: "Volume",
    title: "How busy is the inbox right now?",
    body: "This helps decide whether to start with manual import, saved views, or workflow health checks.",
    type: "single",
    options: ["A few emails per week", "1-10 emails per day", "10-50 emails per day", "50+ emails per day"],
  },
  {
    key: "mainWork" as const,
    eyebrow: "Support topics",
    title: "Which conversations should Sift understand first?",
    body: "Choose all that apply. You can adjust these later in settings.",
    type: "multi",
    options: ["Refunds", "Billing", "Technical issues", "Account lockouts", "Product questions", "Spam cleanup"],
  },
];

const tourItems = [
  ["Dashboard", "Start with queue health, approvals, AI usage, and the setup checklist."],
  ["Gmail settings", "Connect inboxes, monitor sync/watch health, and import conversations."],
  ["Triage queue", "Filter, save views, assign, resolve, retry AI, and approve replies."],
  ["Ticket detail", "Review the customer message, AI reasoning, SLA state, attachments, and draft trail."],
  ["Team roles", "Invite admins and agents, then keep permissions aligned with real responsibilities."],
  ["Readiness", "Watch usage caps, pilot controls, data export, and known issues before going live."],
];

function emptyAnswers(): OnboardingAnswers {
  return { purpose: "", companyName: "", teamSize: "", industry: "", supportVolume: "", mainWork: [] };
}

export function OnboardingStep(_props?: { step?: string }) {
  const router = useRouter();
  const supabase = createClient();
  const [answers, setAnswers] = useState<OnboardingAnswers>(emptyAnswers);
  const [index, setIndex] = useState(0);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [tour, setTour] = useState(false);
  const [invitedWorkspaceName, setInvitedWorkspaceName] = useState<string | null>(null);
  const question = questions[index];
  const progress = tour ? 100 : ((index + 1) / (questions.length + 1)) * 100;

  useEffect(() => {
    if (tour) return;
    async function skipCompanySetupForInvitedTeammate() {
      const { data } = await supabase.auth.getSession();
      const accessToken = data.session?.access_token;
      if (!accessToken) return;
      try {
        const me = await getMe(accessToken);
        const invitedOrganization = me.organizations.find((organization) => organization.joined_via_invite || organization.role !== "owner");
        if (!invitedOrganization) return;
        setStoredOrganizationId(invitedOrganization.id);
        setInvitedWorkspaceName(invitedOrganization.name);
        await supabase.auth.updateUser({
          data: {
            onboarding_completed: true,
            invited_onboarding_completed: true,
            company_name: invitedOrganization.name,
          },
        });
        setTour(true);
      } catch {
        // Keep the standard onboarding available if invite detection fails.
      }
    }
    void skipCompanySetupForInvitedTeammate();
  }, [supabase, tour]);
  const canContinue = useMemo(() => {
    const value = answers[question.key];
    if (Array.isArray(value)) return value.length > 0;
    return value.trim().length > 0;
  }, [answers, question.key]);

  function setSingle(value: string) {
    setAnswers((current) => ({ ...current, [question.key]: value }));
  }

  function toggleMulti(value: string) {
    setAnswers((current) => {
      const selected = current.mainWork.includes(value) ? current.mainWork.filter((item) => item !== value) : [...current.mainWork, value];
      return { ...current, mainWork: selected };
    });
  }

  async function finishPersonalization() {
    setSaving(true);
    setMessage(null);
    try {
      const { data } = await supabase.auth.getSession();
      const accessToken = data.session?.access_token;
      if (!accessToken) {
        router.push("/login");
        return;
      }

      await supabase.auth.updateUser({
        data: {
          onboarding_completed: true,
          onboarding_profile: answers,
          company_name: answers.companyName,
          company_industry: answers.industry,
          support_team_size: answers.teamSize,
          support_purpose: answers.purpose,
        },
      });
      window.localStorage.setItem("sift-onboarding-profile", JSON.stringify(answers));

      const me = await getMe(accessToken);
      const existing = me.organizations[0];
      if (existing) {
        setStoredOrganizationId(existing.id);
      } else {
        const created = await createOrganization(accessToken, answers.companyName.trim() || "My Sift Workspace");
        setStoredOrganizationId(created.id);
      }
      setTour(true);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not finish onboarding.");
    } finally {
      setSaving(false);
    }
  }

  async function handleNext() {
    if (!canContinue) return;
    if (index < questions.length - 1) {
      setIndex((current) => current + 1);
      return;
    }
    await finishPersonalization();
  }

  if (tour) {
    return (
      <main className="onboarding-shell personalized-onboarding">
        <section className="wizard onboarding-tour-card">
          <div className="wizard-head"><SiftLogo /><span className="micro">Introduction tour</span></div>
          <div className="progress"><i style={{ width: `${progress}%` }} /></div>
          <div className="wizard-body animated-question">
            <span className="eyebrow">Let&apos;s get started</span>
            <h1>{invitedWorkspaceName ? `You joined ${invitedWorkspaceName}.` : "Your workspace is ready. Here is where everything lives."}</h1>
            <p>{invitedWorkspaceName ? "Your owner already set up the company workspace. Start from the dashboard, review assigned tickets, and use the queue your team shares." : "Sift is set up around your company profile. Start with Gmail when you are ready, then use the queue and approval flow to manage real conversations."}</p>
            <div className="tour-grid">
              {tourItems.map(([title, body]) => <article key={title}><strong>{title}</strong><p>{body}</p></article>)}
            </div>
            <div className="hero-actions">
              {invitedWorkspaceName ? null : <Link className="button primary" href="/dashboard/settings/gmail">Connect Gmail</Link>}
              <Link className={invitedWorkspaceName ? "button primary" : "button secondary"} href="/dashboard">Open dashboard</Link>
            </div>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="onboarding-shell personalized-onboarding">
      <section className="wizard onboarding-question-card">
        <div className="wizard-head"><SiftLogo /><span className="micro">Question {index + 1} of {questions.length}</span></div>
        <div className="progress"><i style={{ width: `${progress}%` }} /></div>
        <div className="wizard-body animated-question" key={question.key}>
          <span className="eyebrow">{question.eyebrow}</span>
          <h1>{question.title}</h1>
          <p>{question.body}</p>
          {question.type === "text" ? (
            <label className="field onboarding-input-label">Company name<input className="input" autoFocus value={answers.companyName} placeholder={question.placeholder} onChange={(event) => setAnswers((current) => ({ ...current, companyName: event.target.value }))} /></label>
          ) : null}
          {question.type === "single" ? (
            <div className="onboarding-choice-grid">
              {question.options?.map((option) => <button key={option} type="button" className={answers[question.key] === option ? "selected" : ""} onClick={() => setSingle(option)}>{option}</button>)}
            </div>
          ) : null}
          {question.type === "multi" ? (
            <div className="onboarding-choice-grid">
              {question.options?.map((option) => <button key={option} type="button" className={answers.mainWork.includes(option) ? "selected" : ""} onClick={() => toggleMulti(option)}>{option}</button>)}
            </div>
          ) : null}
          <div className="hero-actions">
            {index > 0 ? <button className="button secondary" type="button" onClick={() => setIndex((current) => current - 1)}>Back</button> : null}
            <button className="button primary" type="button" disabled={!canContinue || saving} onClick={() => void handleNext()}>{saving ? "Creating workspace..." : index === questions.length - 1 ? "Finish setup" : "Continue"}</button>
            <Link className="button ghost" href="/dashboard">Skip for now</Link>
          </div>
          {message ? <p className="auth-message error">{message}</p> : null}
        </div>
      </section>
    </main>
  );
}