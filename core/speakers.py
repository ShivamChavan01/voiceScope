"""Preserve explicit transcript roles without inferring personal identity."""

import re

ROLE_LABELS = {'agent': 'Agent', 'customer': 'Customer', 'other': 'Other', 'unknown': 'Unknown'}
_PREFIX = re.compile(
    r'^\s*(assistant|agent|ai|bot|rep|support|customer|user|caller|speaker\s*\d+|caller\s*\d+|[a-z][a-z_-]{0,30})\s*:\s*(.*)$',
    re.IGNORECASE,
)
_AGENT_PREFIXES = {'assistant', 'agent', 'ai', 'bot', 'rep', 'support'}
_CUSTOMER_PREFIXES = {'customer', 'user', 'caller'}


def parse_speaker_turns(transcript: str) -> list[dict]:
    """Parse line-delimited attributed text; leave unlabelled transcripts intact."""
    turns: list[dict] = []
    identities: dict[str, int] = {}
    for line in transcript.splitlines():
        match = _PREFIX.match(line)
        if not match:
            if turns:
                turns[-1]['text'] += '\n' + line
            elif line.strip():
                return []
            continue
        prefix, text = match.groups()
        prefix = prefix.lower()
        role = 'agent' if prefix in _AGENT_PREFIXES else 'customer' if prefix in _CUSTOMER_PREFIXES else 'unknown'
        identity = role if role != 'unknown' else prefix
        speaker = identities.setdefault(identity, len(identities))
        turns.append({
            'speaker': speaker, 'text': text, 'role': role,
            'label': ROLE_LABELS[role] if role != 'unknown' else f'Speaker {speaker}',
            'role_source': 'transcript_label' if role != 'unknown' else 'unknown',
        })
    return turns


def attributed_transcript(turns: list[dict]) -> str:
    """Keep inferred role attribution visible while retaining original raw text."""
    lines = []
    for turn in turns:
        role = turn.get('role', 'unknown')
        label = ROLE_LABELS.get(role, 'Unknown')
        if role == 'unknown':
            label = f"Speaker {turn['speaker']} (role unknown)"
        elif turn.get('role_source') == 'model_inference':
            label += ' (inferred)'
        lines.append(f"{label}: {turn['text']}")
    return '\n'.join(lines)
