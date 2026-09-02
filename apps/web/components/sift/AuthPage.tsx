"use client";

import Link from "next/link";
import { FormEvent, ReactNode, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { createClient } from "@/lib/supabase/client";

type AuthMode = "login" | "signup";

export function AuthPage({ mode }: { mode: AuthMode }) {
  const signup = mode === "signup";
  const router = useRouter();
  const supabase = createClient();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setMessage(null);

    const origin = window.location.origin;
    const fullName = [firstName.trim(), lastName.trim()].filter(Boolean).join(" ");
    const result = signup
      ? await supabase.auth.signUp({
          email,
          password,
          options: {
            data: {
              first_name: firstName.trim(),
              last_name: lastName.trim(),
              full_name: fullName,
            },
            emailRedirectTo: `${origin}/auth/callback?next=/onboarding`,
          },
        })
      : await supabase.auth.signInWithPassword({ email, password });

    setLoading(false);

    if (result.error) {
      setMessage(result.error.message);
      return;
    }

    if (signup && !result.data.session) {
      router.push(`/verify-email?email=${encodeURIComponent(email)}`);
      return;
    }

    router.push(signup ? "/onboarding" : "/dashboard");
    router.refresh();
  }

  return (
    <main className="auth-layout polished-auth">
      <section className="auth-visual">
        <Link href="/" className="sift-logo"><span className="sift-mark sift-mark-dark"><span /><span /><span /></span><span>Sift</span></Link>
        <div className="auth-hero-copy">
          <span className="eyebrow">Human-approved AI</span>
          <h1>{signup ? "Start a calmer support workflow." : "Welcome back to your support command center."}</h1>
          <p>{signup ? "Create your free pilot workspace, connect Gmail, and keep every AI reply human-approved." : "Sign in to review tickets, approve drafts, and monitor Gmail workflow health."}</p>
        </div>
        <div className="auth-preview-card">
          <div className="queue-row"><span className="severity-dot high" /><div><strong>Refund request from VIP account</strong><br /><small>Moved to high priority - AI suggestion ready</small></div></div>
          <div className="auth-mini-metrics"><span>Approval first</span><span>Gmail connected</span><span>Free pilot</span></div>
        </div>
      </section>
      <section className="auth-card-wrap">
        <div className="auth-card polished-card">
          <Link href="/" className="sift-logo"><span className="sift-mark"><span /><span /><span /></span><span>Sift</span></Link>
          <div className="auth-card-heading">
            <span>{signup ? "Start free" : "Sign in"}</span>
            <h1>{signup ? "Create your account" : "Welcome back"}</h1>
            <p>{signup ? "No credit card required. Start with the Gmail-first free pilot." : "Continue to your workspace and support queue."}</p>
          </div>
          <div className="social-row">
            <button className="button secondary" type="button" disabled>Google</button>
            <button className="button secondary" type="button" disabled>GitHub</button>
          </div>
          <div className="divider">or {signup ? "use your work email" : "continue with email"}</div>
          <form className="form-grid" onSubmit={handleSubmit}>
            {signup ? (
              <div className="name-grid">
                <label className="field">First name<input className="input" name="firstName" autoComplete="given-name" value={firstName} onChange={(event) => setFirstName(event.target.value)} required /></label>
                <label className="field">Last name<input className="input" name="lastName" autoComplete="family-name" value={lastName} onChange={(event) => setLastName(event.target.value)} required /></label>
              </div>
            ) : null}
            <label className="field">Work email<input className="input" name="email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
            <label className="field">Password<input className="input" name="password" type="password" autoComplete={signup ? "new-password" : "current-password"} value={password} onChange={(event) => setPassword(event.target.value)} required minLength={6} /></label>
            {signup ? <label className="auth-check"><input type="checkbox" required /> I agree to the <Link href="/terms">Terms</Link> and <Link href="/privacy">Privacy Policy</Link>.</label> : <div className="auth-row"><label><input type="checkbox" /> Remember me</label><Link href="/forgot-password">Forgot password?</Link></div>}
            <button className="button primary auth-submit" type="submit" disabled={loading}>{loading ? "Working..." : signup ? "Create account" : "Sign in"}</button>
          </form>
          {message ? <p className="auth-message error">{message}</p> : null}
          <p className="auth-switch">{signup ? "Already have an account?" : "Don't have an account?"} <Link className="quiet-link" href={signup ? "/login" : "/signup"}>{signup ? "Sign in" : "Start free"}</Link></p>
        </div>
      </section>
    </main>
  );
}

export function ForgotPasswordPage() {
  const supabase = createClient();
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setMessage(null);
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/auth/callback?next=/reset-password`,
    });
    setLoading(false);
    setMessage(error ? error.message : "Check your email for a password reset link.");
  }

  return <AuthSimple title="Reset your password" body="Enter your work email and Sift will send reset instructions." message={message}><form className="form-grid" onSubmit={handleSubmit}><label className="field">Work email<input className="input" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label><button className="button primary auth-submit" type="submit" disabled={loading}>{loading ? "Sending..." : "Send reset link"}</button></form></AuthSimple>;
}

export function VerifyEmailPage() {
  const searchParams = useSearchParams();
  const email = searchParams.get("email");
  return <AuthSimple title="Check your email" body={`Use the verification link${email ? ` sent to ${email}` : ""} to finish creating your Sift workspace.`}><Link className="button primary auth-submit" href="/login">Back to sign in</Link></AuthSimple>;
}

export function ResetPasswordPage() {
  const router = useRouter();
  const supabase = createClient();
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setMessage(null);
    const { error } = await supabase.auth.updateUser({ password });
    setLoading(false);
    if (error) {
      setMessage(error.message);
      return;
    }
    router.push("/dashboard");
    router.refresh();
  }

  return <AuthSimple title="Choose a new password" body="Enter a new password for your Sift account." message={message} error><form className="form-grid" onSubmit={handleSubmit}><label className="field">New password<input className="input" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required minLength={6} /></label><button className="button primary auth-submit" type="submit" disabled={loading}>{loading ? "Saving..." : "Update password"}</button></form></AuthSimple>;
}

function AuthSimple({ title, body, children, message, error = false }: { title: string; body: string; children: ReactNode; message?: string | null; error?: boolean }) {
  return <main className="onboarding-shell polished-simple-auth"><section className="auth-card polished-card"><Link href="/" className="sift-logo"><span className="sift-mark"><span /><span /><span /></span><span>Sift</span></Link><div className="auth-card-heading"><span>Account access</span><h1>{title}</h1><p>{body}</p></div>{children}{message ? <p className={`auth-message ${error ? "error" : ""}`}>{message}</p> : null}<p className="auth-switch"><Link className="quiet-link" href="/login">Back to sign in</Link></p></section></main>;
}