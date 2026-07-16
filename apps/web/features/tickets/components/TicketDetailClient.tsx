"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";

import { Button } from "@/components/ui/Button";
import { UrgencyBadge } from "@/components/ui/Badges";
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
  getWorkspaceSettings,
  getTicket,
  getTicketAttachmentDownloadUrl,
  getTicketRoutingExecutions,
  getTicketEvents,
  getTicketTriageResults,
  insertResponseTemplate,
  rejectReplySuggestion,
  releaseCollaborationLock,
  runTicketTriage,
  TicketApiError,
  sendGmailReplyFromSuggestion,
  storeTicketAttachment,
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
  RoutingRuleExecution,
  Ticket,
  TicketEvent,
} from "../types";

function displayStatus(status: string) {
  return status.replaceAll("_", " ");
}

function formatAttachmentSize(sizeBytes: number | null) {
  if (sizeBytes === null) return "Unknown size";
  if (sizeBytes < 1024) return `${sizeBytes} B`;
  const units = ["KB", "MB", "GB"];
  let size = sizeBytes / 1024;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  return `${size.toFixed(size >= 10 ? 0 : 1)} ${units[unitIndex]}`;
}

function attachmentStatusClass(status: string) {
  if (status.startsWith("blocked")) return "border-red-200 bg-red-50 text-red-700";
  if (status === "stored" || status === "clean" || status === "metadata_only") return "border-teal-200 bg-teal-50 text-teal-700";
  return "border-slate-200 bg-slate-50 text-slate-600";
}

function replySubject(subject: string) {
  return subject.toLowerCase().startsWith("re:") ? subject : `Re: ${subject}`;
}

function displayAttachmentStatus(status: string) {
  return status.replaceAll("_", " ");
}

function formatRetryAfter(seconds: number | null) {
  if (!seconds || seconds <= 0) return null;
  if (seconds < 60) return `${seconds} seconds`;
  const minutes = Math.ceil(seconds / 60);
  return `${minutes} minute${minutes === 1 ? "" : "s"}`;
}

function triageStatusTone(status?: string | null) {
  if (status === "triaged") return "border-teal-200 bg-teal-50 text-teal-700";
  if (status === "queued" || status === "triaging") return "border-sky-200 bg-sky-50 text-sky-700";
  if (status === "triage_failed") return "border-amber-200 bg-amber-50 text-amber-800";
  if (status === "not_queued") return "border-slate-200 bg-slate-50 text-slate-600";
  return "border-slate-200 bg-slate-50 text-slate-600";
}

function triageStatusLabel(status?: string | null) {
  if (!status) return "Not queued";
  if (status === "triage_failed") return "Needs retry";
  return status.replaceAll("_", " ");
}

function formatDue(value?: string | null) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function slaExplanation(ticket: Ticket) {
  const reviewDue = formatDue(ticket.first_review_due_at);
  const resolutionDue = formatDue(ticket.resolution_due_at);
  if (ticket.sla_status === "paused") return "Paused because the ticket is pending, resolved, or spam.";
  if (ticket.sla_status === "breached") return reviewDue ? `First review was due ${reviewDue}.` : resolutionDue ? `Resolution was due ${resolutionDue}.` : "SLA target has passed.";
  if (ticket.sla_status === "warning") return reviewDue ? `First review due soon: ${reviewDue}.` : resolutionDue ? `Resolution due soon: ${resolutionDue}.` : "SLA target is close.";
  return reviewDue ? `First review due ${reviewDue}.` : resolutionDue ? `Resolution due ${resolutionDue}.` : "No SLA target set.";
}

function workflowStatus(ticket: Ticket, latestSuggestion?: ReplySuggestion) {
  if (ticket.status === "resolved") {
    return { label: "Resolved", detail: latestSuggestion?.gmail_draft_id ? `Gmail draft exists: ${latestSuggestion.gmail_draft_id}` : null };
  }
  if (ticket.status === "spam") {
    return { label: "Spam", detail: latestSuggestion?.gmail_draft_id ? `Gmail draft exists: ${latestSuggestion.gmail_draft_id}` : null };
  }
  if (latestSuggestion?.status === "approved" && !latestSuggestion.gmail_draft_id) {
    return { label: "Reply approved", detail: "Draft not created yet. Create a Gmail draft when ready." };
  }
  if (latestSuggestion?.status === "draft_created" || latestSuggestion?.gmail_draft_id || ticket.status === "draft_created") {
    return { label: "Draft created", detail: latestSuggestion?.gmail_draft_id ? `Gmail draft ${latestSuggestion.gmail_draft_id}` : "Gmail draft created." };
  }
  return { label: displayStatus(ticket.status), detail: null as string | null };
}

