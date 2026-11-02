import type { RunSummary } from '../lib/api';

export function OverviewCoverage({ summary }: { summary: Pick<RunSummary, 'real_calls' | 'legacy_calls'> }) {
  return <span>Real inputs without a structured policy assessment: {summary.legacy_calls} of {summary.real_calls}. Synthetic examples are excluded from assessment counts.</span>;
}
