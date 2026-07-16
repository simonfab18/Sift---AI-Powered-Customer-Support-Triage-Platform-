"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/Button";
import { getStoredOrganizationId } from "@/features/organizations/components/OrganizationManager";
import { createClient } from "@/lib/supabase/client";
import { getMembers } from "@/lib/api-client";
import type { Member } from "@/lib/api-types";
import { createRoutingRule, getRoutingRules, testRoutingRule, updateRoutingRule } from "@/features/tickets/api";
import type { RoutingRule, RoutingRuleTestResult } from "@/features/tickets/types";

const categories = ["refund", "return", "damaged_item", "billing", "account_access", "complaint", "product_question", "other"];
const priorities = ["critical", "high", "medium", "low"];
const sentiments = ["angry", "negative", "neutral", "positive"];
const assignableRoles = new Set(["owner", "admin", "agent"]);

function compactObject(input: Record<string, unknown>) {
  return Object.fromEntries(Object.entries(input).filter(([, value]) => value !== "" && value !== null && value !== undefined));
}

function labelize(value: string) {
  return value.replaceAll("_", " ");
}

function memberLabel(member?: Member) {
  if (!member) return "Unknown member";
  return `${member.email} (${member.role})`;
}

function describeJson(value: Record<string, unknown>, membersByUserId: Map<string, Member> = new Map()) {
  const entries = Object.entries(value);
  if (entries.length === 0) return "No values";
  return entries.map(([key, item]) => {
    if ((key === "assign_user_id" || key === "assigned_to_user_id") && typeof item === "string") {
      return `assign to: ${memberLabel(membersByUserId.get(item))}`;
    }
    if (key === "priority_floor") return `minimum urgency: ${String(item)}`;
    if (key === "require_approval") return `require approval: ${item ? "yes" : "no"}`;
    if (key === "add_tag") return `tag: ${String(item)}`;
    if (Array.isArray(item)) return `${labelize(key)}: ${item.join(", ")}`;
    return `${labelize(key)}: ${String(item)}`;
  }).join(" / ");
}

function matchesValue(expected: unknown, actual: unknown) {
  if (expected === null || expected === undefined || expected === "") return true;
  if (Array.isArray(expected)) return expected.map((item) => String(item).toLowerCase()).includes(String(actual ?? "").toLowerCase());
  return String(actual ?? "").toLowerCase() === String(expected).toLowerCase();
}

function evaluateSample(conditions: Record<string, unknown>, sample: Record<string, unknown>) {
  const matched: string[] = [];
  for (const key of ["category", "priority", "sentiment", "sender_domain", "customer_email"]) {
    if (key in conditions) {
      if (!matchesValue(conditions[key], sample[key])) return { matched: false, matched_conditions: matched };
      matched.push(key);
    }
  }

  const keyword = conditions.keyword;
  if (keyword) {
    const haystack = `${sample.subject ?? ""} ${sample.message_text ?? ""}`.toLowerCase();
    const keywords = Array.isArray(keyword) ? keyword : [keyword];
    if (!keywords.some((item) => haystack.includes(String(item).toLowerCase()))) return { matched: false, matched_conditions: matched };
    matched.push("keyword");
  }

  return { matched: true, matched_conditions: matched };
}