function latestTriageChange(events: TicketEvent[]) {
  const event = [...events].reverse().find((item) => item.event_type === "ticket.ai_triaged" && item.event_metadata?.changed === true);
  if (!event) return null;
  const previousPriority = String(event.event_metadata.previous_priority ?? "unknown").replaceAll("_", " ");
  const newPriority = String(event.event_metadata.new_priority ?? "unknown").replaceAll("_", " ");
  const previousCategory = String(event.event_metadata.previous_category ?? "unknown").replaceAll("_", " ");
  const newCategory = String(event.event_metadata.new_category ?? "unknown").replaceAll("_", " ");
  const adjustments = Array.isArray(event.event_metadata.policy_adjustments) ? event.event_metadata.policy_adjustments.join("; ") : null;
  return { previousPriority, newPriority, previousCategory, newCategory, adjustments };
}
function triageFailureMessage(ticket: Ticket) {
  if (ticket.triage_status !== "triage_failed") return null;
  const error = ticket.triage_error_message ?? "AI triage did not complete.";
  const lower = error.toLowerCase();
  if (lower.includes("quota") || lower.includes("free gemini") || lower.includes("too_many_requests")) {
    return {
      title: "AI paused by Gemini free quota",
      body: "This ticket was imported correctly, but AI classification paused before Gemini returned a result. You can edit the reply manually or retry after the quota window resets.",
      reason: error,
    };
  }
  return {
    title: "AI triage needs a retry",
    body: "This ticket is still safe to handle manually. Regenerate can retry the classification and draft suggestion.",
    reason: error,
  };
}

