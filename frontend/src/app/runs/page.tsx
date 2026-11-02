'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useReadOnlyDemo } from '@/components/demo-access';
import { callNavigationUrl, syntheticScenarioNote } from '@/lib/call-navigation';
import { AudioLines, ArrowUpRight, Search, Upload, X } from 'lucide-react';
import { HarnessBar, HARNESS_KEYS } from '@/components/harness-bar';
import { CallReport, CallSummary, FindingsPanel, ReviewBadge, SpeechPanel } from '@/components/call-review';
import { CallRecording } from '@/components/call-recording';
import { STTReviewPanel } from '@/components/stt-review';
import { TranscriptConversation } from '@/components/transcript-conversation';
import { UploadProgress } from '@/components/upload-progress';
import { getRuns, getRun, analyzeAudioStream, deleteRun, loadReviewDemo, type Run, type StreamEvent } from '@/lib/api';
import { validScore } from '@/lib/evaluation';
import { formatDuration, relativeTime } from '@/lib/reliability';

type Detail = { kind: 'closed' } | { kind: 'loading'; id: string } | { kind: 'error'; id: string; message: string } | { kind: 'ready'; run: Run };
type Tab = 'findings' | 'transcript' | 'speech' | 'stt' | 'checks';
const TABS: { key: Tab; label: string }[] = [{ key: 'findings', label: 'Findings' }, { key: 'transcript', label: 'Transcript' }, { key: 'speech', label: 'Speech diagnostics' }, { key: 'stt', label: 'STT quality' }, { key: 'checks', label: 'Evaluation checks' }];

