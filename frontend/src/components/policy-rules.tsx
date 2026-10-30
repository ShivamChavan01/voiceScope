'use client';

import { useCallback, useEffect, useState } from 'react';
import { FileCheck2, Plus } from 'lucide-react';
import { deletePolicyRule, getPolicyRules, savePolicyRule } from '@/lib/api';
import type { PolicyKind, PolicyRule } from '@/lib/reliability';

const OPTIONS: { kind: PolicyKind; label: string; template: string; description: string }[] = [
  { kind: 'no_same_day_refund_guarantee', label: 'Forbidden same-day refund guarantee', template: 'Agents must never guarantee same-day refunds.', description: 'Matches explicit prohibited guarantees. Estimates and missing refund results do not establish this violation.' },
  { kind: 'honor_escalation_request', label: 'Honor a request for human escalation', template: 'If a customer requests a supervisor, agents must honor the request immediately.', description: 'Matches an explicit caller request followed by an explicit refusal. An absent transfer log is not proof of refusal.' },
];
type Draft = Omit<PolicyRule, 'version'>;
const newDraft = (): Draft => ({ id: '', title: '', kind: 'no_same_day_refund_guarantee', text: OPTIONS[0].template, enabled: true });

export function PolicyRulesPanel() {
  const [rules, setRules] = useState<PolicyRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [saving, setSaving] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const reload = useCallback(async () => {
    setLoading(true); setError(null);
    try { setRules(await getPolicyRules()); }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'Policies could not be loaded.'); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => {
    let active = true;
    getPolicyRules().then(items => { if (active) setRules(items); }).catch(failure => { if (active) setError(failure instanceof Error ? failure.message : 'Policies could not be loaded.'); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!draft) return;
    setSaving(true); setError(null);
    try {
      await savePolicyRule({ ...draft, id: draft.id || crypto.randomUUID() });
      setDraft(null); await reload();
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Policy could not be saved.'); }
    finally { setSaving(false); }
  };
  const toggle = async (rule: PolicyRule) => {
    setBusyId(rule.id); setError(null);
    try { await savePolicyRule({ id: rule.id, title: rule.title, kind: rule.kind, text: rule.text, enabled: !rule.enabled }); await reload(); }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'Policy could not be updated.'); }
    finally { setBusyId(null); }
  };
  const remove = async (rule: PolicyRule) => {
    if (!window.confirm(`Remove policy “${rule.title}”? Historical finding snapshots are retained.`)) return;
    setBusyId(rule.id); setError(null);
    try { await deletePolicyRule(rule.id); await reload(); }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'Policy could not be removed.'); }
    finally { setBusyId(null); }
  };
  return <div className="review-stack">
    <div className="review-section-heading"><div><h2>Supported policy checks</h2><p className="review-description">Activate a rule only when it reflects your company’s actual policy.</p></div><button className="btn btn-primary" onClick={() => setDraft(newDraft())}><Plus size={15} />Add policy</button></div>
    <div className="review-note">No fictional policy is applied automatically. Reference knowledge remains available separately. Changes apply to future evaluations; stored findings retain the policy text and version used at evaluation time.</div>
    {error && <div className="review-error" role="alert"><p>{error}</p>{!draft && <button className="btn btn-ghost" onClick={() => void reload()}>Retry loading policies</button>}</div>}
    {draft && <form className="review-policy-form" onSubmit={save}><h3>{draft.id ? 'Edit supported policy' : 'Add a company policy'}</h3><label>Policy title<input aria-label="Policy title" required className="f-input" value={draft.title} onChange={event => setDraft({ ...draft, title: event.target.value })} placeholder="e.g. Refund timing restrictions" /></label><label>Supported check<select aria-label="Supported check" className="f-input" value={draft.kind} onChange={event => { const option = OPTIONS.find(item => item.kind === event.target.value); if (option) setDraft({ ...draft, kind: option.kind, text: option.template }); }}>{OPTIONS.map(option => <option key={option.kind} value={option.kind}>{option.label}</option>)}</select></label><p className="review-description">{OPTIONS.find(option => option.kind === draft.kind)?.description}</p><label>Actual company policy<textarea aria-label="Actual company policy" required className="f-input" rows={4} value={draft.text} onChange={event => setDraft({ ...draft, text: event.target.value })} /></label><label className="review-checkbox"><input type="checkbox" checked={draft.enabled} onChange={event => setDraft({ ...draft, enabled: event.target.checked })} />Enable this check for future calls</label><div className="review-form-actions"><button type="submit" className="btn btn-primary" disabled={saving}>{saving ? 'Saving…' : 'Save company policy'}</button><button type="button" className="btn btn-ghost" disabled={saving} onClick={() => setDraft(null)}>Cancel</button></div></form>}
    {loading ? <div className="review-empty" role="status">Loading supported policies…</div> : !rules.length && !error ? <section className="review-empty"><FileCheck2 size={30} /><h3>No company policies configured</h3><p>Calls can still be transcribed. Policy assessment will report insufficient evidence until you explicitly activate a supported company rule.</p><button className="btn btn-ghost" onClick={() => setDraft(newDraft())}>Configure your first policy</button></section> : <div className="review-policy-list">{rules.map(rule => <article className="review-policy-item" key={rule.id}><div className="review-section-heading"><h3>{rule.title}</h3><span className={`source-label ${rule.enabled ? '' : 'source-synthetic'}`}>{rule.enabled ? 'Enabled' : 'Disabled'}</span></div><p>{rule.text}</p><span className="policy-version">{OPTIONS.find(option => option.kind === rule.kind)?.label || rule.kind} · Version {rule.version.slice(0, 12)}</span><div className="review-form-actions"><button className="btn btn-ghost" disabled={busyId === rule.id} onClick={() => setDraft({ id: rule.id, title: rule.title, kind: rule.kind, text: rule.text, enabled: rule.enabled })}>Edit</button><button className="btn btn-ghost" disabled={busyId === rule.id} onClick={() => void toggle(rule)}>{rule.enabled ? 'Disable' : 'Enable'}</button><button className="review-delete-text" disabled={busyId === rule.id} onClick={() => void remove(rule)}>Remove</button></div></article>)}</div>}
  </div>;
}