export function TicketDetailClient({ ticketId, basePath = "/dashboard/tickets" }: { ticketId: string; basePath?: string }) {
  const supabase = createClient();
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [events, setEvents] = useState<TicketEvent[]>([]);
  const [triageResults, setTriageResults] = useState<AITriageResult[]>([]);
  const [replySuggestions, setReplySuggestions] = useState<ReplySuggestion[]>([]);
  const [templates, setTemplates] = useState<ResponseTemplate[]>([]);
  const [notes, setNotes] = useState<InternalNote[]>([]);
  const [routingExecutions, setRoutingExecutions] = useState<RoutingRuleExecution[]>([]);
  const [noteEdits, setNoteEdits] = useState<Record<string, InternalNoteEdit[]>>({});
  const [noteMentions, setNoteMentions] = useState<Record<string, InternalNoteMention[]>>({});
  const [replyText, setReplyText] = useState("");
  const [templateSearch, setTemplateSearch] = useState("");
  const [noteText, setNoteText] = useState("");
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null);
  const [editingNoteText, setEditingNoteText] = useState("");
  const [activeLock, setActiveLock] = useState<CollaborationLock | null>(null);
  const activeLockRef = useRef<CollaborationLock | null>(null);
  const [lockWarning, setLockWarning] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [triaging, setTriaging] = useState(false);
  const [savingReply, setSavingReply] = useState(false);
  const [approvingReply, setApprovingReply] = useState(false);
  const [rejectingReply, setRejectingReply] = useState(false);
  const [creatingDraft, setCreatingDraft] = useState(false);
  const [sendingReply, setSendingReply] = useState(false);
  const [directSendEnabled, setDirectSendEnabled] = useState(false);
  const [sendConfirmation, setSendConfirmation] = useState("");
  const [savingNote, setSavingNote] = useState(false);
  const [processingAttachmentId, setProcessingAttachmentId] = useState<string | null>(null);

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

      const [loadedEvents, loadedResults, loadedSuggestions, loadedTemplates, loadedNotes, loadedRoutingExecutions, loadedSettings] = await Promise.all([
        getTicketEvents(context.organizationId, ticketId, context.accessToken).catch(() => []),
        getTicketTriageResults(context.organizationId, ticketId, context.accessToken).catch(() => []),
        getReplySuggestions(context.organizationId, ticketId, context.accessToken).catch(() => []),
        getResponseTemplates(context.organizationId, context.accessToken).catch(() => []),
        getInternalNotes(context.organizationId, ticketId, context.accessToken).catch(() => []),
        getTicketRoutingExecutions(context.organizationId, ticketId, context.accessToken).catch(() => []),
        getWorkspaceSettings(context.organizationId, context.accessToken).catch(() => null),
      ]);
      setEvents(loadedEvents);
      setTriageResults(loadedResults);
      setReplySuggestions(loadedSuggestions);
      setTemplates(loadedTemplates);
      setNotes(loadedNotes);
      setRoutingExecutions(loadedRoutingExecutions);
      setDirectSendEnabled(Boolean(loadedSettings?.direct_send_enabled));
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
      setMessage("AI triage completed.");
    } catch (error) {
      if (error instanceof TicketApiError && error.status === 429) {
        const wait = formatRetryAfter(error.retryAfterSeconds);
        setMessage(wait ? `${error.message} Try again in about ${wait}.` : error.message);
      } else {
        setMessage(error instanceof Error ? error.message : "Failed to run AI triage.");
      }
      await loadTicket();
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


  async function handleSendReply() {
    const latestSuggestion = replySuggestions[0];
    const context = await getSessionContext();
    if (!latestSuggestion || !ticket || !context) return;
    setSendingReply(true);
    setMessage(null);
    try {
      const finalBody = latestSuggestion.edited_body ?? latestSuggestion.body;
      const result = await sendGmailReplyFromSuggestion(context.organizationId, latestSuggestion.id, context.accessToken, {
        reply_version: latestSuggestion.reply_version,
        confirm_recipient_email: ticket.customer.email,
        confirm_subject: replySubject(ticket.subject),
        confirm_body: finalBody,
        confirmation_text: "SEND",
      });
      setSendConfirmation("");
      await loadTicket();
      setMessage(result.test_mode ? `Test send recorded: ${result.gmail_message_id}` : `Gmail reply sent: ${result.gmail_message_id}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to send Gmail reply.");
    } finally {
      setSendingReply(false);
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


  async function handleStoreAttachment(attachmentId: string) {
    const context = await getSessionContext();
    if (!context) return;
    setProcessingAttachmentId(attachmentId);
    setMessage(null);
    try {
      await storeTicketAttachment(context.organizationId, ticketId, attachmentId, context.accessToken);
      await loadTicket();
      setMessage("Attachment stored securely.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to store attachment.");
    } finally {
      setProcessingAttachmentId(null);
    }
  }

  async function handleDownloadAttachment(attachmentId: string, filename?: string | null) {
    const context = await getSessionContext();
    if (!context) return;
    setProcessingAttachmentId(attachmentId);
    setMessage(null);
    try {
      const result = await getTicketAttachmentDownloadUrl(context.organizationId, ticketId, attachmentId, context.accessToken);
      const anchor = document.createElement("a");
      anchor.href = result.download_url;
      anchor.download = filename || "attachment";
      anchor.rel = "noopener";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to create attachment download link.");
    } finally {
      setProcessingAttachmentId(null);
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
  const currentWorkflow = ticket ? workflowStatus(ticket, latestSuggestion) : null;
  const currentSlaExplanation = ticket ? slaExplanation(ticket) : null;
  const currentTriageChange = latestTriageChange(events);
  const triageFailedWithoutResult = ticket?.triage_status === "triage_failed" && !latestTriage;
  const displayedCategory = triageFailedWithoutResult ? "Not classified" : ticket?.category.replaceAll("_", " ");
  const displayedReview = triageFailedWithoutResult ? "Not available" : latestTriage?.requires_human_review ? "Required" : "Not flagged";
  const displayedUrgencyBadge = triageFailedWithoutResult ? <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">Not classified</span> : ticket ? <UrgencyBadge priority={ticket.priority} /> : null;
  const canEdit = latestSuggestion?.status === "suggested" || latestSuggestion?.status === "edited";
  const draftCreated = latestSuggestion?.status === "draft_created" || Boolean(latestSuggestion?.gmail_draft_id);
  const canDraft = latestSuggestion?.status === "approved" && !latestSuggestion.gmail_draft_id;
  const directSendReady = latestSuggestion?.status === "approved" || latestSuggestion?.status === "draft_created";
  const sendReplyBody = latestSuggestion ? latestSuggestion.edited_body ?? latestSuggestion.body : "";
  const sendReplySubject = ticket ? replySubject(ticket.subject) : "";
  const canSend = directSendEnabled && directSendReady && sendConfirmation === "SEND";

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
                <div className="flex flex-wrap gap-2">
                  {displayedUrgencyBadge}
                  <span className="inline-flex flex-col rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-medium capitalize text-slate-600">
                    <span>{currentWorkflow?.label}</span>
                    {currentWorkflow?.detail ? <span className="mt-0.5 font-normal normal-case text-slate-500">{currentWorkflow.detail}</span> : null}
                  </span>
                  <span className="inline-flex max-w-64 flex-col rounded-md bg-slate-100 px-2 py-1 text-xs font-medium capitalize text-slate-600" title={currentSlaExplanation ?? undefined}>
                    <span>SLA {ticket.sla_status.replaceAll("_", " ")}</span>
                    {currentSlaExplanation ? <span className="mt-0.5 truncate font-normal normal-case text-slate-500">{currentSlaExplanation}</span> : null}
                  </span>
                </div>
              </div>
            </div>
            <div className="max-h-[calc(100vh-280px)] overflow-y-auto p-5">
              <div className="rounded-lg bg-slate-50 p-5 text-sm leading-7 text-slate-700">
                <p className="whitespace-pre-wrap">{ticket.message_text}</p>
              </div>
              {(ticket.attachments ?? []).length ? (
                <div className="mt-4 rounded-lg border border-slate-200 bg-white p-4">
                  <div className="flex items-center justify-between gap-3">
                    <h3 className="font-display text-base font-semibold text-slate-900">Email attachments</h3>
                    <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">Metadata only</span>
                  </div>
                  <div className="mt-3 space-y-2">
                    {(ticket.attachments ?? []).map((attachment) => (
                      <div key={attachment.id} className="rounded-md border border-slate-200 p-3 text-sm">
                        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                          <div className="min-w-0">
                            <p className="truncate font-medium text-slate-800">{attachment.filename ?? "Unnamed attachment"}</p>
                            <p className="mt-1 text-xs text-slate-500">
                              {[attachment.mime_type ?? "unknown type", formatAttachmentSize(attachment.size_bytes), attachment.is_inline ? "inline" : "attachment"].join(" / ")}
                            </p>
                          </div>
                          <div className="flex flex-wrap gap-1">
                            <span className={`rounded-md border px-2 py-1 text-xs font-medium capitalize ${attachmentStatusClass(attachment.policy_status)}`}>{displayAttachmentStatus(attachment.policy_status)}</span>
                            <span className={`rounded-md border px-2 py-1 text-xs font-medium capitalize ${attachmentStatusClass(attachment.storage_status)}`}>{displayAttachmentStatus(attachment.storage_status)}</span>
                            <span className={`rounded-md border px-2 py-1 text-xs font-medium capitalize ${attachmentStatusClass(attachment.scan_status)}`}>{displayAttachmentStatus(attachment.scan_status)}</span>
                            {attachment.storage_status === "stored" ? (
                              <Button type="button" variant="ghost" onClick={() => void handleDownloadAttachment(attachment.id, attachment.filename)} disabled={processingAttachmentId === attachment.id}>
                                {processingAttachmentId === attachment.id ? "Opening..." : "Download"}
                              </Button>
                            ) : !attachment.policy_status.startsWith("blocked") ? (
                              <Button type="button" variant="ghost" onClick={() => void handleStoreAttachment(attachment.id)} disabled={processingAttachmentId === attachment.id}>
                                {processingAttachmentId === attachment.id ? "Storing..." : "Store file"}
                              </Button>
                            ) : null}
                          </div>
                        </div>
                        {attachment.notes ? <p className="mt-2 text-xs text-slate-500">{attachment.notes}</p> : null}
                      </div>
                    ))}
                  </div>
                  <p className="mt-3 text-xs text-slate-500">Files stay private. Stored attachments open through short-lived signed URLs after policy and workspace checks.</p>
                </div>
              ) : null}
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
                <div><dt className="text-slate-500">Urgency</dt><dd className="mt-1">{displayedUrgencyBadge}</dd></div>
                <div><dt className="text-slate-500">Category</dt><dd className="mt-1 font-medium capitalize">{displayedCategory}</dd></div>
                <div><dt className="text-slate-500">Triage</dt><dd className="mt-1"><span className={`inline-flex rounded-md border px-2 py-1 text-xs font-medium capitalize ${triageStatusTone(ticket.triage_status)}`}>{triageStatusLabel(ticket.triage_status)}</span></dd></div>
                <div><dt className="text-slate-500">Review</dt><dd className="mt-1 font-medium">{displayedReview}</dd></div>
                <div><dt className="text-slate-500">First review due</dt><dd className="mt-1 font-medium">{ticket.first_review_due_at ? new Date(ticket.first_review_due_at).toLocaleString() : "Not set"}</dd></div>
                <div><dt className="text-slate-500">Resolution due</dt><dd className="mt-1 font-medium">{ticket.resolution_due_at ? new Date(ticket.resolution_due_at).toLocaleString() : "Not set"}</dd></div>
              </dl>
              {triageFailedWithoutResult ? (
                <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                  AI triage did not complete. The default urgency/category values are hidden because they are not an AI classification.
                  {ticket.triage_error_message ? <span className="mt-2 block">Reason: {ticket.triage_error_message}</span> : null}
                </div>
              ) : null}
              {currentTriageChange ? (
                <div className="mt-4 rounded-md border border-sky-200 bg-sky-50 p-3 text-sm text-sky-800">
                  <p className="font-medium">Regenerated triage changed classification</p>
                  <p className="mt-1 text-xs leading-5">
                    Urgency changed from {currentTriageChange.previousPriority} to {currentTriageChange.newPriority}; category changed from {currentTriageChange.previousCategory} to {currentTriageChange.newCategory}.
                  </p>
                  {currentTriageChange.adjustments ? <p className="mt-1 text-xs leading-5">Guardrails: {currentTriageChange.adjustments}</p> : null}
                </div>
              ) : null}
              {latestTriage ? (
                <div className="mt-4 border-t border-slate-200 pt-4 text-sm">
                  <p className="font-medium">Reasoning</p>
                  <p className="mt-1 text-slate-600">{latestTriage.summary}</p>
                  <p className="mt-3 font-medium">Suggested action</p>
                  <p className="mt-1 text-slate-600">{latestTriage.suggested_action}</p>
                  <p className="mt-3 font-medium">Knowledge sources</p>
                  {latestTriage.knowledge_sources?.length ? (
                    <div className="mt-2 space-y-2">
                      {latestTriage.knowledge_sources.map((source) => (
                        <div key={source.id} className="rounded-md border border-slate-200 p-3">
                          <div className="flex items-center justify-between gap-2">
                            <p className="font-medium text-slate-800">{source.title}</p>
                            <span className="font-mono text-xs text-slate-500">score {source.score}</span>
                          </div>
                          <p className="mt-1 text-slate-600">{source.excerpt}</p>
                          {source.matched_terms.length ? <p className="mt-2 text-xs text-slate-500">Matched {source.matched_terms.join(", ")}</p> : null}
                        </div>
                      ))}
                    </div>
                  ) : <p className="mt-1 text-slate-500">No workspace source influenced this result.</p>}
                </div>
              ) : <p className="mt-4 text-sm text-slate-500">No AI triage result yet.</p>}
            </div>

            <div className="rounded-lg border border-slate-200 bg-white p-5">
              <h2 className="font-display text-lg font-semibold">Routing history</h2>
              <div className="mt-3 space-y-2">
                {routingExecutions.length === 0 ? <p className="text-sm text-slate-500">No routing rules have run on this ticket.</p> : routingExecutions.map((execution) => (
                  <div key={execution.id} className="rounded-md border border-slate-200 p-3 text-sm">
                    <div className="flex items-center justify-between gap-2">
                      <span className={execution.matched ? "font-medium text-teal-700" : "font-medium text-slate-500"}>{execution.matched ? "Matched" : "Skipped"}</span>
                      <span className="font-mono text-xs text-slate-500">{new Date(execution.created_at).toLocaleString()}</span>
                    </div>
                    <p className="mt-2 text-xs text-slate-500">{Object.keys(execution.actions_applied).length ? JSON.stringify(execution.actions_applied) : "No actions applied"}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-lg border border-slate-200 bg-white p-5">
              <h2 className="font-display text-lg font-semibold">Suggested reply</h2>
              {!latestSuggestion ? <p className="mt-3 text-sm text-slate-500">Run triage or insert a template to create an editable reply.</p> : (
                <div className="mt-4 space-y-4">
                  <div className="flex items-center justify-between rounded-md bg-slate-50 p-3 text-sm">
                    <span className="capitalize text-slate-600">{displayStatus(latestSuggestion.status)}</span>
                    <span className="font-mono text-xs text-slate-500">v{latestSuggestion.reply_version} / {latestSuggestion.created_by}</span>
                  </div>
                  {draftCreated ? (
                    <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="font-medium">Gmail draft created</p>
                        {latestSuggestion.gmail_draft_id ? <span className="font-mono text-xs">{latestSuggestion.gmail_draft_id}</span> : null}
                      </div>
                      <p className="mt-1 text-xs leading-5">This approved reply already has a Gmail draft. Open Gmail drafts if you want to review it in Gmail before sending manually.</p>
                      <a href="https://mail.google.com/mail/u/0/#drafts" target="_blank" rel="noreferrer" className="mt-2 inline-flex text-xs font-medium underline">Open Gmail drafts</a>
                    </div>
                  ) : latestSuggestion.status === "approved" ? (
                    <div className="rounded-md border border-sky-200 bg-sky-50 p-3 text-sm text-sky-800">
                      <p className="font-medium">Approved reply ready</p>
                      <p className="mt-1 text-xs leading-5">Create a Gmail draft when you are ready. The draft will stay in Gmail for final review.</p>
                    </div>
                  ) : null}
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
                    <Button type="button" variant="primary" onClick={() => void handleCreateDraft()} disabled={!canDraft || creatingDraft}>{draftCreated ? "Draft created" : creatingDraft ? "Creating..." : "Create draft"}</Button>
                    <div className="sm:col-span-2 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="font-medium text-slate-800">Direct send</p>
                        <span className={`rounded-md border px-2 py-1 text-xs font-medium ${directSendEnabled ? "border-amber-200 bg-amber-50 text-amber-800" : "border-slate-200 bg-white text-slate-500"}`}>
                          {directSendEnabled ? "Final confirmation required" : "Off"}
                        </span>
                      </div>
                      <p className="mt-2 text-xs leading-5 text-slate-500">Before sending, Sift verifies this exact recipient, subject, approved version, and reply body.</p>
                      <dl className="mt-3 grid gap-2 rounded-md border border-slate-200 bg-white p-3 text-xs sm:grid-cols-2">
                        <div><dt className="text-slate-500">To</dt><dd className="mt-1 break-all font-medium text-slate-800">{ticket.customer.email}</dd></div>
                        <div><dt className="text-slate-500">Subject</dt><dd className="mt-1 break-words font-medium text-slate-800">{sendReplySubject}</dd></div>
                        <div><dt className="text-slate-500">Approved version</dt><dd className="mt-1 font-medium text-slate-800">v{latestSuggestion.reply_version}</dd></div>
                        <div><dt className="text-slate-500">Status</dt><dd className="mt-1 font-medium capitalize text-slate-800">{displayStatus(latestSuggestion.status)}</dd></div>
                      </dl>
                      <div className="mt-3 max-h-36 overflow-y-auto whitespace-pre-wrap rounded-md border border-slate-200 bg-white p-3 text-xs leading-5 text-slate-700">{sendReplyBody}</div>
                      <input value={sendConfirmation} onChange={(event) => setSendConfirmation(event.target.value)} disabled={!directSendEnabled || !directSendReady} placeholder="Type SEND" className="mt-3 w-full rounded-md border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100" />
                      <Button type="button" variant="danger" className="mt-2" onClick={() => void handleSendReply()} disabled={!canSend || sendingReply}>{sendingReply ? "Sending..." : "Send reply"}</Button>
                      {!directSendEnabled ? <p className="mt-2 text-xs text-slate-500">Direct send is off in Settings - Readiness.</p> : null}
                      {directSendEnabled && !directSendReady ? <p className="mt-2 text-xs text-slate-500">Approve the reply before direct send is available.</p> : null}
                    </div>
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

