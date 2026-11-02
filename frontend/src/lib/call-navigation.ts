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
