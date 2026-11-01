'use client';

import Link from 'next/link';
import { ArrowUpRight, CheckCircle2, FileQuestion, Info, ShieldAlert, TriangleAlert } from 'lucide-react';
import type { Run } from '@/lib/api';
import { categoryLabel, formatMetric, readReliability, readSpeech, reviewVerdict } from '@/lib/reliability';

export function ReviewBadge({ run }: { run: Run }) {
  const verdict = reviewVerdict(run);
  return <span className={`review-badge review-badge-${verdict.kind}`}>{verdict.label}</span>;
}

export function CallReport({ run, onChecks }: { run: Run; onChecks: () => void }) {
  const summary = run.evaluation?.report?.executive_summary;
  if (typeof summary !== 'string' || !summary.trim() || !run.provider || run.provider === 'synthetic' || run.status === 'failed') return null;
  const messages = run.evaluation?.harness?.validation_errors;
  const warnings = Array.isArray(messages) ? messages.filter(message => typeof message === 'string' && message.trim()) : [];
  const needsReview = run.status === 'partial' || warnings.length > 0;
  return <section className="call-report" aria-label="Generated call report">
    <div className="review-section-heading"><h3>Call summary</h3><span>AI-generated{needsReview ? ' · Needs review' : ''}</span></div>
    <p className="call-report-summary">{summary}</p>
    <div className="call-report-meta">
      {run.intent && <div><span>Caller intent · model reported</span><strong>{run.intent}</strong></div>}
      {run.outcome && <div><span>Outcome · model reported</span><strong>{run.outcome}</strong></div>}
      {run.sentiment && <div><span>Sentiment · model reported</span><strong>{run.sentiment}</strong></div>}
    </div>
    {warnings.length > 0 && <div className="call-report-warnings">
      <h4>{warnings.length} {warnings.length === 1 ? 'evaluation warning' : 'evaluation warnings'}</h4>
      <p>The evaluator flagged these issues for review. They do not establish a violation by the call agent.</p>
      <ul>{warnings.map((message, index) => <li key={index}>{message}</li>)}</ul>
      <button className="evidence-jump" onClick={onChecks}>View evaluation checks <ArrowUpRight size={13} /></button>
    </div>}
  </section>;
}

export function CallSummary({ run }: { run: Run }) {
  const report = readReliability(run.evaluation?.reliability);
  const verdict = reviewVerdict(run);
  const noPolicies = report !== null && report.findings.length === 0 && report.policy_snapshots.length === 0 && report.checked_rule_ids.length === 0;
  const title = verdict.kind === 'insufficient' || noPolicies ? 'Policy checks unavailable' : verdict.label;
  const detail = noPolicies ? 'No supported company policies were enabled for this assessment.' : verdict.detail;
  const Icon = verdict.kind === 'confirmed' ? ShieldAlert : verdict.kind === 'review' ? TriangleAlert : verdict.kind === 'no_matches' ? CheckCircle2 : FileQuestion;
  return <section className={`call-summary call-summary-${verdict.kind}`} aria-label="Call assessment">
    <Icon size={20} aria-hidden="true" />
    <div><h2>{title}</h2><p>{detail}</p>
      {run.status === 'partial' && <p className="call-processing-note">Evaluation requires review. See Evaluation checks.</p>}
      {run.status === 'failed' && <p className="call-processing-note">Processing failed. See Evaluation checks for the stored errors.</p>}
      {run.run_id.startsWith('demo-') && <p className="call-processing-note">Synthetic scenario · fictional transcript and policies.</p>}
    </div>
    {noPolicies && <Link className="call-summary-link" href="/settings">Set up policies <ArrowUpRight size={14} /></Link>}
  </section>;
}

