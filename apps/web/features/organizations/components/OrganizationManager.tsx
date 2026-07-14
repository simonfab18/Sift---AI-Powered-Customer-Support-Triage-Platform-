"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";

import { createOrganization, getMe } from "@/lib/api-client";
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

  async function loadOrganizations() {
    setLoading(true);
    setMessage(null);
    const { data } = await supabase.auth.getSession();
    if (!data.session) {
      setMessage("Sign in before creating an organization.");
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

  return (
    <div className="mt-8 grid gap-6 lg:grid-cols-[1.2fr_1fr]">
      <div className="rounded-lg border border-slate-200 bg-white p-6">
        <h2 className="text-base font-semibold">Your organizations</h2>
        {loading ? <p className="mt-3 text-sm text-slate-600">Loading...</p> : null}
        {!loading && organizations.length === 0 ? (
          <p className="mt-3 text-sm text-slate-600">Create your first organization to continue.</p>
        ) : null}
        <div className="mt-4 space-y-2">
          {organizations.map((organization) => (
            <button
              key={organization.id}
              type="button"
              onClick={() => handleSelect(organization.id)}
              className={`w-full rounded-md border px-4 py-3 text-left text-sm ${
                selectedOrganizationId === organization.id
                  ? "border-slate-950 bg-slate-50"
                  : "border-slate-200 bg-white"
              }`}
            >
              <span className="block font-medium">{organization.name}</span>
              <span className="mt-1 block text-xs text-slate-500">{organization.role}</span>
            </button>
          ))}
        </div>
        {selectedOrganizationId ? (
          <Link
            href="/dashboard/settings/gmail"
            className="mt-5 inline-flex rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white"
          >
            Continue to Gmail import
          </Link>
        ) : null}
      </div>

      <form onSubmit={handleCreateOrganization} className="rounded-lg border border-slate-200 bg-white p-6">
        <h2 className="text-base font-semibold">Create organization</h2>
        <label className="mt-5 block text-sm font-medium text-slate-700" htmlFor="org-name">
          Organization name
        </label>
        <input
          id="org-name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          required
          className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-slate-950"
        />
        <button type="submit" className="mt-5 rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white">
          Create organization
        </button>
        {message ? <p className="mt-4 text-sm text-slate-600">{message}</p> : null}
      </form>
    </div>
  );
}
