"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { createOrganization, getMe, requestOrganizationDeletion } from "@/lib/api-client";
import type { Organization } from "@/lib/api-types";
import { createClient } from "@/lib/supabase/client";

const SELECTED_ORG_KEY = "support-triage:selected-org-id";

export function getStoredOrganizationId() {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(SELECTED_ORG_KEY);
}

export function setStoredOrganizationId(organizationId: string) {
  window.localStorage.setItem(SELECTED_ORG_KEY, organizationId);
}

export function OrganizationManager() {
  const supabase = createClient();
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [selectedOrganizationId, setSelectedOrganizationId] = useState<string | null>(null);
  const [name, setName] = useState("Acme Support");
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [removeTarget, setRemoveTarget] = useState<Organization | null>(null);
  const [removeConfirmation, setRemoveConfirmation] = useState("");
  const [removing, setRemoving] = useState(false);

  const selectedOrganization = useMemo(
    () => organizations.find((organization) => organization.id === selectedOrganizationId) ?? null,
    [organizations, selectedOrganizationId],
  );
  const canManageSelected = selectedOrganization?.role === "owner" || selectedOrganization?.role === "admin";
  const canCreateOrganizations = organizations.length === 0 || organizations.some((organization) => organization.role === "owner" || organization.role === "admin");

  async function loadOrganizations() {
    setLoading(true);
    setMessage(null);
    const { data } = await supabase.auth.getSession();
    if (!data.session) {
      setMessage("Sign in before choosing an organization.");
      setLoading(false);
      return;
    }

    try {
      const me = await getMe(data.session.access_token);
      setOrganizations(me.organizations);
      const stored = getStoredOrganizationId();
      const selected = me.organizations.find((organization) => organization.id === stored) ?? me.organizations[0];
      if (selected) {
        setSelectedOrganizationId(selected.id);
        setStoredOrganizationId(selected.id);
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to load organizations.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadOrganizations();
  }, []);

  async function handleCreateOrganization(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    if (!canCreateOrganizations) {
      setMessage("Agents cannot create organizations. Ask an owner or admin to invite you to the right workspace.");
      return;
    }
    const { data } = await supabase.auth.getSession();
    if (!data.session) {
      setMessage("Sign in before creating an organization.");
      return;
    }

    try {
      const organization = await createOrganization(data.session.access_token, name);
      setStoredOrganizationId(organization.id);
      setSelectedOrganizationId(organization.id);
      setName("");
      await loadOrganizations();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to create organization.");
    }
  }

  function handleSelect(organizationId: string) {
    setSelectedOrganizationId(organizationId);
    setStoredOrganizationId(organizationId);
  }

  async function handleRemoveOrganization() {
    if (!removeTarget || removeConfirmation !== "Remove") return;
    const { data } = await supabase.auth.getSession();
    if (!data.session) return;
    setRemoving(true);
    setMessage(null);
    try {
      await requestOrganizationDeletion(data.session.access_token, removeTarget.id, "Removed from organization manager.");
      const removedOrganizationId = removeTarget.id;
      const remainingOrganizations = organizations.filter((organization) => organization.id !== removedOrganizationId);
      setOrganizations(remainingOrganizations);
      const nextSelectedOrganization = remainingOrganizations[0] ?? null;
      setSelectedOrganizationId(nextSelectedOrganization?.id ?? null);
      if (nextSelectedOrganization) {
        setStoredOrganizationId(nextSelectedOrganization.id);
      } else {
        window.localStorage.removeItem(SELECTED_ORG_KEY);
      }
      setMessage(`${removeTarget.name} was removed from your organization list. Sync, AI triage, and draft creation were paused for safety.`);
      setRemoveTarget(null);
      setRemoveConfirmation("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to remove organization.");
    } finally {
      setRemoving(false);
    }
  }

  return (
    <div className="mt-8 grid gap-6 lg:grid-cols-[1.2fr_1fr]">
      <div className="rounded-lg border border-white/60 bg-white/60 p-6 shadow-[0_18px_48px_rgba(72,60,96,0.075)] backdrop-blur-xl">
        <h2 className="text-base font-semibold text-slate-950">Your organizations</h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">Choose the workspace you want to operate. Owners and admins can manage Gmail setup and request removal.</p>
        {loading ? <p className="mt-3 text-sm text-slate-600">Loading...</p> : null}
        {!loading && organizations.length === 0 ? (
          <p className="mt-3 text-sm text-slate-600">Create your first organization to continue.</p>
        ) : null}
        <div className="mt-4 space-y-2">
          {organizations.map((organization) => {
            const canManage = organization.role === "owner" || organization.role === "admin";
            return (
              <div key={organization.id} className={`rounded-md border p-4 text-sm ${selectedOrganizationId === organization.id ? "border-[#cfc7dd] bg-white/70" : "border-white/60 bg-white/45"}`}>
                <button type="button" onClick={() => handleSelect(organization.id)} className="w-full text-left">
                  <span className="block font-medium text-slate-950">{organization.name}</span>
                  <span className="mt-1 block text-xs capitalize text-slate-500">{organization.role}</span>
                  <span className="mt-1 block font-mono text-[11px] text-slate-400">{organization.id}</span>
                </button>
                {selectedOrganizationId === organization.id ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {canManage ? <Link href="/dashboard/settings/gmail" className="rounded-md bg-slate-950 px-3 py-2 text-xs font-semibold text-white">Continue to Gmail import</Link> : null}
                    {canManage ? <button type="button" onClick={() => { setRemoveTarget(organization); setRemoveConfirmation(""); }} className="rounded-md border border-[#d8d2e4] bg-white/60 px-3 py-2 text-xs font-semibold text-[#6f6174]">Remove organization</button> : null}
                    {!canManage ? <span className="rounded-md border border-white/60 bg-white/50 px-3 py-2 text-xs font-semibold text-slate-500">Agent access: Gmail import unavailable</span> : null}
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      </div>

      {canCreateOrganizations ? (
        <form onSubmit={handleCreateOrganization} className="rounded-lg border border-white/60 bg-white/60 p-6 shadow-[0_18px_48px_rgba(72,60,96,0.075)] backdrop-blur-xl">
          <h2 className="text-base font-semibold text-slate-950">Create organization</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">Owners and admins can create another workspace. Agents should be invited by an owner/admin.</p>
          <label className="mt-5 block text-sm font-medium text-slate-700" htmlFor="org-name">
            Organization name
          </label>
          <input
            id="org-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
            className="mt-2 w-full rounded-md border border-[#ddd7e6] bg-white/70 px-3 py-2 text-sm outline-none focus:border-[#756f9f]"
          />
          <button type="submit" className="mt-5 rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white">
            Create organization
          </button>
          {message ? <p className="mt-4 text-sm text-slate-600">{message}</p> : null}
        </form>
      ) : (
        <section className="rounded-lg border border-white/60 bg-white/60 p-6 shadow-[0_18px_48px_rgba(72,60,96,0.075)] backdrop-blur-xl">
          <h2 className="text-base font-semibold text-slate-950">Organization access</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">Your current role is agent. Agents can work assigned tickets, but cannot create organizations or continue to Gmail import setup.</p>
          {message ? <p className="mt-4 text-sm text-slate-600">{message}</p> : null}
        </section>
      )}

      {removeTarget ? (
        <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/20 px-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="remove-org-title">
          <div className="w-full max-w-md rounded-xl border border-white/70 bg-white/95 p-5 shadow-[0_24px_80px_rgba(72,60,96,0.18)]">
            <h3 id="remove-org-title" className="font-display text-lg font-semibold text-slate-950">Remove organization?</h3>
            <p className="mt-3 text-sm leading-6 text-slate-600">This requests removal for {removeTarget.name}. Sift pauses Gmail sync, AI triage, and draft creation so no more work runs while the organization is reviewed.</p>
            <label className="mt-4 block text-sm font-medium text-slate-700">Type Remove to confirm</label>
            <input value={removeConfirmation} onChange={(event) => setRemoveConfirmation(event.target.value)} className="mt-2 w-full rounded-md border border-[#ddd7e6] bg-white px-3 py-2 text-sm" />
            <div className="mt-5 flex justify-end gap-2">
              <button type="button" onClick={() => setRemoveTarget(null)} className="rounded-md border border-[#ddd7e6] bg-white px-4 py-2 text-sm font-semibold text-slate-700">Cancel</button>
              <button type="button" onClick={() => void handleRemoveOrganization()} disabled={removeConfirmation !== "Remove" || removing} className="rounded-md border border-[#d8d2e4] bg-white/70 px-4 py-2 text-sm font-semibold text-[#6f6174] disabled:cursor-not-allowed disabled:opacity-50">{removing ? "Removing..." : "Remove"}</button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}