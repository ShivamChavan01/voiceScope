import { disagreementParts, audioTime, sttMetric, type STTReview } from '../lib/stt-quality';

export function STTResults({ review, onSeek }: { review: STTReview; onSeek: (time: number) => void }) {
  const metric = sttMetric(review);
  const synthetic = review.reference_source === 'synthetic';
  return <div className="review-stack">
    <section className="review-verdict"><div><h2>{metric.value}</h2><p>{metric.label} · {review.status}</p>{review.reference_human_verified && <p>Verified by {review.verified_by}</p>}</div></section>
    {review.edits && review.metric_value !== null && <p className="review-description">{review.edits.substitutions} substitutions · {review.edits.deletions} deletions · {review.edits.insertions} insertions / {review.edits.reference_words} reference words</p>}
    {review.metric_value !== null && <p className="review-description">(Substitutions + deletions + insertions) ÷ reference words. {synthetic ? 'This compares authored synthetic fixtures, not measured recognizer accuracy.' : review.reference_human_verified ? 'WER uses the submitted human-verified reference.' : 'This estimates disagreement with an automatic reference, not transcription accuracy.'}</p>}
    {review.alignment && <div className="review-note"><div><strong>Automatic whole-call alignment</strong><p>Inferred speaker mapping: {Object.entries(review.alignment.speaker_roles).map(([speaker,role])=>`${speaker} → ${role}`).join(' · ')}.</p><p>Audio positions are estimated from the Deepgram reference. Original Bolna timestamps remain unavailable. Every discrepancy needs human review.</p></div></div>}
    {review.metric_value === null && <p className="review-description">Unavailable: required audio, speaker coverage, reference, or timing evidence has not been established. Review the reasons below.</p>}
    {review.issues.length > 0 && <div className="review-note"><ul>{review.issues.map(issue => <li key={issue}>{issue}</li>)}</ul></div>}
    {(review.findings.length > 0 || review.status === 'completed') && <div className="review-section-heading"><h3>Transcript discrepancies</h3><span>{review.findings.length} findings · {review.compared_groups} {review.alignment?'speaker comparisons':'aligned intervals'}</span></div>}
    {review.status === 'completed' && !review.findings.length && <p className="review-description">No differences were found in the compared intervals. Model agreement does not prove accuracy.</p>}
    {review.findings.map((finding, index) => { const parts=disagreementParts(finding.bolna_text,finding.reference_text); return <article className="finding-card" key={index}>
      <div className="finding-meta"><span className={`review-badge review-badge-${finding.status === 'confirmed_error' ? 'confirmed' : 'review'}`}>{finding.status === 'confirmed_error' ? 'Confirmed STT error' : 'Needs human review'}</span><span className={`finding-severity severity-${finding.severity}`}>{finding.severity}</span></div>
      <h3>{finding.category.map(item => item.replaceAll('_', ' ')).join(', ')}</h3><p>{synthetic ? 'The authored synthetic texts disagree. This illustrates the review workflow; no recognizer error is established.' : finding.explanation}</p>
      {finding.start === null ? <p className="review-description">Timestamp unavailable</p> : <button className="evidence-jump" onClick={() => { if (finding.start !== null) onSeek(finding.start); }}>Listen {finding.timing_basis==='reference_anchors'?'near':'at'} {audioTime(finding.start)} · {finding.role}</button>}
      <div className="benchmark-comparison"><section><h4>{synthetic ? 'Synthetic source transcript' : 'Bolna transcript'}</h4><p className="stt-quote">{finding.bolna_text ? parts[0].map((part,i)=>part.changed?<mark className="stt-disagreement" key={i}>{part.text}</mark>:part.text) : 'No words in this interval'}</p></section><section><h4>{synthetic ? 'Synthetic comparison fixture' : review.reference_human_verified ? 'Human-verified reference' : 'Automatic reference'}</h4><p className="stt-quote">{finding.reference_text ? parts[1].map((part,i)=>part.changed?<mark className="stt-disagreement" key={i}>{part.text}</mark>:part.text) : 'No words in this interval'}</p></section></div>
      <p className="review-description">{synthetic ? 'Fixture provenance only; no model confidence was measured.' : `Confidence: ${finding.confidence}. ${finding.confidence_basis}`}</p>
    </article>; })}
    <details className="review-limitations stt-comparison-setup"><summary>Scoring details and limitations</summary><ul>{review.limitations.map(limit => <li key={limit}>{limit}</li>)}</ul></details>
  </div>;
}
