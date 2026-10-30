import type { BenchmarkFinding, PolicyBenchmark } from '../lib/api';

function percentage(value: number | null) {
  return value === null ? 'Not measured' : `${(value * 100).toFixed(1)}%`;
}

function Labels({ findings }: { findings: BenchmarkFinding[] }) {
  if (!findings.length) return <span>No finding</span>;
  return <ul>{findings.map((finding, index) => <li key={index}>
    <strong>{finding.category.replaceAll('_', ' ')}</strong> · {finding.status.replaceAll('_', ' ')}
    <span>{finding.policy_kind?.replaceAll('_', ' ') || 'No policy required'} · {finding.severity}</span>
    <span>{finding.turn_indices.length ? `Evidence turns ${finding.turn_indices.map(turn => turn + 1).join(', ')}` : 'No transcript evidence'}</span>
    {finding.missing_evidence.length > 0 && <span>Missing: {finding.missing_evidence.map(item => item.replaceAll('_', ' ')).join(', ')}</span>}
  </li>)}</ul>;
}

export function BenchmarkResults({ benchmark }: { benchmark: PolicyBenchmark }) {
  return <div className="review-stack">
    <div className="review-stat-grid">
      <div className="review-stat"><span>Exact case matches</span><strong>{benchmark.passed_cases}/{benchmark.total_cases}</strong><p>{percentage(benchmark.exact_case_accuracy)} · includes challenge cases</p></div>
      <div className="review-stat"><span>Finding precision</span><strong>{percentage(benchmark.metrics.precision)}</strong><p>{benchmark.metrics.false_positives} unexpected findings</p></div>
      <div className="review-stat"><span>Finding recall</span><strong>{percentage(benchmark.metrics.recall)}</strong><p>{benchmark.metrics.false_negatives} missed findings</p></div>
      <div className="review-stat"><span>Finding F1</span><strong>{percentage(benchmark.metrics.f1)}</strong><p>Exact finding labels and source turns</p></div>
    </div>
    <div className="review-note">Synthetic, manually labeled regression cases. Supported patterns: {benchmark.supported_passed}/{benchmark.supported_cases}. Challenge paraphrases: {benchmark.challenge_passed}/{benchmark.challenge_cases}. These results do not estimate production hallucination accuracy.</div>
    <div className="table-wrap"><div className="table-scroll"><table className="benchmark-metrics-table"><thead><tr><th>Category</th><th>Correct findings</th><th>Unexpected</th><th>Missed</th><th>Precision</th><th>Recall</th></tr></thead><tbody>{Object.entries(benchmark.by_category).map(([category, metrics]) => <tr key={category}><td>{category.replaceAll('_', ' ')}</td><td>{metrics.true_positives}</td><td>{metrics.false_positives}</td><td>{metrics.false_negatives}</td><td>{percentage(metrics.precision)}</td><td>{percentage(metrics.recall)}</td></tr>)}</tbody></table></div></div>
    <div className="review-section-heading"><h2>Case results</h2><span>{benchmark.total_cases - benchmark.passed_cases} mismatches</span></div>
    <div className="benchmark-cases">{benchmark.results.map(result => <details className={`benchmark-case ${result.passed ? '' : 'benchmark-case-failed'}`} key={result.id} open={!result.passed}>
      <summary><span className={`review-badge review-badge-${result.passed ? 'no_matches' : 'review'}`}>{result.passed ? 'Match' : 'Mismatch'}</span><strong>{result.name}</strong><span>{result.scope === 'supported_patterns' ? 'Rule check' : 'Wording challenge'}</span></summary>
      <p className="benchmark-purpose">{result.purpose}</p>
      <div className="benchmark-source"><h3>Synthetic test conversation</h3>{result.turns.length ? result.turns.map((turn, index) => <p key={index}><strong>{index + 1} · {turn.role}</strong>{turn.role_source !== 'transcript_label' && <span> · {turn.role_source.replaceAll('_', ' ')}</span>}<br />{turn.text}</p>) : <p>No transcript supplied.</p>}{result.policies.length > 0 ? <div className="benchmark-rules"><h3>Fictional rule under test</h3>{result.policies.map(policy => <p key={policy.id}>{policy.text}</p>)}</div> : <p className="benchmark-rule-note">No company policy is supplied. This case tests evidence handling rather than a company rule.</p>}</div>
      <div className="benchmark-comparison"><section><h3>Expected result</h3><p>Assessment: {result.expected_status.replaceAll('_', ' ')}</p><Labels findings={result.expected} /></section><section><h3>Detector result</h3><p>Assessment: {result.actual_status.replaceAll('_', ' ')}</p><Labels findings={result.actual} /></section></div>
      {result.evidence_errors.length > 0 && <ul className="review-messages">{result.evidence_errors.map((error, index) => <li key={index}>{error}</li>)}</ul>}
    </details>)}</div>
    <section className="review-limitations"><h3>Scope and reproducibility</h3><ul>{benchmark.limitations.map(limit => <li key={limit}>{limit}</li>)}</ul><p className="policy-version">Dataset v{benchmark.dataset_version} · SHA-256 {benchmark.dataset_sha256}</p></section>
  </div>;
}
