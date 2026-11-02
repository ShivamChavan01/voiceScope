import type { RunSummary } from './api';

export function parseRunSummary(value: unknown): RunSummary {
  const invalid = () => new Error('Overview API returned an invalid response. Retry loading the overview.');
  const count = (v: unknown): v is number => typeof v === 'number' && Number.isSafeInteger(v) && v >= 0;
  const rate = (v: unknown): v is number | null => v === null || (typeof v === 'number' && Number.isFinite(v) && v >= 0 && v <= 1);
  if (typeof value !== 'object' || value === null || Array.isArray(value)) throw invalid();
  if (!('total_calls' in value) || !count(value.total_calls)
      || !('real_calls' in value) || !count(value.real_calls)
      || !('demo_calls' in value) || !count(value.demo_calls)
      || !('completed_calls' in value) || !count(value.completed_calls)
      || !('evaluated_real_calls' in value) || !count(value.evaluated_real_calls)
      || !('flagged_calls' in value) || !count(value.flagged_calls)
      || !('escalated_calls' in value) || !count(value.escalated_calls)
      || !('confirmed_policy_calls' in value) || !count(value.confirmed_policy_calls)
      || !('review_calls' in value) || !count(value.review_calls)
      || !('evaluated_policy_calls' in value) || !count(value.evaluated_policy_calls)
      || !('legacy_calls' in value) || !count(value.legacy_calls)
      || !('hallucination_rate' in value) || !rate(value.hallucination_rate)
      || !('escalation_rate' in value) || !rate(value.escalation_rate)
      || !('scope' in value) || value.scope !== 'all_time_persisted_runs') throw invalid();
  if (value.total_calls !== value.real_calls + value.demo_calls
      || value.completed_calls > value.total_calls || value.evaluated_real_calls > value.real_calls
      || value.flagged_calls > value.evaluated_real_calls || value.escalated_calls > value.evaluated_real_calls
      || value.confirmed_policy_calls > value.real_calls || value.review_calls > value.real_calls
      || value.evaluated_policy_calls > value.real_calls || value.legacy_calls > value.real_calls) throw invalid();
  return { total_calls: value.total_calls, real_calls: value.real_calls, demo_calls: value.demo_calls,
    completed_calls: value.completed_calls, evaluated_real_calls: value.evaluated_real_calls,
    flagged_calls: value.flagged_calls, escalated_calls: value.escalated_calls,
    hallucination_rate: value.hallucination_rate, escalation_rate: value.escalation_rate,
    confirmed_policy_calls: value.confirmed_policy_calls, review_calls: value.review_calls,
    evaluated_policy_calls: value.evaluated_policy_calls, legacy_calls: value.legacy_calls, scope: value.scope };
}