export function RoutingRulesSettings() {
  const supabase = createClient();
  const [rules, setRules] = useState<RoutingRule[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [name, setName] = useState("");
  const [priorityOrder, setPriorityOrder] = useState(100);
  const [isActive, setIsActive] = useState(false);
  const [category, setCategory] = useState("");
  const [priority, setPriority] = useState("");
  const [sentiment, setSentiment] = useState("");
  const [keyword, setKeyword] = useState("");
  const [senderDomain, setSenderDomain] = useState("");
  const [assignUserId, setAssignUserId] = useState("");
  const [priorityFloor, setPriorityFloor] = useState("");
  const [requireApproval, setRequireApproval] = useState(true);
  const [addTag, setAddTag] = useState("");
  const [sampleSubject, setSampleSubject] = useState("Refund request");
  const [sampleMessage, setSampleMessage] = useState("Please refund this damaged order.");
  const [sampleCategory, setSampleCategory] = useState("refund");
  const [samplePriority, setSamplePriority] = useState("medium");
  const [sampleSentiment, setSampleSentiment] = useState("negative");
  const [sampleSenderDomain, setSampleSenderDomain] = useState("example.com");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<RoutingRuleTestResult | null>(null);
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

  const membersByUserId = useMemo(() => new Map(members.map((member) => [member.user_id, member])), [members]);
  const assignableMembers = useMemo(
    () => members.filter((member) => member.status === "active" && assignableRoles.has(member.role)).sort((first, second) => first.email.localeCompare(second.email)),
    [members],
  );
  const currentConditions = useMemo(() => compactObject({ category, priority, sentiment, keyword, sender_domain: senderDomain }), [category, priority, sentiment, keyword, senderDomain]);
  const currentActions = useMemo(() => compactObject({ assign_user_id: assignUserId, priority_floor: priorityFloor, require_approval: requireApproval || undefined, add_tag: addTag }), [assignUserId, priorityFloor, requireApproval, addTag]);
  const currentSample = useMemo(() => compactObject({
    subject: sampleSubject,
    message_text: sampleMessage,
    category: sampleCategory,
    priority: samplePriority,
    sentiment: sampleSentiment,
    sender_domain: sampleSenderDomain,
  }), [sampleSubject, sampleMessage, sampleCategory, samplePriority, sampleSentiment, sampleSenderDomain]);

  async function loadRules() {
    setLoading(true);
    setMessage(null);
    const context = await getContext();
    if (!context) {
      setMessage("Select a workspace and sign in before managing routing rules.");
      setLoading(false);
      return;
    }
    try {
      const [loadedRules, loadedMembers] = await Promise.all([
        getRoutingRules(context.organizationId, context.accessToken),
        getMembers(context.accessToken, context.organizationId).catch(() => []),
      ]);
      setRules(loadedRules);
      setMembers(loadedMembers);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to load routing rules.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadRules();
  }, []);

  function resetForm() {
    setEditingId(null);
    setName("");
    setPriorityOrder(100);
    setIsActive(false);
    setCategory("");
    setPriority("");
    setSentiment("");
    setKeyword("");
    setSenderDomain("");
    setAssignUserId("");
    setPriorityFloor("");
    setRequireApproval(true);
    setAddTag("");
    setTestResult(null);
  }

  function startEdit(rule: RoutingRule) {
    setEditingId(rule.id);
    setName(rule.name);
    setPriorityOrder(rule.priority_order);
    setIsActive(rule.is_active);
    setCategory(String(rule.conditions.category ?? ""));
    setPriority(String(rule.conditions.priority ?? ""));
    setSentiment(String(rule.conditions.sentiment ?? ""));
    setKeyword(String(rule.conditions.keyword ?? ""));
    setSenderDomain(String(rule.conditions.sender_domain ?? ""));
    setAssignUserId(String(rule.actions.assign_user_id ?? ""));
    setPriorityFloor(String(rule.actions.priority_floor ?? ""));
    setRequireApproval(Boolean(rule.actions.require_approval));
    setAddTag(String(rule.actions.add_tag ?? ""));
    setSampleCategory(String(rule.conditions.category ?? sampleCategory));
    setSamplePriority(String(rule.conditions.priority ?? samplePriority));
    setSampleSentiment(String(rule.conditions.sentiment ?? sampleSentiment));
    setSampleSenderDomain(String(rule.conditions.sender_domain ?? sampleSenderDomain));
    setTestResult(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const context = await getContext();
    if (!context) return;
    if (!name.trim()) {
      setMessage("Name the rule before saving.");
      return;
    }
    setSaving(true);
    setMessage(null);
    try {
      const payload = {
        name: name.trim(),
        priority_order: priorityOrder,
        is_active: isActive,
        conditions: currentConditions,
        actions: currentActions,
      };
      if (editingId) {
        await updateRoutingRule(context.organizationId, context.accessToken, editingId, payload);
        setMessage("Routing rule updated.");
      } else {
        await createRoutingRule(context.organizationId, context.accessToken, payload);
        setMessage("Routing rule created.");
      }
      resetForm();
      await loadRules();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to save routing rule.");
    } finally {
      setSaving(false);
    }
  }

  async function handleToggleActive(rule: RoutingRule) {
    const context = await getContext();
    if (!context) return;
    try {
      await updateRoutingRule(context.organizationId, context.accessToken, rule.id, { is_active: !rule.is_active });
      await loadRules();
      setMessage(!rule.is_active ? "Routing rule activated." : "Routing rule paused.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to update routing rule.");
    }
  }

  async function handleTestCurrentRule() {
    const context = await getContext();
    if (!context) return;
    if (!editingId) {
      const result = evaluateSample(currentConditions, currentSample);
      setTestResult({
        ...result,
        actions_preview: result.matched ? currentActions : {},
      });
      return;
    }
    try {
      const result = await testRoutingRule(context.organizationId, context.accessToken, editingId, currentSample);
      setTestResult(result);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to test routing rule.");
    }
  }

  return (
    <section className="space-y-6">
      <div>
        <p className="font-mono text-xs uppercase tracking-wide text-slate-500">Automation</p>
        <h2 className="font-display text-3xl font-semibold tracking-tight text-slate-900">Routing rules</h2>
        <p className="mt-2 max-w-2xl text-slate-600">Route matching tickets by category, urgency, sender, keywords, and review requirements.</p>
      </div>

      {message ? <p className="rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-600">{message}</p> : null}

      <div className="grid gap-6 xl:grid-cols-[460px_1fr]">
        <form onSubmit={handleSubmit} className="rounded-lg border border-slate-200 bg-white p-5">
          <h3 className="font-display text-lg font-semibold">{editingId ? "Edit rule" : "New rule"}</h3>
          <label className="mt-4 block text-sm font-medium text-slate-700" htmlFor="rule-name">Rule name</label>
          <input id="rule-name" value={name} onChange={(event) => setName(event.target.value)} className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <label className="block text-sm font-medium text-slate-700" htmlFor="rule-order">Order
              <input id="rule-order" type="number" value={priorityOrder} onChange={(event) => setPriorityOrder(Number(event.target.value))} className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-normal" />
            </label>
            <label className="flex items-center gap-2 pt-8 text-sm font-medium text-slate-700">
              <input type="checkbox" checked={isActive} onChange={(event) => setIsActive(event.target.checked)} className="h-4 w-4 rounded border-slate-300" /> Active
            </label>
          </div>

          <div className="mt-5 border-t border-slate-200 pt-5">
            <p className="text-sm font-semibold text-slate-900">Conditions</p>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <select value={category} onChange={(event) => setCategory(event.target.value)} className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"><option value="">Any category</option>{categories.map((item) => <option key={item} value={item}>{labelize(item)}</option>)}</select>
              <select value={priority} onChange={(event) => setPriority(event.target.value)} className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"><option value="">Any urgency</option>{priorities.map((item) => <option key={item} value={item}>{item}</option>)}</select>
              <select value={sentiment} onChange={(event) => setSentiment(event.target.value)} className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"><option value="">Any sentiment</option>{sentiments.map((item) => <option key={item} value={item}>{item}</option>)}</select>
              <input value={senderDomain} onChange={(event) => setSenderDomain(event.target.value.trim().toLowerCase())} placeholder="Sender domain" className="rounded-md border border-slate-300 px-3 py-2 text-sm" />
            </div>
            <input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="Keyword in subject or message" className="mt-3 w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
          </div>

          <div className="mt-5 border-t border-slate-200 pt-5">
            <p className="text-sm font-semibold text-slate-900">Actions</p>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <select value={assignUserId} onChange={(event) => setAssignUserId(event.target.value)} className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm">
                <option value="">Leave unassigned</option>
                {assignableMembers.map((member) => <option key={member.id} value={member.user_id}>{memberLabel(member)}</option>)}
              </select>
              <select value={priorityFloor} onChange={(event) => setPriorityFloor(event.target.value)} className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"><option value="">No urgency floor</option>{priorities.map((item) => <option key={item} value={item}>{item}</option>)}</select>
              <input value={addTag} onChange={(event) => setAddTag(event.target.value)} placeholder="Record tag" className="rounded-md border border-slate-300 px-3 py-2 text-sm" />
              <label className="flex items-center gap-2 text-sm font-medium text-slate-700"><input type="checkbox" checked={requireApproval} onChange={(event) => setRequireApproval(event.target.checked)} className="h-4 w-4 rounded border-slate-300" /> Require approval</label>
            </div>
            {assignableMembers.length === 0 ? <p className="mt-2 text-xs text-amber-700">No active agents/admins found. Add a team member before using automatic assignment.</p> : null}
          </div>

          <div className="mt-5 border-t border-slate-200 pt-5">
            <p className="text-sm font-semibold text-slate-900">Test sample</p>
            <input value={sampleSubject} onChange={(event) => setSampleSubject(event.target.value)} className="mt-3 w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
            <textarea value={sampleMessage} onChange={(event) => setSampleMessage(event.target.value)} rows={3} className="mt-3 w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <select value={sampleCategory} onChange={(event) => setSampleCategory(event.target.value)} className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm">{categories.map((item) => <option key={item} value={item}>{labelize(item)}</option>)}</select>
              <select value={samplePriority} onChange={(event) => setSamplePriority(event.target.value)} className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm">{priorities.map((item) => <option key={item} value={item}>{item}</option>)}</select>
              <select value={sampleSentiment} onChange={(event) => setSampleSentiment(event.target.value)} className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm">{sentiments.map((item) => <option key={item} value={item}>{item}</option>)}</select>
              <input value={sampleSenderDomain} onChange={(event) => setSampleSenderDomain(event.target.value.trim().toLowerCase())} placeholder="Sample sender domain" className="rounded-md border border-slate-300 px-3 py-2 text-sm" />
            </div>
            <Button type="button" variant="outline" className="mt-3" onClick={() => void handleTestCurrentRule()}>Test rule</Button>
            {testResult ? (
              <div className={`mt-3 rounded-md border p-3 text-sm ${testResult.matched ? "border-teal-200 bg-teal-50 text-teal-800" : "border-slate-200 bg-slate-50 text-slate-600"}`}>
                <p className="font-medium">{testResult.matched ? "Sample matches this rule" : "Sample does not match"}</p>
                <p className="mt-1 text-xs leading-5">Matched conditions: {testResult.matched_conditions.length ? testResult.matched_conditions.map(labelize).join(", ") : "none"}</p>
                <p className="mt-1 text-xs leading-5">Actions: {describeJson(testResult.actions_preview, membersByUserId)}</p>
              </div>
            ) : null}
          </div>

          <div className="mt-5 flex gap-2">
            <Button type="submit" variant="primary" disabled={saving}>{saving ? "Saving..." : editingId ? "Save rule" : "Create rule"}</Button>
            {editingId ? <Button type="button" variant="ghost" onClick={resetForm}>Cancel</Button> : null}
          </div>
        </form>

        <div className="rounded-lg border border-slate-200 bg-white p-5">
          <h3 className="font-display text-lg font-semibold">Rule order</h3>
          {loading ? <p className="mt-4 text-sm text-slate-500">Loading rules...</p> : null}
          <div className="mt-4 space-y-3">
            {rules.map((rule) => (
              <div key={rule.id} className="rounded-lg border border-slate-200 p-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-medium text-slate-900">{rule.priority_order}. {rule.name}</p>
                      <span className={`rounded-md px-2 py-1 text-xs ${rule.is_active ? "bg-teal-50 text-teal-700" : "bg-slate-100 text-slate-500"}`}>{rule.is_active ? "Active" : "Paused"}</span>
                    </div>
                    <p className="mt-2 text-sm text-slate-600">When {describeJson(rule.conditions, membersByUserId)}</p>
                    <p className="mt-1 text-sm text-slate-500">Then {describeJson(rule.actions, membersByUserId)}</p>
                  </div>
                  <div className="flex gap-2">
                    <Button type="button" variant="outline" onClick={() => startEdit(rule)}>Edit</Button>
                    <Button type="button" variant="ghost" onClick={() => void handleToggleActive(rule)}>{rule.is_active ? "Pause" : "Activate"}</Button>
                  </div>
                </div>
              </div>
            ))}
            {!loading && rules.length === 0 ? <p className="text-sm text-slate-500">No routing rules yet.</p> : null}
          </div>
        </div>
      </div>
    </section>
  );
}