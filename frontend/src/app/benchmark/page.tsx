'use client';

import { useEffect, useState } from 'react';
import { BenchmarkResults } from '@/components/benchmark-results';
import { getBenchmark, getPolicyBenchmark, type BenchmarkSummary, type PolicyBenchmark } from '@/lib/api';

type State = { kind: 'loading' } | { kind: 'error'; message: string } | { kind: 'ready'; result: PolicyBenchmark; legacy: BenchmarkSummary | null };

export default function BenchmarkPage() {
  const [state, setState] = useState<State>({ kind: 'loading' });
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let active = true;
    Promise.all([getPolicyBenchmark(), getBenchmark().catch(() => null)])
      .then(([result, legacy]) => { if (active) setState({ kind: 'ready', result, legacy }); })
      .catch(error => { if (active) setState({ kind: 'error', message: error instanceof Error ? error.message : 'Benchmark could not be run.' }); });
    return () => { active = false; };
  }, [reload]);
  const run = () => { setState({ kind: 'loading' }); setReload(value => value + 1); };
  return <>
    <div className="review-page-header"><div><div className="review-eyebrow">Evaluation tests</div><h1 className="page-title">Policy detector benchmark</h1><p className="page-subtitle">Synthetic test conversations with fictional rules. These test the detector, not your saved calls.</p></div><button className="btn btn-primary" onClick={run} disabled={state.kind === 'loading'}>{state.kind === 'loading' ? 'Running benchmark…' : 'Run benchmark'}</button></div>
    {state.kind === 'loading' ? <div className="review-empty" role="status">Running labeled policy cases…</div> : state.kind === 'error' ? <div className="review-error" role="alert"><strong>Benchmark unavailable</strong><p>{state.message}</p><button className="btn btn-ghost" onClick={run}>Retry benchmark</button></div> : <>
      <BenchmarkResults benchmark={state.result} />
      <details className="benchmark-case benchmark-legacy"><summary>Legacy harness consistency checks</summary><p>These checks use fixture answers as evaluator input. Their consistency score does not measure detector accuracy. Optimizer weights are not applied to the production harness.</p>{state.legacy ? <p>{state.legacy.total_tests} fixture cases · mean consistency {state.legacy.avg_truth_score.toFixed(2)} · hallucination detection {state.legacy.hallucination_accuracy === null ? 'not measured' : `${(state.legacy.hallucination_accuracy * 100).toFixed(1)}%`}</p> : <p>Legacy checks unavailable. Policy results above remain independent.</p>}</details>
    </>}
  </>;
}
