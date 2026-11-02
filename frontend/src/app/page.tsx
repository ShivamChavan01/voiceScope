'use client';

import { useEffect, useState, useCallback } from 'react';
import { useReadOnlyDemo } from '@/components/demo-access';
import Link from 'next/link';
import { ArrowRight, AudioLines, FileSearch, ShieldCheck, SlidersHorizontal } from 'lucide-react';
import { OverviewCoverage } from '@/components/overview-coverage';
import { ReviewBadge } from '@/components/call-review';
import { getRuns, getRunSummary, getCosts, loadReviewDemo, type Run, type RunSummary, type CostSummary } from '@/lib/api';
import { formatDuration, relativeTime } from '@/lib/reliability';

type Overview = { kind: 'loading' } | { kind: 'error'; message: string } | { kind: 'ready'; summary: RunSummary; runs: Run[]; costs: CostSummary | null };

export default function OverviewPage() {
  const readOnly=useReadOnlyDemo();
  const [state, setState] = useState<Overview>({ kind: 'loading' });
  const [demoLoading, setDemoLoading] = useState(false);
  const [demoError, setDemoError] = useState<string | null>(null);
  const load = useCallback(async () => {
    setState({ kind: 'loading' });
    try {
      const [summary, calls, costs] = await Promise.all([getRunSummary(), getRuns({ limit: 8 }), getCosts().catch(() => null)]);
      setState({ kind: 'ready', summary, runs: calls.runs, costs });
    } catch (error) { setState({ kind: 'error', message: error instanceof Error ? error.message : 'The overview could not be loaded.' }); }
  }, []);
  useEffect(() => {
    let active = true;
    Promise.all([getRunSummary(), getRuns({ limit: 8 }), getCosts().catch(() => null)]).then(([summary, calls, costs]) => {
      if (active) setState({ kind: 'ready', summary, runs: calls.runs, costs });
    }).catch(error => { if (active) setState({ kind: 'error', message: error instanceof Error ? error.message : 'The overview could not be loaded.' }); });
    return () => { active = false; };
  }, []);
  const demo = async () => {
    setDemoLoading(true); setDemoError(null);
    try { await loadReviewDemo(); await load(); }
    catch (error) { setDemoError(error instanceof Error ? error.message : 'Synthetic scenarios could not be loaded.'); }
    finally { setDemoLoading(false); }
  };
  const ready = state.kind === 'ready' ? state : null;
  return <>
    <div className="review-page-header"><div><div className="review-eyebrow">VoiceScope / Overview</div><h1 className="page-title">Know what happened on the call.</h1><p className="page-subtitle">Trace policy findings to the conversation. Keep missing evidence visible.</p></div><Link className="btn btn-primary" href="/runs">Review calls <ArrowRight size={15} /></Link></div>
    <section className="review-intro"><div className="review-intro-copy"><span className="review-eyebrow">Evidence before a verdict</span><h2>A clear path from claim to policy.</h2><p>Inspect the exact words, the rule that applied, and what remains unverified. Speech diagnostics help investigate the conversation without guessing the cause.</p><div className="review-intro-actions">{!readOnly && <button className="btn btn-ghost" disabled={demoLoading} onClick={demo}>{demoLoading ? 'Loading scenarios…' : 'Explore 3 synthetic scenarios'}</button>}<Link href="/settings" className="review-text-link">{readOnly ? "View demo policies" : "Configure policies"} <ArrowRight size={14} /></Link></div>{demoError && <p className="review-inline-error" role="alert">{demoError}</p>}</div><div className="review-intro-flow"><div><span className="review-flow-icon"><AudioLines size={18} /></span><strong>Conversation</strong><p>Attributed turns</p></div><span className="review-flow-arrow">→</span><div><span className="review-flow-icon"><SlidersHorizontal size={18} /></span><strong>Your policy</strong><p>Explicit supported rule</p></div><span className="review-flow-arrow">→</span><div><span className="review-flow-icon"><FileSearch size={18} /></span><strong>Finding</strong><p>Quote and explanation</p></div></div></section>
    {state.kind === 'error' ? <section className="review-error" role="alert"><strong>Overview unavailable</strong><p>{state.message}</p><button className="btn btn-ghost" onClick={() => void load()}>Retry loading</button></section> : <>
      <div className="review-stat-grid" aria-busy={state.kind === 'loading'}>
        <Stat label="Stored calls" value={ready?.summary.total_calls} detail={ready ? `${ready.summary.real_calls} real inputs · ${ready.summary.demo_calls} synthetic` : 'Loading persisted totals'} />
        <Stat label="Calls with policy matches" value={ready?.summary.confirmed_policy_calls} detail="Real calls only · confirmed supported rule matches" tone="danger" />
        <Stat label="Calls needing evidence review" value={ready?.summary.review_calls} detail="Real calls only · evidence needs corroboration" tone="warning" />
        <Stat label="Calls assessed with policies" value={ready?.summary.evaluated_policy_calls} detail="Real calls only · scoped supported checks" />
      </div>
      <section className="review-queue"><div className="review-section-heading"><div><span className="review-eyebrow">Inspection queue</span><h2>Recent calls</h2></div><Link href="/runs" className="review-text-link">View all calls <ArrowRight size={14} /></Link></div>
        <div className="table-wrap"><div className="table-scroll"><table className="review-calls-table"><thead><tr><th>Call</th><th>Assessment</th><th>Source</th><th>Duration</th><th>Processing</th></tr></thead><tbody>{state.kind === 'loading' ? <tr><td colSpan={5} className="review-table-empty">Loading the call queue…</td></tr> : !ready?.runs.length ? <tr><td colSpan={5}><div className="review-empty"><FileSearch size={28} /><h3>No calls to review yet</h3><p>{readOnly?'Synthetic fixtures are unavailable. Ask the demo operator to check startup.':'Upload a recording or explore the three synthetic scenarios. Synthetic inputs remain clearly labeled.'}</p><Link href="/runs" className="btn btn-ghost">Open call review <ArrowRight size={14} /></Link></div></td></tr> : ready.runs.map(run => <tr key={run.run_id}><td><Link href={`/runs?call=${encodeURIComponent(run.run_id)}`} className="call-intent call-review-link">{run.intent || 'Intent unavailable'}<ArrowRight size={13} /></Link><span className="call-id">{run.run_id.slice(0, 16)} · {relativeTime(run.created_at)}</span></td><td><ReviewBadge run={run} /></td><td><span className={`source-label ${run.run_id.startsWith('demo-') ? 'source-synthetic' : ''}`}>{run.run_id.startsWith('demo-') ? 'Synthetic demo' : 'Real input'}</span></td><td className="mono">{formatDuration(run.duration_seconds)}</td><td><span className={`processing-state processing-${run.status}`}>{run.status}</span></td></tr>)}</tbody></table></div></div>
      </section>
      {ready && <div className="review-operational"><span><ShieldCheck size={15} /><OverviewCoverage summary={ready.summary} /></span><span>Recorded LLM cost <strong>{ready.costs?.overall.total_cost == null ? 'Unavailable' : `$${ready.costs.overall.total_cost.toFixed(4)}`}</strong></span></div>}
    </>}
    <div className="review-scope-note">No configured rule match does not mean a call is fully compliant. VoiceScope cannot verify external actions without their results.</div>
  </>;
}

function Stat({ label, value, detail, tone = 'default' }: { label: string; value: number | undefined; detail: string; tone?: 'default' | 'danger' | 'warning' }) {
  return <section className={`review-stat review-stat-${tone}`}><span>{label}</span><strong>{value == null ? '—' : value.toLocaleString()}</strong><p>{detail}</p></section>;
}
