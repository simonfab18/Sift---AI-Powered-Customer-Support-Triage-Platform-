"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import { getStoredOrganizationId } from "@/features/organizations/components/OrganizationManager";
import { getWorkspaceSettings, updateWorkspaceSettings } from "@/features/tickets/api";
import type { WorkspaceSettings as WorkspaceSettingsType } from "@/features/tickets/types";
import { createClient } from "@/lib/supabase/client";

const weekdays = [
  { key: "0", label: "Monday" },
  { key: "1", label: "Tuesday" },
  { key: "2", label: "Wednesday" },
  { key: "3", label: "Thursday" },
  { key: "4", label: "Friday" },
];

function defaultHours(settings: WorkspaceSettingsType | null) {
  const hours = settings?.business_hours ?? {};
  return weekdays.reduce<Record<string, { start: string; end: string }>>((current, day) => {
    current[day.key] = {
      start: hours[day.key]?.start ?? "09:00",
      end: hours[day.key]?.end ?? "17:00",
    };
    return current;
  }, {});
}

export function WorkspaceSettings() {
  const supabase = createClient();
  const [settings, setSettings] = useState<WorkspaceSettingsType | null>(null);
  const [signature, setSignature] = useState("Best regards,\nCustomer Support Team");
  const [timezone, setTimezone] = useState("UTC");
  const [firstReviewMinutes, setFirstReviewMinutes] = useState(240);
  const [resolutionMinutes, setResolutionMinutes] = useState(1440);
  const [businessHours, setBusinessHours] = useState<Record<string, { start: string; end: string }>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  async function getContext() {
    const organizationId = getStoredOrganizationId();
    const { data } = await supabase.auth.getSession();
    const accessToken = data.session?.access_token;
    if (!organizationId || !accessToken) return null;
    return { organizationId, accessToken };
  }

  async function loadSettings() {
    setLoading(true);
    setMessage(null);
    const context = await getContext();
    if (!context) {
      setMessage("Select a workspace and sign in before editing settings.");
      setLoading(false);
      return;
    }
    try {
      const loaded = await getWorkspaceSettings(context.organizationId, context.accessToken);
      setSettings(loaded);
      setSignature(loaded.default_reply_signature);
      setTimezone(loaded.business_timezone);
      setFirstReviewMinutes(loaded.first_review_target_minutes);
      setResolutionMinutes(loaded.resolution_target_minutes);
      setBusinessHours(defaultHours(loaded));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to load workspace settings.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadSettings();
  }, []);

  function updateDay(dayKey: string, field: "start" | "end", value: string) {
    setBusinessHours((current) => ({
      ...current,
      [dayKey]: { ...(current[dayKey] ?? { start: "09:00", end: "17:00" }), [field]: value },
    }));
  }

  async function handleSave() {
    const context = await getContext();
    if (!context) return;
    setSaving(true);
    setMessage(null);
    try {
      const updated = await updateWorkspaceSettings(context.organizationId, context.accessToken, {
        default_reply_signature: signature,
        business_timezone: timezone,
        business_hours: businessHours,
        first_review_target_minutes: firstReviewMinutes,
        resolution_target_minutes: resolutionMinutes,
      });
      setSettings(updated);
      setMessage("Workspace settings saved.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to save workspace settings.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_360px]">
      <div className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="font-display text-lg font-semibold">Workspace preferences</h2>
        {loading ? <p className="mt-3 text-sm text-slate-500">Loading settings...</p> : null}
        <label className="mt-5 block text-sm font-medium text-slate-700" htmlFor="signature">Default reply signature</label>
        <textarea id="signature" value={signature} onChange={(event) => setSignature(event.target.value)} rows={6} className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2 text-sm leading-6 outline-none focus:border-slate-900" />

        <div className="mt-6 border-t border-slate-200 pt-5">
          <h3 className="font-display text-base font-semibold">SLA timers</h3>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <label className="block text-sm font-medium text-slate-700" htmlFor="timezone">Timezone
              <input id="timezone" value={timezone} onChange={(event) => setTimezone(event.target.value)} className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-normal" />
            </label>
            <label className="block text-sm font-medium text-slate-700" htmlFor="first-review">First review minutes
              <input id="first-review" type="number" min={1} value={firstReviewMinutes} onChange={(event) => setFirstReviewMinutes(Number(event.target.value))} className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-normal" />
            </label>
            <label className="block text-sm font-medium text-slate-700" htmlFor="resolution-target">Resolution minutes
              <input id="resolution-target" type="number" min={1} value={resolutionMinutes} onChange={(event) => setResolutionMinutes(Number(event.target.value))} className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-normal" />
            </label>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {weekdays.map((day) => (
              <div key={day.key} className="rounded-md border border-slate-200 p-3">
                <p className="text-sm font-medium text-slate-700">{day.label}</p>
                <div className="mt-2 grid grid-cols-2 gap-2">
                  <input aria-label={`${day.label} start`} type="time" value={businessHours[day.key]?.start ?? "09:00"} onChange={(event) => updateDay(day.key, "start", event.target.value)} className="rounded-md border border-slate-300 px-3 py-2 text-sm" />
                  <input aria-label={`${day.label} end`} type="time" value={businessHours[day.key]?.end ?? "17:00"} onChange={(event) => updateDay(day.key, "end", event.target.value)} className="rounded-md border border-slate-300 px-3 py-2 text-sm" />
                </div>
              </div>
            ))}
          </div>
        </div>

        <Button type="button" variant="primary" className="mt-5" onClick={() => void handleSave()} disabled={saving}>{saving ? "Saving..." : "Save settings"}</Button>
        {message ? <p className="mt-4 text-sm text-slate-600">{message}</p> : null}
      </div>
      <div className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="font-display text-lg font-semibold">Current policy</h2>
        <dl className="mt-4 space-y-3 text-sm">
          <div><dt className="text-slate-500">Draft policy</dt><dd className="font-medium">{settings?.draft_requires_approval ? "Human approval required" : "Approval optional"}</dd></div>
          <div><dt className="text-slate-500">Sync</dt><dd className="font-medium">{settings?.sync_enabled ? "Enabled" : "Paused"}</dd></div>
          <div><dt className="text-slate-500">Auto triage</dt><dd className="font-medium">{settings?.auto_triage_enabled ? "Enabled" : "Paused"}</dd></div>
          <div><dt className="text-slate-500">SLA basis</dt><dd className="font-medium">Business hours</dd></div>
        </dl>
      </div>
    </div>
  );
}