export default function RunsPage() {
  const readOnly=useReadOnlyDemo();
  const [runs, setRuns] = useState<Run[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [detail, setDetail] = useState<Detail>({ kind: 'closed' });
  const [tab, setTab] = useState<Tab>('findings');
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [deleting, setDeleting] = useState<string | null>(null);
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [actionError, setActionError] = useState<string | undefined>();
  const [demoLoading, setDemoLoading] = useState(false);
  const [highlightedTurn, setHighlightedTurn] = useState<number | null>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const triggerRef = useRef<HTMLElement | null>(null);
  const drawerRef = useRef<HTMLDivElement>(null);
  const turnRefs = useRef(new Map<number, HTMLDivElement>());
  const detailRequest = useRef(0);
  const listRequest = useRef(0);
  const open = detail.kind !== 'closed';
  const selected = detail.kind === 'ready' ? detail.run : null;

  const refresh = useCallback(async () => {
    const request=++listRequest.current;
    setLoading(true);
    setListError(null);
    try {
      const response = await getRuns({ limit: 50, search, status });
      if(request===listRequest.current){setRuns(response.runs);setTotal(response.total);}
    } catch (error) {
      if(request===listRequest.current)setListError(error instanceof Error ? error.message : 'Calls could not be loaded.');
    } finally { if(request===listRequest.current)setLoading(false); }
  }, [search, status]);

  useEffect(() => {
    let active = true;
    const request=++listRequest.current;
    getRuns({ limit: 50, search, status }).then(response => {
      if (active && request===listRequest.current) { setRuns(response.runs); setTotal(response.total); }
    }).catch(error => {
      if (active && request===listRequest.current) setListError(error instanceof Error ? error.message : 'Calls could not be loaded.');
    }).finally(() => { if (active && request===listRequest.current) setLoading(false); });
    return () => { active = false; listRequest.current+=1; };
  }, [search, status]);

  const loadDetail = useCallback((call: string | null) => {
    const request = ++detailRequest.current;
    setTab('findings');
    setHighlightedTurn(null);
    if (!call) { setDetail({ kind: 'closed' }); return; }
    setDetail({ kind: 'loading', id: call });
    getRun(call).then(run => {
      if (request === detailRequest.current) setDetail({ kind: 'ready', run });
    }).catch(error => {
      if (request === detailRequest.current) setDetail({ kind: 'error', id: call, message: error instanceof Error ? error.message : 'Call details could not be loaded.' });
    });
  }, []);
  useEffect(() => {
    const sync = () => loadDetail(new URL(window.location.href).searchParams.get('call'));
    sync();
    window.addEventListener('popstate', sync);
    return () => { detailRequest.current += 1; window.removeEventListener('popstate', sync); };
  }, [loadDetail]);

  const close = useCallback(() => {
    if (new URL(window.location.href).searchParams.has('call')) {
      window.history.pushState(null, '', callNavigationUrl(window.location.href, null));
    }
    loadDetail(null);
    triggerRef.current?.focus();
  }, [loadDetail]);

  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close();
      if (event.key !== 'Tab') return;
      const closedSections = Array.from(drawerRef.current?.querySelectorAll('details:not([open])') || []);
      const elements = Array.from(drawerRef.current?.querySelectorAll<HTMLElement>('button:not([disabled]), a[href], input, select, textarea, summary, audio[controls], [tabindex="0"]') || []).filter(element =>
        element.getClientRects().length > 0 && !closedSections.some(section => section.contains(element) && section.querySelector('summary') !== element));
      if (!elements?.length) return;
      const first = elements[0];
      const last = elements[elements.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, close]);

  useEffect(() => {
    if (tab === 'transcript' && highlightedTurn != null) {
      turnRefs.current.get(highlightedTurn)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [tab, highlightedTurn]);

  const openRun = async (run: Pick<Run, 'run_id'>, trigger?: HTMLElement) => {
    if (trigger) triggerRef.current = trigger;
    if (new URL(window.location.href).searchParams.get('call') !== run.run_id) {
      window.history.pushState(null, '', callNavigationUrl(window.location.href, run.run_id));
    }
    loadDetail(run.run_id);
  };
  const upload = async (file: File) => {
    if (uploading) return;
    if (file.size > 25 * 1024 * 1024) { setActionError('Choose an audio file smaller than 25 MB.'); return; }
    setUploading(true); setEvents([]); setActionError(undefined);
    try {
      for await (const event of analyzeAudioStream(file)) {
        setEvents(previous => [...previous, event]);
        if (event.event === 'complete' && event.result) { await refresh(); await openRun(event.result); }
        if (event.event === 'error') setActionError(event.detail || 'Analysis failed.');
      }
    } catch (error) { setActionError(error instanceof Error ? error.message : 'Analysis failed.'); }
    finally { setUploading(false); }
  };
  const demo = async () => {
    setDemoLoading(true); setActionError(undefined);
    try { await loadReviewDemo(); await refresh(); }
    catch (error) { setActionError(error instanceof Error ? error.message : 'Demo scenarios could not be loaded.'); }
    finally { setDemoLoading(false); }
  };
  const remove = async (event: React.MouseEvent, id: string) => {
    event.stopPropagation();
    if (!window.confirm('Delete this stored call?')) return;
    setDeleting(id); setActionError(undefined);
    try { await deleteRun(id); await refresh(); if (selected?.run_id === id) close(); }
    catch (error) { setActionError(error instanceof Error ? error.message : 'The call could not be deleted.'); }
    finally { setDeleting(null); }
  };
  const id = detail.kind === 'ready' ? detail.run.run_id : detail.kind !== 'closed' ? detail.id : '';

  return <div className="calls-page">
    <div className="review-page-header"><div><div className="review-eyebrow">Your workspace</div><h1 className="page-title">Calls</h1><p className="page-subtitle">Listen to the recording. Read the conversation. Review what needs attention.</p></div>{!readOnly && <button className="btn btn-ghost" onClick={demo} disabled={demoLoading}>{demoLoading ? 'Loading scenarios…' : 'Explore sample calls'}</button>}</div>
    {readOnly && <p className="review-note">Read-only synthetic demo. Uploads, policy changes and call deletion are disabled.</p>}
    {!readOnly && <div className="review-upload" role="button" tabIndex={uploading ? -1 : 0} aria-disabled={uploading} aria-label="Upload audio file for analysis" onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); const file = event.dataTransfer.files[0]; if (file) void upload(file); }} onClick={() => { if (!uploading) document.getElementById('file-input')?.click(); }} onKeyDown={event => { if (!uploading && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); document.getElementById('file-input')?.click(); } }}>
      <input id="file-input" type="file" accept="audio/*" hidden disabled={uploading} onChange={event => { const file = event.target.files?.[0]; if (file) void upload(file); event.target.value = ''; }} />
      <div className="review-upload-icon"><Upload size={21} /></div><div><strong>{uploading ? 'Processing your recording…' : 'Drop a recording here or choose a file'}</strong><p>WAV, MP3 or M4A · up to 25 MB</p></div><span className="review-upload-action">Choose audio <ArrowUpRight size={15} /></span>
    </div>
    }
    <UploadProgress events={uploading ? events : []} error={uploading ? actionError : undefined} />
    {!uploading && actionError && <div className="review-error" role="alert">{actionError}</div>}
    <div className="review-toolbar"><label className="review-search"><Search size={16} /><input aria-label="Search calls" placeholder="Search calls…" value={search} onChange={event => { setLoading(true); setListError(null); setSearch(event.target.value); }} /></label><select className="filter-input" aria-label="Filter by processing status" value={status} onChange={event => { setLoading(true); setListError(null); setStatus(event.target.value); }}><option value="">All statuses</option><option value="completed">Processed</option><option value="partial">Review required</option><option value="failed">Processing failed</option></select><span>{loading ? 'Loading calls…' : `${total} ${total === 1 ? 'call' : 'calls'}`}</span></div>
    {listError ? <div className="review-error" role="alert"><strong>Calls are unavailable</strong><p>{listError}</p><button className="btn btn-ghost" onClick={() => void refresh()}>Retry loading</button></div> : <div className="table-wrap"><div className="table-scroll"><table className="review-calls-table"><thead><tr><th>Call</th><th>Assessment</th><th>Source</th><th>Duration</th><th><span className="sr-only">Actions</span></th></tr></thead><tbody>{loading ? <tr><td colSpan={5} className="review-table-empty">Loading stored calls…</td></tr> : !runs.length ? <tr><td colSpan={5}><div className="review-empty"><AudioLines size={28} /><h3>{search || status ? 'No calls match these filters' : 'Your first call starts here'}</h3><p>{readOnly?'Try another filter. This demo contains fixed synthetic examples.':'Upload a recording or load the three synthetic scenarios to inspect an evidence-backed finding.'}</p></div></td></tr> : runs.map(run => <tr key={run.run_id} role="button" tabIndex={0} aria-label={`Review ${run.intent || run.run_id}`} onClick={event => void openRun(run, event.currentTarget)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); void openRun(run, event.currentTarget); } }}><td><strong className="call-intent">{run.intent || 'Untitled call'}</strong>{syntheticScenarioNote(run.run_id) && <span className="call-id">{syntheticScenarioNote(run.run_id)}</span>}<span className="call-id">{run.run_id.slice(0, 16)} · {relativeTime(run.created_at)}</span></td><td><ReviewBadge run={run} />{run.status !== 'completed' && <span className="call-processing-label">{run.status === 'failed' ? 'Processing failed' : run.status === 'partial' ? 'Review required' : run.status}</span>}</td><td><span className={`source-label ${run.run_id.startsWith('demo-') ? 'source-synthetic' : ''}`}>{run.run_id.startsWith('demo-') ? 'Synthetic demo' : 'Real input'}</span></td><td className="mono">{formatDuration(run.duration_seconds)}</td><td>{!readOnly && <button className="review-delete" disabled={deleting === run.run_id} onClick={event => void remove(event, run.run_id)} aria-label={`Delete call ${run.run_id}`} title="Delete stored call">{deleting === run.run_id ? '…' : '×'}</button>}</td></tr>)}</tbody></table></div></div>}
    <p className="calls-footer-note">Policy reviews cover configured checks. A call without findings is not a guarantee of compliance.</p>
    <div className={`drawer-overlay ${open ? 'open' : ''}`} onClick={close} />
    <div className={`drawer review-drawer ${open ? 'open' : ''}`} ref={drawerRef} role="dialog" aria-modal="true" aria-hidden={!open} inert={!open} aria-label={`Call detail: ${id.slice(0, 12)}`}>
      <div className="drawer-header"><div className="review-drawer-title"><strong>{selected?.intent || 'Call review'}</strong><span>{selected ? `${formatDuration(selected.duration_seconds)} · ${relativeTime(selected.created_at)}` : 'Loading call…'}</span></div>{selected && <span className={`source-label ${selected.run_id.startsWith('demo-') ? 'source-synthetic' : ''}`}>{selected.run_id.startsWith('demo-') ? 'Synthetic' : 'Real input'}</span>}<button className="drawer-close" ref={closeRef} onClick={close} aria-label="Close drawer"><X size={18} /></button></div>
      <div className="drawer-tabs" role="tablist" aria-label="Call inspection sections">{TABS.map(item => <button key={item.key} className={`drawer-tab ${tab === item.key ? 'active' : ''}`} role="tab" id={`call-tab-${item.key}`} aria-selected={tab === item.key} aria-controls={`drawer-panel-${item.key}`} onClick={() => setTab(item.key)}>{item.label}</button>)}</div>
      <div className="drawer-body">{detail.kind === 'loading' ? <div className="review-empty" role="status">Loading the full evaluation and transcript…</div> : detail.kind === 'error' ? <div className="review-error" role="alert"><strong>Call details are unavailable</strong><p>{detail.message}</p><button className="btn btn-ghost" onClick={() => { void openRun({run_id:detail.id}); }}>Retry</button></div> : selected && <div id={`drawer-panel-${tab}`} role="tabpanel" aria-labelledby={`call-tab-${tab}`}>
        {tab === 'findings' && <><CallReport run={selected} onChecks={() => setTab('checks')} /><CallSummary run={selected} /><FindingsPanel run={selected} onEvidence={turn => { setHighlightedTurn(turn); setTab('transcript'); }} /></>}
        {tab === 'stt' && <STTReviewPanel key={selected.run_id} runId={selected.run_id} />}
        {tab === 'transcript' && <div className="call-conversation"><CallRecording key={selected.run_id} run={selected} /><div className="review-section-heading"><h3>Conversation</h3><span>Original transcript</span></div><TranscriptConversation run={selected} highlightedTurn={highlightedTurn} registerTurn={(index, element) => { if (element) turnRefs.current.set(index, element); else turnRefs.current.delete(index); }} /></div>}
        {tab === 'speech' && <SpeechPanel run={selected} />}
        {tab === 'checks' && <div className="review-stack"><p className="call-debug-id">Call ID: {selected.run_id}</p><section className="review-note">These checks validate the evaluator output. Their score is not a probability that the call is truthful or compliant.</section><div className="diagnostic-grid"><div className="diagnostic-card"><span>Processing</span><strong>{selected.status}</strong><p>{selected.evaluation?.evaluation_status || 'Historical evaluation'}</p></div><div className="diagnostic-card"><span>Heuristic consistency</span><strong>{validScore(selected.truth_score) == null ? 'Unavailable' : `${Math.round((selected.truth_score ?? 0) * 100)}%`}</strong><p>Applicable evaluator checks</p></div><div className="diagnostic-card"><span>Model</span><strong className="review-small-value">{selected.model || 'Unavailable'}</strong><p>{selected.provider || 'Provider unavailable'}</p></div><div className="diagnostic-card"><span>Call duration</span><strong>{formatDuration(selected.duration_seconds)}</strong><p>Reported duration</p></div></div><HarnessBar scores={HARNESS_KEYS.map(key => selected.layer_scores?.[key] != null ? Math.round(selected.layer_scores[key] * 100) : null)} /><div className="review-section-heading"><h3>Evaluator messages</h3></div>{[...(selected.evaluation?.errors || []), ...(selected.evaluation?.harness?.validation_errors || [])].length ? <ul className="review-messages">{[...(selected.evaluation?.errors || []), ...(selected.evaluation?.harness?.validation_errors || [])].map((error, index) => <li key={index}>{error}</li>)}</ul> : <p className="review-description">No evaluator messages are stored. Older runs may not contain full validation details.</p>}{selected.hallucination_evidence && <section className="finding-policy"><strong>Legacy model evidence</strong><p>{selected.hallucination_evidence}</p><small>This model-generated text is separate from structured policy findings.</small></section>}</div>}
      </div>}</div>
    </div>
  </div>;
}
