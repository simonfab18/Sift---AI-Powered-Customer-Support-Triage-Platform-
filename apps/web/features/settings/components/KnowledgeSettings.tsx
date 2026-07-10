"use client";

import { FormEvent, useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import { getStoredOrganizationId } from "@/features/organizations/components/OrganizationManager";
import { createClient } from "@/lib/supabase/client";
import {
  archiveKnowledgeSource,
  createKnowledgeSource,
  getKnowledgeSources,
  updateKnowledgeSource,
} from "@/features/tickets/api";
import type { KnowledgeSource } from "@/features/tickets/types";

const sourceTypes = ["faq", "policy", "product_fact", "escalation", "macro"];

function formatDate(value: string | null) {
  if (!value) return "No date limit";
  return new Date(value).toLocaleDateString();
}

export function KnowledgeSettings() {
  const supabase = createClient();
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [title, setTitle] = useState("");
  const [sourceType, setSourceType] = useState("faq");
  const [body, setBody] = useState("");
  const [effectiveFrom, setEffectiveFrom] = useState("");
  const [effectiveUntil, setEffectiveUntil] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
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

  function resetForm() {
    setEditingId(null);
    setTitle("");
    setSourceType("faq");
    setBody("");
    setEffectiveFrom("");
    setEffectiveUntil("");
  }

  async function loadSources(nextIncludeArchived = includeArchived) {
    setLoading(true);
    setMessage(null);
    const context = await getContext();
    if (!context) {
      setMessage("Select a workspace and sign in before managing knowledge.");
      setLoading(false);
      return;
    }
    try {
      setSources(await getKnowledgeSources(context.organizationId, context.accessToken, nextIncludeArchived));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to load knowledge sources.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadSources();
  }, []);

  function startEdit(source: KnowledgeSource) {
    setEditingId(source.id);
    setTitle(source.title);
    setSourceType(source.source_type);
    setBody(source.body);
    setEffectiveFrom(source.effective_from ? source.effective_from.slice(0, 10) : "");
    setEffectiveUntil(source.effective_until ? source.effective_until.slice(0, 10) : "");
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const context = await getContext();
    if (!context) return;
    if (!title.trim() || !body.trim()) {
      setMessage("Add a title and body before saving.");
      return;
    }
    setSaving(true);
    setMessage(null);
    const payload = {
      title: title.trim(),
      body: body.trim(),
      source_type: sourceType,
      effective_from: effectiveFrom ? new Date(`${effectiveFrom}T00:00:00`).toISOString() : null,
      effective_until: effectiveUntil ? new Date(`${effectiveUntil}T23:59:59`).toISOString() : null,
      source_metadata: {},
    };
    try {
      if (editingId) {
        await updateKnowledgeSource(context.organizationId, context.accessToken, editingId, payload);
        setMessage("Knowledge source updated.");
      } else {
        await createKnowledgeSource(context.organizationId, context.accessToken, payload);
        setMessage("Knowledge source created.");
      }
      resetForm();
      await loadSources();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to save knowledge source.");
    } finally {
      setSaving(false);
    }
  }

  async function handleArchive(sourceId: string) {
    const context = await getContext();
    if (!context) return;
    try {
      await archiveKnowledgeSource(context.organizationId, context.accessToken, sourceId);
      await loadSources();
      setMessage("Knowledge source archived. It will not be used for new AI generation.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to archive knowledge source.");
    }
  }

  async function toggleArchived() {
    const next = !includeArchived;
    setIncludeArchived(next);
    await loadSources(next);
  }

  return (
    <section className="space-y-6">
      <div>
        <p className="font-mono text-xs uppercase tracking-wide text-slate-500">Workspace knowledge</p>
        <h2 className="font-display text-3xl font-semibold tracking-tight text-slate-900">Knowledge sources</h2>
        <p className="mt-2 max-w-2xl text-slate-600">Maintain the policies, FAQs, product facts, and escalation notes the AI can reference.</p>
      </div>

      {message ? <p className="rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-600">{message}</p> : null}

      <div className="grid gap-6 xl:grid-cols-[420px_1fr]">
        <form onSubmit={handleSubmit} className="rounded-lg border border-slate-200 bg-white p-5">
          <h3 className="font-display text-lg font-semibold">{editingId ? "Edit source" : "New source"}</h3>
          <label className="mt-4 block text-sm font-medium text-slate-700" htmlFor="knowledge-title">Title</label>
          <input id="knowledge-title" value={title} onChange={(event) => setTitle(event.target.value)} className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />

          <label className="mt-4 block text-sm font-medium text-slate-700" htmlFor="knowledge-type">Type</label>
          <select id="knowledge-type" value={sourceType} onChange={(event) => setSourceType(event.target.value)} className="mt-2 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm">
            {sourceTypes.map((type) => <option key={type} value={type}>{type.replaceAll("_", " ")}</option>)}
          </select>

          <label className="mt-4 block text-sm font-medium text-slate-700" htmlFor="knowledge-body">Content</label>
          <textarea id="knowledge-body" value={body} onChange={(event) => setBody(event.target.value)} rows={10} className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2 text-sm leading-6" />

          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <label className="block text-sm font-medium text-slate-700" htmlFor="effective-from">Effective from
              <input id="effective-from" type="date" value={effectiveFrom} onChange={(event) => setEffectiveFrom(event.target.value)} className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-normal" />
            </label>
            <label className="block text-sm font-medium text-slate-700" htmlFor="effective-until">Effective until
              <input id="effective-until" type="date" value={effectiveUntil} onChange={(event) => setEffectiveUntil(event.target.value)} className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-normal" />
            </label>
          </div>

          <div className="mt-5 flex gap-2">
            <Button type="submit" variant="primary" disabled={saving}>{saving ? "Saving..." : editingId ? "Save changes" : "Create source"}</Button>
            {editingId ? <Button type="button" variant="ghost" onClick={resetForm}>Cancel</Button> : null}
          </div>
        </form>

        <div className="rounded-lg border border-slate-200 bg-white p-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <h3 className="font-display text-lg font-semibold">Sources</h3>
            <Button type="button" variant="outline" onClick={() => void toggleArchived()}>{includeArchived ? "Hide archived" : "Show archived"}</Button>
          </div>
          {loading ? <p className="mt-4 text-sm text-slate-500">Loading sources...</p> : null}
          <div className="mt-4 space-y-3">
            {sources.map((source) => (
              <div key={source.id} className="rounded-lg border border-slate-200 p-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-medium text-slate-900">{source.title}</p>
                      <span className="rounded-md bg-slate-100 px-2 py-1 text-xs capitalize text-slate-600">{source.source_type.replaceAll("_", " ")}</span>
                      <span className={`rounded-md px-2 py-1 text-xs capitalize ${source.status === "active" ? "bg-teal-50 text-teal-700" : "bg-slate-100 text-slate-500"}`}>{source.status}</span>
                    </div>
                    <p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-600">{source.body}</p>
                    <p className="mt-2 text-xs text-slate-500">{formatDate(source.effective_from)} to {formatDate(source.effective_until)}</p>
                  </div>
                  <div className="flex gap-2">
                    <Button type="button" variant="outline" onClick={() => startEdit(source)}>Edit</Button>
                    {source.status !== "archived" ? <Button type="button" variant="danger" onClick={() => void handleArchive(source.id)}>Archive</Button> : null}
                  </div>
                </div>
              </div>
            ))}
            {!loading && sources.length === 0 ? <p className="text-sm text-slate-500">No knowledge sources yet.</p> : null}
          </div>
        </div>
      </div>
    </section>
  );
}
