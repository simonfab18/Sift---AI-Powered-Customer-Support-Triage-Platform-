"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { createClient } from "@/lib/supabase/client";

type ProfileForm = {
  firstName: string;
  lastName: string;
  companyName: string;
  jobTitle: string;
  phone: string;
};

export function AccountSettings() {
  const router = useRouter();
  const supabase = createClient();
  const [userId, setUserId] = useState<string | null>(null);
  const [email, setEmail] = useState<string | null>(null);
  const [form, setForm] = useState<ProfileForm>({ firstName: "", lastName: "", companyName: "", jobTitle: "", phone: "" });
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    async function loadProfile() {
      const { data } = await supabase.auth.getUser();
      const user = data.user;
      const metadata = user?.user_metadata ?? {};
      setUserId(user?.id ?? null);
      setEmail(user?.email ?? null);
      setForm({
        firstName: String(metadata.first_name ?? ""),
        lastName: String(metadata.last_name ?? ""),
        companyName: String(metadata.company_name ?? ""),
        jobTitle: String(metadata.job_title ?? ""),
        phone: String(metadata.phone ?? ""),
      });
    }
    void loadProfile();
  }, [supabase]);

  function updateField(field: keyof ProfileForm, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setMessage(null);
    const fullName = [form.firstName.trim(), form.lastName.trim()].filter(Boolean).join(" ");
    const { error } = await supabase.auth.updateUser({
      data: {
        first_name: form.firstName.trim(),
        last_name: form.lastName.trim(),
        full_name: fullName,
        company_name: form.companyName.trim(),
        job_title: form.jobTitle.trim(),
        phone: form.phone.trim(),
      },
    });
    setSaving(false);
    setMessage(error ? error.message : "Account profile saved.");
  }

  async function handleLogout() {
    await supabase.auth.signOut();
    window.localStorage.removeItem("support-triage:selected-org-id");
    window.localStorage.removeItem("sift-selected-organization-id");
    window.localStorage.removeItem("sift-onboarding-profile");
    router.push("/login");
    router.refresh();
  }

  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!password) return;
    setSaving(true);
    setMessage(null);
    const { error } = await supabase.auth.updateUser({ password });
    setSaving(false);
    if (!error) setPassword("");
    setMessage(error ? error.message : "Password updated.");
  }

  return (
    <section className="space-y-6">
      <div>
        <p className="font-mono text-xs uppercase tracking-wide text-slate-500">Account</p>
        <h2 className="font-display text-3xl font-semibold tracking-tight text-slate-900">Profile settings</h2>
        <p className="mt-2 max-w-2xl text-slate-600">Manage your personal identity, sign-in details, and free pilot account status.</p>
      </div>
      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <form onSubmit={saveProfile} className="rounded-lg border border-white/60 bg-white/60 p-6 shadow-[0_18px_48px_rgba(72,60,96,0.075)] backdrop-blur-xl">
          <h3 className="font-display text-lg font-semibold text-slate-950">Personal profile</h3>
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <label className="field">First name<input className="input" value={form.firstName} onChange={(event) => updateField("firstName", event.target.value)} /></label>
            <label className="field">Last name<input className="input" value={form.lastName} onChange={(event) => updateField("lastName", event.target.value)} /></label>
            <label className="field sm:col-span-2">Email<input className="input" value={email ?? ""} disabled /></label>
            <label className="field sm:col-span-2">Person ID<input className="input font-mono text-xs" value={userId ?? ""} disabled /></label>
            <label className="field">Company name<input className="input" value={form.companyName} onChange={(event) => updateField("companyName", event.target.value)} /></label>
            <label className="field">Job title<input className="input" value={form.jobTitle} onChange={(event) => updateField("jobTitle", event.target.value)} /></label>
            <label className="field sm:col-span-2">Phone<input className="input" value={form.phone} onChange={(event) => updateField("phone", event.target.value)} /></label>
          </div>
          <button className="button primary mt-5" type="submit" disabled={saving}>{saving ? "Saving..." : "Save profile"}</button>
        </form>
        <div className="space-y-6">
          <form onSubmit={changePassword} className="rounded-lg border border-white/60 bg-white/60 p-6 shadow-[0_18px_48px_rgba(72,60,96,0.075)] backdrop-blur-xl">
            <h3 className="font-display text-lg font-semibold text-slate-950">Password</h3>
            <p className="mt-2 text-sm leading-6 text-slate-600">Change the password for this Supabase Auth account.</p>
            <label className="field mt-4">New password<input className="input" type="password" value={password} minLength={6} onChange={(event) => setPassword(event.target.value)} /></label>
            <button className="button secondary mt-4 w-full" type="submit" disabled={saving || !password}>Update password</button>
          </form>
          <section className="rounded-lg border border-white/60 bg-white/60 p-6 shadow-[0_18px_48px_rgba(72,60,96,0.075)] backdrop-blur-xl">
            <h3 className="font-display text-lg font-semibold text-slate-950">Billing</h3>
            <p className="mt-2 text-sm leading-6 text-slate-600">Your account is on the free pilot. No payment method or subscription is required.</p>
          </section>
          <button type="button" onClick={() => void handleLogout()} className="button secondary w-full">Logout</button>
        </div>
      </div>
      {message ? <p className="rounded-lg border border-white/60 bg-white/60 p-4 text-sm text-slate-700 shadow-[0_18px_48px_rgba(72,60,96,0.075)]">{message}</p> : null}
    </section>
  );
}