"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { Button } from "@/components/ui/Button";
import { StatusBadge, UrgencyBadge } from "@/components/ui/Badges";
import { getStoredOrganizationId, setStoredOrganizationId } from "@/features/organizations/components/OrganizationManager";
import { createClient } from "@/lib/supabase/client";
import { getMe } from "@/lib/api-client";
import {
  acquireCollaborationLock,
  approveReplySuggestion,
  createGmailDraftFromSuggestion,
  createInternalNote,
  getInternalNoteEdits,
  getInternalNoteMentions,
  getInternalNotes,
  getReplySuggestions,
  getResponseTemplates,
  getTicket,
  getTicketEvents,
  getTicketTriageResults,
  insertResponseTemplate,
  rejectReplySuggestion,
  releaseCollaborationLock,
  runTicketTriage,
  updateInternalNote,
  updateReplySuggestion,
} from "../api";
import type {
  AITriageResult,
  CollaborationLock,
  InternalNote,
  InternalNoteEdit,
  InternalNoteMention,
  ReplySuggestion,
  ResponseTemplate,
  Ticket,
  TicketEvent,
} from "../types";

function displayStatus(status: string) {
  return status.replaceAll("_", " ");
}

export function TicketDetailClient({ ticketId, basePath = "/dashboard/tickets" }: { ticketId: string; basePath?: string }) {
  const supabase = createClient();
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [events, setEvents] = useState<TicketEvent[]>([]);
  const [triageResults, setTriageResults] = useState<AITriageResult[]>([]);
  const [replySuggestions, setReplySuggestions] = useState<ReplySuggestion[]>([]);
  const [templates, setTemplates] = useState<ResponseTemplate[]>([]);
  const [notes, setNotes] = useState<InternalNote[]>([]);
  const [noteEdits, setNoteEdits] = useState<Record<string, InternalNoteEdit[]>>({});
  const [noteMentions, setNoteMentions] = useState<Record<string, InternalNoteMention[]>>({});
  const [replyText, setReplyText] = useState("");
  const [templateSearch, setTemplateSearch] = useState("");
  const [noteText, setNoteText] = useState("");
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null);
  const [editingNoteText, setEditingNoteText] = useState("");
  const [activeLock, setActiveLock] = useState<CollaborationLock | null>(null);
  const [lockWarning, setLockWarning] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [triaging, setTriaging] = useState(false);
  const [savingReply, setSavingReply] = useState(false);
  const [approvingReply, setApprovingReply] = useState(false);
  const [rejectingReply, setRejectingReply] = useState(false);
  const [creatingDraft, setCreatingDraft] = useState(false);
  const [savingNote, setSavingNote] = useState(false);

  async function getSessionContext() {
    const { data } = await supabase.auth.getSession();
    const accessToken = data.session?.access_token;
    if (!accessToken) return null;

    const storedOrganizationId = getStoredOrganizationId();
    if (storedOrganizationId) return { organizationId: storedOrganizationId, accessToken };

    const me = await getMe(accessToken);
    const selected = me.organizations[0] ?? null;
    if (!selected) return null;

    setStoredOrganizationId(selected.id);
    return { organizationId: selected.id, accessToken };
  }

  async function loadTicket() {
    setLoading(true);
    setMessage(null);
    const context = await getSessionContext();
    if (!context) {
      setMessage("Create or select a workspace before viewing conversations.");
      setLoading(false);
      return;
    }

    try {
      const loadedTicket = await getTicket(context.organizationId, ticketId, context.accessToken);
      setTicket(loadedTicket);

      const [loadedEvents, loadedResults, loadedSuggestions, loadedTemplates, loadedNotes] = await Promise.all([
        getTicketEvents(context.organizationId, ticketId, context.accessToken).catch(() => []),
        getTicketTriageResults(context.organizationId, ticketId, context.accessToken).catch(() => []),
        getReplySuggestions(context.organizationId, ticketId, context.accessToken).catch(() => []),
        getResponseTemplates(context.organizationId, context.accessToken).catch(() => []),
        getInternalNotes(context.organizationId, ticketId, context.accessToken).catch(() => []),
      ]);
      setEvents(loadedEvents);
      setTriageResults(loadedResults);
      setReplySuggestions(loadedSuggestions);
      setTemplates(loadedTemplates);
      setNotes(loadedNotes);
      const latestSuggestion = loadedSuggestions[0];
      setReplyText(latestSuggestion?.edited_body ?? latestSuggestion?.body ?? "");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to load ticket.");
    } finally {
      setLoading(false);
    }
  }

  async function loadTemplates(search = templateSearch) {
    const context = await getSessionContext();
    if (!context) return;
    try {
      setTemplates(await getResponseTemplates(context.organizationId, context.accessToken, search));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to load templates.");
    }
  }

  async function handleRunTriage() {
    const context = await getSessionContext();
    if (!context) return;
    setTriaging(true);
    setMessage(null);
    try {
      await runTicketTriage(context.organizationId, ticketId, context.accessToken);
      await loadTicket();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to run AI triage.");
    } finally {
      setTriaging(false);
    }
  }

  async function ensureEditLock() {
    const latestSuggestion = replySuggestions[0];
    const context = await getSessionContext();
    if (!latestSuggestion || !context || activeLock) return true;
    try {
      const lock = await acquireCollaborationLock(context.organizationId, context.accessToken, {
        ticket_id: ticketId,
        resource_type: "reply_suggestion",
        resource_id: latestSuggestion.id,
        ttl_seconds: 180,
      });
      setActiveLock(lock);
      setLockWarning(null);
      return true;
    } catch (error) {
      setLockWarning(error instanceof Error ? error.message : "Another agent is editing this reply.");
      return false;
    }
  }

  async function releaseEditLock() {
    const context = await getSessionContext();
    if (!context || !activeLock) return;
    try {
      await releaseCollaborationLock(context.organizationId, context.accessToken, activeLock.id);
      setActiveLock(null);
    } catch {
      setActiveLock(null);
    }
  }

  async function handleSaveReply() {
    const latestSuggestion = replySuggestions[0];
    const context = await getSessionContext();
    if (!latestSuggestion || !context) return;
    if (!(await ensureEditLock())) return;
    setSavingReply(true);
    setMessage(null);
    try {
      await updateReplySuggestion(context.organizationId, latestSuggestion.id, context.accessToken, replyText);
      await releaseEditLock();
      await loadTicket();
      setMessage("Reply edits saved.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to save reply.");
    } finally {
      setSavingReply(false);
    }
  }

  async function handleApproveReply() {
    const latestSuggestion = replySuggestions[0];
    const context = await getSessionContext();
    if (!latestSuggestion || !context) return;
    if (!(await ensureEditLock())) return;
    setApprovingReply(true);
    setMessage(null);
    try {
      if ((latestSuggestion.edited_body ?? latestSuggestion.body) !== replyText) {
        await updateReplySuggestion(context.organizationId, latestSuggestion.id, context.accessToken, replyText);
      }
      await approveReplySuggestion(context.organizationId, latestSuggestion.id, context.accessToken);
      await releaseEditLock();
      await loadTicket();
      setMessage("Reply approved. Draft creation is now available.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to approve reply.");
    } finally {
      setApprovingReply(false);
    }
  }

  async function handleRejectReply() {
    const latestSuggestion = replySuggestions[0];
    const context = await getSessionContext();
    if (!latestSuggestion || !context) return;
    setRejectingReply(true);
    setMessage(null);
    try {
      await rejectReplySuggestion(context.organizationId, latestSuggestion.id, context.accessToken);
      await releaseEditLock();
      await loadTicket();
      setMessage("Reply suggestion rejected.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to reject reply.");
    } finally {
      setRejectingReply(false);
    }
  }

  async function handleCreateDraft() {
    const latestSuggestion = replySuggestions[0];
    const context = await getSessionContext();
    if (!latestSuggestion || !context) return;
    setCreatingDraft(true);
    setMessage(null);
    try {
      const result = await createGmailDraftFromSuggestion(context.organizationId, latestSuggestion.id, context.accessToken);
      await loadTicket();
      setMessage(`Gmail draft created: ${result.gmail_draft_id}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to create Gmail draft.");
    } finally {
      setCreatingDraft(false);
    }
  }

  async function handleInsertTemplate(templateId: string) {
    const context = await getSessionContext();
    if (!context) return;
    setMessage(null);
    try {
      await insertResponseTemplate(context.organizationId, context.accessToken, templateId, ticketId);
      await loadTicket();
      setMessage("Template inserted as an editable reply suggestion.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to insert template.");
    }
  }

  async function handleCreateNote() {
    const context = await getSessionContext();
    if (!context || !noteText.trim()) return;
    setSavingNote(true);
    setMessage(null);
    try {
      await createInternalNote(context.organizationId, ticketId, context.accessToken, noteText.trim());
      setNoteText("");
      setNotes(await getInternalNotes(context.organizationId, ticketId, context.accessToken));
      setMessage("Internal note added.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to add note.");
    } finally {
      setSavingNote(false);
    }
  }

  async function handleUpdateNote(noteId: string) {
    const context = await getSessionContext();
    if (!context || !editingNoteText.trim()) return;
    setSavingNote(true);
    try {
      await updateInternalNote(context.organizationId, noteId, context.accessToken, editingNoteText.trim());
      setEditingNoteId(null);
      setEditingNoteText("");
      setNotes(await getInternalNotes(context.organizationId, ticketId, context.accessToken));
      setMessage("Internal note updated.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to update note.");
    } finally {
      setSavingNote(false);
    }
  }

  async function toggleNoteEdits(noteId: string) {
    if (noteEdits[noteId]) {
      setNoteEdits((current) => {
        const next = { ...current };
        delete next[noteId];
        return next;
      });
      return;
    }
    const context = await getSessionContext();
    if (!context) return;
    try {
      const edits = await getInternalNoteEdits(context.organizationId, noteId, context.accessToken);
      setNoteEdits((current) => ({ ...current, [noteId]: edits }));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to load note history.");
    }
  }
  async function toggleNoteMentions(noteId: string) {
    if (noteMentions[noteId]) {
      setNoteMentions((current) => {
        const next = { ...current };
        delete next[noteId];
        return next;
      });
      return;
    }
    const context = await getSessionContext();
    if (!context) return;
    try {
      const mentions = await getInternalNoteMentions(context.organizationId, noteId, context.accessToken);
      setNoteMentions((current) => ({ ...current, [noteId]: mentions }));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to load note mentions.");
    }
  }
  useEffect(() => {
    void loadTicket();
    return () => {
      void releaseEditLock();
    };
  }, [ticketId]);

  const latestTriage = triageResults[0];
  const latestSuggestion = replySuggestions[0];
  const canEdit = latestSuggestion?.status === "suggested" || latestSuggestion?.status === "edited";
  const canDraft = latestSuggestion?.status === "approved";

  if (loading) return <p className="rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-600">Loading ticket...</p>;

  return (
    <section className="space-y-5">
      <Link href={basePath} className="text-sm font-medium text-slate-600 hover:text-slate-900">Back to queue</Link>
      {message ? <p className="rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-600">{message}</p> : null}
      {lockWarning ? <p className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">{lockWarning}</p> : null}

      {ticket ? (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_420px]">
          <article className="min-h-[calc(100vh-160px)] rounded-lg border border-slate-200 bg-white">
            <div className="border-b border-slate-200 p-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="font-mono text-xs text-slate-500">{ticket.id}</p>
                  <h2 className="mt-2 font-display text-2xl font-semibold tracking-tight text-slate-900">{ticket.subject}</h2>
                  <p className="mt-2 text-sm text-slate-500">From {ticket.customer.name ?? ticket.customer.email} - {new Date(ticket.received_at).toLocaleString()}</p>
                </div>
                <div className="flex flex-wrap gap-2"><UrgencyBadge priority={ticket.priority} /><StatusBadge status={ticket.status} /></div>
              </div>
            </div>
            <div className="max-h-[calc(100vh-280px)] overflow-y-auto p-5">
              <div className="rounded-lg bg-slate-50 p-5 text-sm leading-7 text-slate-700">
                <p className="whitespace-pre-wrap">{ticket.message_text}</p>
              </div>
              <div className="mt-6">
                <h3 className="font-display text-lg font-semibold">Timeline</h3>
                <div className="mt-3 divide-y divide-slate-100 rounded-lg border border-slate-200">
                  {events.map((event) => (
                    <div key={event.id} className="grid gap-2 p-3 text-sm sm:grid-cols-[1fr_auto]">
                      <span className="font-medium text-slate-700">{event.event_type.replaceAll("_", " ")}</span>
                      <span className="font-mono text-xs text-slate-500">{new Date(event.created_at).toLocaleString()}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </article>

          <aside className="space-y-4 lg:sticky lg:top-28 lg:self-start">
            <div className="rounded-lg border border-slate-200 bg-white p-5">
              <div className="flex items-center justify-between gap-3">
                <h2 className="font-display text-lg font-semibold">AI classification</h2>
                <Button type="button" variant="outline" onClick={() => void handleRunTriage()} disabled={triaging}>{triaging ? "Running..." : "Regenerate"}</Button>
              </div>
              <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                <div><dt className="text-slate-500">Urgency</dt><dd className="mt-1"><UrgencyBadge priority={ticket.priority} /></dd></div>
                <div><dt className="text-slate-500">Category</dt><dd className="mt-1 font-medium capitalize">{ticket.category.replaceAll("_", " ")}</dd></div>
                <div><dt className="text-slate-500">Triage</dt><dd className="mt-1 font-medium capitalize">{ticket.triage_status.replaceAll("_", " ")}</dd></div>
                <div><dt className="text-slate-500">Review</dt><dd className="mt-1 font-medium">{latestTriage?.requires_human_review ? "Required" : "Not flagged"}</dd></div>
              </dl>
              {latestTriage ? (
                <div className="mt-4 border-t border-slate-200 pt-4 text-sm">
                  <p className="font-medium">Reasoning</p>
                  <p className="mt-1 text-slate-600">{latestTriage.summary}</p>
                  <p className="mt-3 font-medium">Suggested action</p>
                  <p className="mt-1 text-slate-600">{latestTriage.suggested_action}</p>
                </div>
              ) : <p className="mt-4 text-sm text-slate-500">No AI triage result yet.</p>}
            </div>

            <div className="rounded-lg border border-slate-200 bg-white p-5">
              <h2 className="font-display text-lg font-semibold">Suggested reply</h2>
              {!latestSuggestion ? <p className="mt-3 text-sm text-slate-500">Run triage or insert a template to create an editable reply.</p> : (
                <div className="mt-4 space-y-4">
                  <div className="flex items-center justify-between rounded-md bg-slate-50 p-3 text-sm">
                    <span className="capitalize text-slate-600">{displayStatus(latestSuggestion.status)}</span>
                    <span className="font-mono text-xs text-slate-500">v{latestSuggestion.reply_version} / {latestSuggestion.created_by}</span>
                  </div>
                  <textarea
                    value={replyText}
                    onChange={(event) => setReplyText(event.target.value)}
                    onFocus={() => void ensureEditLock()}
                    disabled={!canEdit}
                    rows={12}
                    className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm leading-6 outline-none focus:border-slate-900 disabled:bg-slate-50"
                  />
                  <div className="grid gap-2 sm:grid-cols-2">
                    <Button type="button" variant="outline" onClick={() => void handleSaveReply()} disabled={!canEdit || savingReply}>{savingReply ? "Saving..." : "Save"}</Button>
                    <Button type="button" variant="primary" onClick={() => void handleApproveReply()} disabled={!canEdit || approvingReply}>{approvingReply ? "Approving..." : "Approve"}</Button>
                    <Button type="button" variant="danger" onClick={() => void handleRejectReply()} disabled={!canEdit || rejectingReply}>{rejectingReply ? "Rejecting..." : "Reject"}</Button>
                    <Button type="button" variant="primary" onClick={() => void handleCreateDraft()} disabled={!canDraft || creatingDraft}>{creatingDraft ? "Creating..." : "Create draft"}</Button>
                  </div>
                </div>
              )}
            </div>

            <div className="rounded-lg border border-slate-200 bg-white p-5">
              <h2 className="font-display text-lg font-semibold">Response templates</h2>
              <div className="mt-3 flex gap-2">
                <input value={templateSearch} onChange={(event) => setTemplateSearch(event.target.value)} placeholder="Search templates" className="min-w-0 flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm" />
                <Button type="button" variant="outline" onClick={() => void loadTemplates()}>Search</Button>
              </div>
              <div className="mt-3 max-h-56 space-y-2 overflow-y-auto">
                {templates.map((template) => (
                  <div key={template.id} className="rounded-md border border-slate-200 p-3 text-sm">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-medium text-slate-800">{template.name}</p>
                        <p className="mt-1 line-clamp-2 text-slate-500">{template.body}</p>
                      </div>
                      <Button type="button" variant="ghost" onClick={() => void handleInsertTemplate(template.id)}>Insert</Button>
                    </div>
                  </div>
                ))}
                {templates.length === 0 ? <p className="text-sm text-slate-500">No templates found.</p> : null}
              </div>
            </div>

            <div className="rounded-lg border border-slate-200 bg-white p-5">
              <h2 className="font-display text-lg font-semibold">Internal notes</h2>
              <textarea value={noteText} onChange={(event) => setNoteText(event.target.value)} rows={4} placeholder="Add a private note. Mention teammates by email with @name@example.com." className="mt-3 w-full rounded-md border border-slate-300 px-3 py-2 text-sm leading-6" />
              <Button type="button" className="mt-2" variant="outline" onClick={() => void handleCreateNote()} disabled={savingNote || !noteText.trim()}>{savingNote ? "Saving..." : "Add note"}</Button>
              <div className="mt-4 space-y-3">
                {notes.map((note) => (
                  <div key={note.id} className="rounded-md border border-slate-200 p-3 text-sm">
                    {editingNoteId === note.id ? (
                      <div className="space-y-2">
                        <textarea value={editingNoteText} onChange={(event) => setEditingNoteText(event.target.value)} rows={4} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
                        <div className="flex gap-2">
                          <Button type="button" variant="primary" onClick={() => void handleUpdateNote(note.id)} disabled={savingNote}>Save note</Button>
                          <Button type="button" variant="ghost" onClick={() => setEditingNoteId(null)}>Cancel</Button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <p className="whitespace-pre-wrap text-slate-700">{note.body}</p>
                        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                          <span>v{note.version}</span>
                          <span>{new Date(note.created_at).toLocaleString()}</span>
                          <button type="button" className="font-medium text-slate-700" onClick={() => { setEditingNoteId(note.id); setEditingNoteText(note.body); }}>Edit</button>
                          <button type="button" className="font-medium text-slate-700" onClick={() => void toggleNoteEdits(note.id)}>History</button>
                          <button type="button" className="font-medium text-slate-700" onClick={() => void toggleNoteMentions(note.id)}>Mentions</button>
                        </div>
                        {noteEdits[note.id] ? (
                          <div className="mt-2 rounded-md bg-slate-50 p-2 text-xs text-slate-600">
                            {noteEdits[note.id].length === 0 ? "No edits yet." : noteEdits[note.id].map((edit) => <p key={edit.id}>v{edit.version}: {new Date(edit.created_at).toLocaleString()}</p>)}
                          </div>
                        ) : null}
                        {noteMentions[note.id] ? (
                          <div className="mt-2 rounded-md bg-slate-50 p-2 text-xs text-slate-600">
                            {noteMentions[note.id].length === 0 ? "No tracked mentions." : noteMentions[note.id].map((mention) => <p key={mention.id}>Mentioned user: {mention.mentioned_user_id}</p>)}
                          </div>
                        ) : null}
                      </>
                    )}
                  </div>
                ))}
                {notes.length === 0 ? <p className="text-sm text-slate-500">No internal notes yet.</p> : null}
              </div>
            </div>
          </aside>
        </div>
      ) : null}
    </section>
  );
}
