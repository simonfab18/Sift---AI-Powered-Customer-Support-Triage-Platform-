"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/Button";
import { getStoredOrganizationId } from "@/features/organizations/components/OrganizationManager";
import { getMembers, inviteMember, removeMember, updateMemberRole } from "@/lib/api-client";
import type { Member } from "@/lib/api-types";
import { createClient } from "@/lib/supabase/client";

const roleDescriptions: Record<string, string> = {
  owner: "Full control of workspace, billing posture, team roles, and data controls.",
  admin: "Can manage Gmail, routing, workspace settings, and invite agents.",
  agent: "Can work tickets, review AI, approve drafts, assign, and resolve conversations.",
};

const roleLabels: Record<string, string> = {
  owner: "Owner",
  admin: "Admin",
  agent: "Agent",
};

type PendingAction =
  | { type: "role"; member: Member; nextRole: string }
  | { type: "remove"; member: Member }
  | null;

export function TeamSettings() {
  const supabase = createClient();
  const [members, setMembers] = useState<Member[]>([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("agent");
  const [message, setMessage] = useState<string | null>(null);
  const [manualInviteUrl, setManualInviteUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [pendingAction, setPendingAction] = useState<PendingAction>(null);
  const [savingAction, setSavingAction] = useState(false);
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);
  const [currentUserEmail, setCurrentUserEmail] = useState<string | null>(null);

  const counts = useMemo(() => ({
    active: members.filter((member) => member.status === "active").length,
    invited: members.filter((member) => member.status === "invited").length,
    admins: members.filter((member) => member.role === "admin" || member.role === "owner").length,
  }), [members]);

  async function context() {
    const organizationId = getStoredOrganizationId();
    const { data } = await supabase.auth.getSession();
    const session = data.session;
    const accessToken = session?.access_token;
    if (session?.user) {
      setCurrentUserId(session.user.id);
      setCurrentUserEmail(session.user.email?.toLowerCase() ?? null);
    }
    if (!organizationId || !accessToken) return null;
    return { organizationId, accessToken };
  }

  async function loadMembers({ clearMessage = true }: { clearMessage?: boolean } = {}) {
    setLoading(true);
    if (clearMessage) {
      setMessage(null);
      setManualInviteUrl(null);
    }
    const ctx = await context();
    if (!ctx) {
      setMessage("Select an organization and sign in first.");
      setLoading(false);
      return;
    }
    try {
      const loadedMembers = await getMembers(ctx.accessToken, ctx.organizationId);
      setMembers(loadedMembers.filter((member) => member.status !== "disabled"));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to load team.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadMembers();
  }, []);

  async function handleInvite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const ctx = await context();
    if (!ctx) return;
    try {
      const invited = await inviteMember(ctx.accessToken, ctx.organizationId, email, role);
      const invitedEmail = email;
      setEmail("");
      await loadMembers({ clearMessage: false });
      setManualInviteUrl(invited.invite_email_delivery_status === "sent" ? null : invited.invite_url ?? null);
      if (invited.invite_email_delivery_status === "sent") {
        setMessage(`Invitation email sent to ${invitedEmail}. They should sign up or sign in with that same email address.`);
      } else if (invited.invite_email_delivery_status === "failed") {
        setMessage(`Invitation record created for ${invitedEmail}, but email delivery failed: ${invited.invite_email_delivery_detail ?? "unknown error"}. Copy the manual invite link below.`);
      } else {
        setMessage(`Invitation record created for ${invitedEmail}. Email delivery is not configured yet, so copy the manual invite link below.`);
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to invite teammate.");
    }
  }

  function requestRoleChange(member: Member, nextRole: string) {
    if (nextRole === member.role) return;
    setPendingAction({ type: "role", member, nextRole });
  }

  async function confirmPendingAction() {
    if (!pendingAction) return;
    const ctx = await context();
    if (!ctx) return;
    setSavingAction(true);
    try {
      if (pendingAction.type === "role") {
        await updateMemberRole(ctx.accessToken, ctx.organizationId, pendingAction.member.id, pendingAction.nextRole);
        await loadMembers({ clearMessage: false });
        setMessage(`${pendingAction.member.email} is now ${roleLabels[pendingAction.nextRole] ?? pendingAction.nextRole}.`);
      } else {
        await removeMember(ctx.accessToken, ctx.organizationId, pendingAction.member.id);
        await loadMembers({ clearMessage: false });
        setMessage(`${pendingAction.member.email} was removed from this workspace.`);
      }
      setManualInviteUrl(null);
      setPendingAction(null);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Team action failed.");
    } finally {
      setSavingAction(false);
    }
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_380px]">
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-3">
          <TeamMetric label="Active members" value={counts.active} />
          <TeamMetric label="Pending invites" value={counts.invited} />
          <TeamMetric label="Owners/Admins" value={counts.admins} />
        </div>
        <div className="rounded-lg border border-white/60 bg-white/60 shadow-[0_18px_48px_rgba(72,60,96,0.075)] backdrop-blur-xl">
          <div className="border-b border-white/60 px-5 py-4">
            <h2 className="font-display text-lg font-semibold text-slate-950">Team members</h2>
            <p className="mt-1 text-sm text-slate-600">Owners and admins manage access. Agents focus on ticket work and approvals.</p>
          </div>
          {loading ? <p className="p-5 text-sm text-slate-500">Loading team...</p> : null}
          <div className="divide-y divide-white/60">
            {members.map((member) => {
              const isSelf = currentUserId === member.user_id || (currentUserEmail !== null && currentUserEmail === member.email.toLowerCase());
              return (
                <div key={member.id} className="grid gap-3 px-5 py-4 text-sm md:grid-cols-[1fr_auto_auto_auto] md:items-center">
                  <div>
                    <p className="font-medium text-slate-900">{member.email}{isSelf ? <span className="ml-2 rounded-full border border-white/60 bg-white/50 px-2 py-0.5 text-[11px] font-semibold text-slate-500">You</span> : null}</p>
                    <p className="mt-1 text-xs leading-5 text-slate-500">{roleDescriptions[member.role] ?? "Workspace member"}</p>
                    <p className="mt-1 font-mono text-[11px] text-slate-400">Person ID: {member.user_id}</p>
                  <div className="mt-3 grid grid-cols-2 gap-1.5 text-[11px] text-slate-500 sm:grid-cols-3 lg:grid-cols-6">
                    <MemberCount label="New" value={member.ticket_counts?.new ?? 0} />
                    <MemberCount label="Open" value={member.ticket_counts?.open ?? 0} />
                    <MemberCount label="Pending" value={member.ticket_counts?.pending ?? 0} />
                    <MemberCount label="Approval" value={member.ticket_counts?.awaiting_approval ?? 0} />
                    <MemberCount label="Resolved" value={member.ticket_counts?.resolved ?? 0} />
                    <MemberCount label="Total" value={member.ticket_counts?.total ?? 0} />
                  </div>
                  </div>
                  <span className="rounded-full border border-white/60 bg-white/50 px-3 py-1 text-xs font-semibold capitalize text-slate-600">{member.status}</span>
                  <select value={member.role} disabled={isSelf} onChange={(event) => requestRoleChange(member, event.target.value)} className="rounded-md border border-[#ddd7e6] bg-white/70 px-3 py-2 text-sm capitalize text-slate-800 disabled:cursor-not-allowed disabled:opacity-55" title={isSelf ? "You cannot change your own role." : "Change teammate role"}>
                    <option value="owner">Owner</option>
                    <option value="admin">Admin</option>
                    <option value="agent">Agent</option>
                  </select>
                  {isSelf ? (
                    <span className="rounded-md border border-white/60 bg-white/50 px-4 py-2 text-center text-sm font-semibold text-slate-500" title="You cannot remove yourself.">
                      Protected
                    </span>
                  ) : (
                    <Button type="button" variant="danger" onClick={() => setPendingAction({ type: "remove", member })}>
                      Remove
                    </Button>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="space-y-4">
        <form onSubmit={handleInvite} className="rounded-lg border border-white/60 bg-white/60 p-5 shadow-[0_18px_48px_rgba(72,60,96,0.075)] backdrop-blur-xl">
          <h2 className="font-display text-lg font-semibold text-slate-950">Invite teammate</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">Create an invitation for an admin or agent. The invited teammate should sign up with this same email address.</p>
          <label className="mt-5 block text-sm font-medium text-slate-700" htmlFor="invite-email">Email</label>
          <input id="invite-email" value={email} onChange={(event) => setEmail(event.target.value)} required type="email" className="mt-2 w-full rounded-md border border-[#ddd7e6] bg-white/70 px-3 py-2 text-sm outline-none focus:border-[#756f9f]" />
          <label className="mt-4 block text-sm font-medium text-slate-700" htmlFor="invite-role">Role</label>
          <select id="invite-role" value={role} onChange={(event) => setRole(event.target.value)} className="mt-2 w-full rounded-md border border-[#ddd7e6] bg-white/70 px-3 py-2 text-sm">
            <option value="agent">Agent</option>
            <option value="admin">Admin</option>
          </select>
          <Button type="submit" variant="primary" className="mt-5 w-full">Create invitation</Button>
          {message ? (
            <div className="mt-4 rounded-md border border-white/60 bg-white/50 p-3 text-sm leading-6 text-slate-600">
              <p>{message}</p>
              {manualInviteUrl ? (
                <div className="mt-3 grid gap-2">
                  <input readOnly value={manualInviteUrl} className="w-full rounded-md border border-[#ddd7e6] bg-white/70 px-3 py-2 text-xs text-slate-600" aria-label="Manual invite link" />
                  <Button type="button" variant="outline" onClick={() => void navigator.clipboard.writeText(manualInviteUrl)}>
                    Copy invite link
                  </Button>
                </div>
              ) : null}
            </div>
          ) : null}
        </form>
        <section className="rounded-lg border border-white/60 bg-white/60 p-5 shadow-[0_18px_48px_rgba(72,60,96,0.075)] backdrop-blur-xl">
          <h3 className="font-display text-base font-semibold text-slate-950">How team invites work right now</h3>
          <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm leading-6 text-slate-600">
            <li>Owner/admin creates an invitation record for an email and role.</li>
            <li>The teammate signs up or signs in using that same email address.</li>
            <li>If SMTP email delivery is configured, Sift sends a real invite email automatically.</li>
          </ol>
        </section>
      </div>
      <ConfirmTeamActionDialog action={pendingAction} saving={savingAction} onCancel={() => setPendingAction(null)} onConfirm={() => void confirmPendingAction()} />
    </div>
  );
}

function ConfirmTeamActionDialog({ action, saving, onCancel, onConfirm }: { action: PendingAction; saving: boolean; onCancel: () => void; onConfirm: () => void }) {
  if (!action) return null;
  const isRoleChange = action.type === "role";
  const title = isRoleChange ? "Confirm role change" : "Remove teammate?";
  const description = isRoleChange
    ? `Change ${action.member.email} from ${roleLabels[action.member.role] ?? action.member.role} to ${roleLabels[action.nextRole] ?? action.nextRole}? Their access will update immediately.`
    : `Remove ${action.member.email} from this workspace? They will lose access to this organization until invited again.`;
  const confirmLabel = isRoleChange ? `Make ${roleLabels[action.nextRole] ?? action.nextRole}` : "Remove teammate";

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/20 px-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="team-confirm-title">
      <div className="w-full max-w-md rounded-xl border border-white/70 bg-white/90 p-5 shadow-[0_24px_80px_rgba(72,60,96,0.18)] backdrop-blur-xl">
        <h3 id="team-confirm-title" className="font-display text-lg font-semibold text-slate-950">{title}</h3>
        <p className="mt-3 text-sm leading-6 text-slate-600">{description}</p>
        <div className="mt-5 flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onCancel} disabled={saving}>Cancel</Button>
          <Button type="button" variant={isRoleChange ? "primary" : "danger"} onClick={onConfirm} disabled={saving}>
            {saving ? "Saving..." : confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}

function TeamMetric({ label, value }: { label: string; value: number }) {
  return <article className="rounded-lg border border-white/60 bg-white/60 p-4 shadow-[0_18px_48px_rgba(72,60,96,0.075)] backdrop-blur-xl"><span className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">{label}</span><strong className="mt-2 block font-display text-2xl text-slate-950">{value}</strong></article>;
}
function MemberCount({ label, value }: { label: string; value: number }) {
  return <span className="rounded-md border border-white/60 bg-white/45 px-2 py-1"><span className="block font-semibold text-slate-800">{value}</span><span>{label}</span></span>;
}