export function FindingsPanel({ run, onEvidence }: { run: Run; onEvidence: (turn: number) => void }) {
  const report = readReliability(run.evaluation?.reliability);
  const example = run.evaluation?.synthetic_contradiction;
  const source = example && Number.isInteger(example.source_turn) ? run.transcript_speakers?.[example.source_turn] : undefined;
  const claim = example && Number.isInteger(example.claim_turn) ? run.transcript_speakers?.[example.claim_turn] : undefined;
  if (run.run_id?.startsWith('demo-') && run.provider === 'synthetic' && run.evaluation?.data_source === 'synthetic_demo'
      && example && source?.role === 'customer' && claim?.role === 'agent'
      && typeof source.text === 'string' && typeof claim.text === 'string') {
    return <article className="finding-card finding-card-needs_review">
      <div className="finding-meta"><span className="review-badge review-badge-review">Synthetic hallucination example</span><span className="finding-certainty">Hand-labeled fixture</span></div>
      <h3>Contradictory receipt total</h3><p>The agent claim conflicts with the supplied receipt statement in this authored example. No live model detector ran, and this is not a verified claim about a real call.</p>
      <div className="finding-evidence"><span className="review-eyebrow">Supplied fixture evidence</span><blockquote>{source.text}</blockquote><button className="evidence-jump" onClick={()=>onEvidence(example.source_turn)}>Turn {example.source_turn+1} · Customer <ArrowUpRight size={13}/></button></div>
      <div className="finding-evidence"><span className="review-eyebrow">Conflicting agent claim</span><blockquote>{claim.text}</blockquote><button className="evidence-jump" onClick={()=>onEvidence(example.claim_turn)}>Turn {example.claim_turn+1} · Agent <ArrowUpRight size={13}/></button></div>
    </article>;
  }
  return (
    <div className="review-stack">
      {!report ? (
        <section className="review-empty"><FileQuestion size={28} /><h3>No structured assessment stored</h3><p>This call has no stored policy assessment. You can still review its conversation. Technical evaluator output is under Evaluation checks.</p><Link className="btn btn-ghost" href="/settings">Configure policies <ArrowUpRight size={14} /></Link></section>
      ) : (
        <>
          {report.findings.length > 0 && <div className="review-section-heading"><h3>Policy findings</h3><span>{report.findings.length} recorded</span></div>}
          {report.findings.length === 0 && <section className="call-no-findings"><FileQuestion size={22} aria-hidden="true" /><h3>No policy findings recorded</h3><p>{report.status === 'assessed' && report.checked_rule_ids.length > 0 ? 'No configured rule matched. This does not establish overall compliance.' : 'Policy assessment is incomplete. This does not establish compliance.'}</p></section>}
          {report.findings.map(finding => {
            const policy = report.policy_snapshots.find(item => item.id === finding.policy_id);
            return <article className={`finding-card finding-card-${finding.status}`} key={finding.id}>
              <div className="finding-meta"><span className={`review-badge ${finding.status === 'confirmed' ? 'review-badge-confirmed' : 'review-badge-review'}`}>{categoryLabel(finding.category)}</span><span className="finding-certainty">{finding.status === 'confirmed' ? 'Confirmed rule match' : 'Needs review'}</span><span className={`finding-severity severity-${finding.severity}`}>{finding.severity}</span></div>
              <h3>{finding.title}</h3><p>{finding.explanation}</p>
              <div className="finding-evidence">
                <span className="review-eyebrow">Transcript evidence</span>
                {finding.evidence.length === 0 ? <p>No attributable transcript excerpt is available.</p> : finding.evidence.map((item, index) => <div key={`${item.turn_index}-${index}`}><blockquote>{item.quote}</blockquote><button className="evidence-jump" onClick={() => onEvidence(item.turn_index)}>Turn {item.turn_index + 1} · {item.speaker_role}{item.role_source === 'model_inference' ? ' · inferred role' : ''}<ArrowUpRight size={13} /></button></div>)}
              </div>
              {policy && <div className="finding-policy"><span className="review-eyebrow">Policy applied</span><strong>{policy.title}</strong><p>{policy.text}</p><span className="policy-version">Snapshot {policy.version.slice(0, 12)}</span></div>}
              {finding.missing_evidence.length > 0 && <div className="finding-missing"><Info size={15} aria-hidden="true" /><span>Missing evidence: {finding.missing_evidence.map(item => item.replaceAll('_', ' ')).join(', ')}. No external action outcome is inferred.</span></div>}
            </article>;
          })}
          {report.limitations.length > 0 && <section className="review-limitations"><h3>Assessment scope and limitations</h3><ul>{report.limitations.map((limit, index) => <li key={index}>{limit}</li>)}</ul></section>}
        </>
      )}
    </div>
  );
}

export function SpeechPanel({ run }: { run: Run }) {
  const speech = readSpeech(run.evaluation?.speech_diagnostics);
  if (!speech || speech.source === 'unavailable') return <section className="review-empty"><FileQuestion size={28} /><h3>Speech diagnostics unavailable</h3><p>This call has no supported provider timing data. An audio recording or silence alone cannot establish a network fault.</p></section>;
  return <div className="review-stack">
    <div className="review-section-heading"><h3>Speech diagnostics</h3><span>Reported by Bolna</span></div>
    <p className="review-description">Component timings help locate delays. They do not establish a network fault or measure transcription accuracy.</p>
    <div className="diagnostic-grid">
      <Metric label="First audio" value={formatMetric(speech.time_to_first_audio_ms)} detail="Provider time to first audio" />
      <Metric label="Transcription" value={formatMetric(speech.transcriber_ms)} detail="Mean reported turn timing" />
      <Metric label="Response generation" value={formatMetric(speech.llm_ms)} detail="Mean reported turn timing" />
      <Metric label="Speech generation" value={formatMetric(speech.synthesizer_ms)} detail="Mean reported turn timing" />
    </div>
    <div className="review-section-heading"><h3>Conversation flow</h3><span>Provider observations</span></div>
    <div className="diagnostic-grid">
      <Metric label="Total interruptions" value={formatMetric(speech.total_interruptions, 'count')} detail="Reported interruption events" />
      <Metric label="Agent interrupted caller" value={formatMetric(speech.agent_interrupted_user_count, 'count')} detail="Direction reported by provider" />
      <Metric label="Caller interrupted agent" value={formatMetric(speech.user_interrupted_agent_count, 'count')} detail="Direction reported by provider" />
      <Metric label="Call ended by" value={speech.hangup_by || 'Unavailable'} detail={speech.hangup_reason || 'Hangup reason unavailable'} />
    </div>
    {speech.limitations.length > 0 && <section className="review-limitations"><h3>What these metrics cannot tell us</h3><ul>{speech.limitations.map((limit, index) => <li key={index}>{limit}</li>)}</ul></section>}
  </div>;
}

function Metric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return <div className="diagnostic-card"><span>{label}</span><strong>{value}</strong><p>{detail}</p></div>;
}
