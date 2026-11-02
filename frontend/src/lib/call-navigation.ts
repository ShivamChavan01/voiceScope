export function callNavigationUrl(current: string, callId: string | null): string {
  const url = new URL(current);
  if (callId === null) url.searchParams.delete('call');
  else url.searchParams.set('call', callId);
  return url.pathname + url.search + url.hash;
}

export function syntheticScenarioNote(id: string): string | null {
  const copies: Record<string, string> = {
    'demo-review-compliant': 'demo-staging-compliant',
    'demo-review-promise': 'demo-staging-policy',
    'demo-review-escalation': 'demo-staging-escalation',
  };
  return Object.hasOwn(copies, id) ? `Earlier synthetic sample: same authored conversation as ${copies[id]}. Preserved for existing links.` : null;
}

export type RunFilters = { search: string; status: string; assessment: string };

export function runFiltersFromUrl(current: string): RunFilters {
  const params = new URL(current).searchParams;
  return { search: params.get('search') || '', status: params.get('status') || '', assessment: params.get('assessment') || '' };
}

export function runFiltersUrl(current: string, filters: RunFilters): string {
  const url = new URL(current);
  for (const [key, value] of Object.entries(filters)) {
    if (value) url.searchParams.set(key, value);
    else url.searchParams.delete(key);
  }
  return url.pathname + url.search + url.hash;
}
