"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { createClient } from "@/lib/supabase/client";

type AuthMode = "login" | "signup";

export function AuthPage({ mode }: { mode: AuthMode }) {
  const signup = mode === "signup";
  const router = useRouter();
  const supabase = createClient();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setMessage(null);

    const origin = window.location.origin;
    const result = signup
      ? await supabase.auth.signUp({
          email,
          password,
          options: {
            data: name ? { full_name: name } : undefined,
            emailRedirectTo: `${origin}/auth/callback?next=/dashboard`,
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

    router.push("/dashboard");
    router.refresh();
  }

  return (
    <main className="auth-layout">
      <section className="auth-visual">
        <Link href="/" className="sift-logo"><span className="sift-mark sift-mark-dark"><span /><span /><span /></span><span>Sift</span></Link>
        <div>
          <span className="eyebrow" style={{ color: "#bfc7d8" }}>Human-approved AI</span>
          <h1 style={{ fontSize: 52, lineHeight: 1.04, margin: "12px 0" }}>A calmer support queue starts here.</h1>
          <p>Sift moves tickets from untriaged noise into clear priority, suggested response, and approval.</p>
        </div>
        <div className="panel" style={{ color: "var(--ink)" }}>
          <div className="queue-row"><span className="severity-dot high" /><div><strong>Refund request from VIP account</strong><br /><small>Moved to high priority · AI suggestion ready</small></div></div>
        </div>
      </section>
      <section className="auth-card-wrap">
        <div className="auth-card">
          <Link href="/" className="sift-logo"><span className="sift-mark"><span /><span /><span /></span><span>Sift</span></Link>
          <h1 style={{ marginTop: 26 }}>{signup ? "Create your Sift workspace" : "Welcome back"}</h1>
          <p style={{ color: "var(--muted)" }}>{signup ? "Start organizing support conversations in minutes." : "Sign in to continue to your Sift workspace."}</p>
          <div className="social-row">
            {/* TODO: Wire to Supabase Google OAuth when backend auth policy is ready. */}
            <button className="button secondary" type="button" disabled>Google</button>
            {/* TODO: Wire to Supabase GitHub OAuth when backend auth policy is ready. */}
            <button className="button secondary" type="button" disabled>GitHub</button>
          </div>
          <div className="divider">or {signup ? "use your work email" : "continue with email"}</div>
          <form className="form-grid" onSubmit={handleSubmit}>
            {signup ? <label className="field">Full name<input className="input" name="name" autoComplete="name" value={name} onChange={(event) => setName(event.target.value)} /></label> : null}
            <label className="field">Work email<input className="input" name="email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
            <label className="field">Password<input className="input" name="password" type="password" autoComplete={signup ? "new-password" : "current-password"} value={password} onChange={(event) => setPassword(event.target.value)} required minLength={6} /></label>
            {signup ? <label style={{ display: "flex", gap: 8, color: "var(--muted)", fontSize: 13 }}><input type="checkbox" required /> I agree to the Terms and Privacy Policy</label> : <div style={{ display: "flex", justifyContent: "space-between", color: "var(--muted)", fontSize: 13 }}><label><input type="checkbox" /> Remember me</label><Link href="/forgot-password">Forgot password?</Link></div>}
            <button className="button primary" type="submit" disabled={loading}>{loading ? "Working..." : signup ? "Create account" : "Sign in"}</button>
          </form>
          {message ? <p style={{ color: "var(--critical)", fontSize: 14, marginTop: 16 }}>{message}</p> : null}
          <p style={{ color: "var(--muted)", fontSize: 14, marginTop: 20 }}>{signup ? "Already have an account?" : "Don't have an account?"} <Link className="quiet-link" href={signup ? "/login" : "/signup"}>{signup ? "Sign in" : "Create one"}</Link></p>
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

  return <main className="onboarding-shell"><section className="auth-card"><Link href="/" className="sift-logo"><span className="sift-mark"><span /><span /><span /></span><span>Sift</span></Link><h1>Reset your password</h1><p style={{color:"var(--muted)"}}>Enter your work email and Sift will send reset instructions.</p><form className="form-grid" onSubmit={handleSubmit}><label className="field">Work email<input className="input" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label><button className="button primary" type="submit" disabled={loading}>{loading ? "Sending..." : "Send reset link"}</button></form>{message ? <p style={{ color: "var(--muted)", marginTop: 16 }}>{message}</p> : null}</section></main>;
}

export function VerifyEmailPage() {
  const searchParams = useSearchParams();
  const email = searchParams.get("email");
  return <main className="onboarding-shell"><section className="auth-card"><Link href="/" className="sift-logo"><span className="sift-mark"><span /><span /><span /></span><span>Sift</span></Link><h1>Check your email</h1><p style={{color:"var(--muted)"}}>Use the verification link{email ? ` sent to ${email}` : ""} to finish creating your Sift workspace.</p><Link className="button primary" href="/login">Back to sign in</Link></section></main>;
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

  return <main className="onboarding-shell"><section className="auth-card"><Link href="/" className="sift-logo"><span className="sift-mark"><span /><span /><span /></span><span>Sift</span></Link><h1>Choose a new password</h1><p style={{color:"var(--muted)"}}>Enter a new password for your Sift account.</p><form className="form-grid" onSubmit={handleSubmit}><label className="field">New password<input className="input" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required minLength={6} /></label><button className="button primary" type="submit" disabled={loading}>{loading ? "Saving..." : "Update password"}</button></form>{message ? <p style={{ color: "var(--critical)", marginTop: 16 }}>{message}</p> : null}</section></main>;
}
