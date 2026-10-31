"""Bounded, deterministic checks over attributed transcript turns and explicit policies."""

import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PolicyKind = Literal['no_same_day_refund_guarantee', 'honor_escalation_request']


def _policy_supported(kind: PolicyKind, text: str) -> bool:
    policy = " ".join(text.lower().split()).rstrip('.!')
    if kind == 'no_same_day_refund_guarantee':
        return bool(re.fullmatch(
            r'(?:agents?|support agents?) (?:cannot|must not|must never|never|may not) '
            r'(?:guarantee|promise) (?:a |any |the )?same[ -]day refunds?'
            r'(?: under any circumstances)?', policy,
        ))
    return bool(re.fullmatch(
        r'(?:if|when) (?:a |the )?(?:customer|caller) requests (?:a |the )?'
        r'(?:human|human agent|supervisor|manager),? agents? (?:must|shall) '
        r'honor (?:the|that) request(?: immediately)?', policy,
    ) or re.fullmatch(
        r'honor (?:all )?(?:customer|caller) requests to (?:speak|talk) '
        r'(?:to|with) (?:a |the )?(?:human|human agent|supervisor|manager)(?: immediately)?', policy,
    ))


class PolicyRule(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid')

    id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=200)
    kind: PolicyKind
    text: str = Field(min_length=1, max_length=10000)
    enabled: bool = Field(default=True, strict=True)
    version: str = ''

    @field_validator('id', 'title', 'text', mode='before')
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator('id')
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]*', value):
            raise ValueError('Policy ID must contain only letters, numbers, dots, colons, underscores or hyphens')
        return value

    @model_validator(mode='after')
    def validate_rule(self):
        if not _policy_supported(self.kind, self.text):
            raise ValueError('Policy text must explicitly express the selected unconditional supported rule')
        payload = json.dumps([self.kind, self.text], ensure_ascii=False, separators=(',', ':'))
        object.__setattr__(self, 'version', hashlib.sha256(payload.encode()).hexdigest())
        return self


class PolicySnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    kind: PolicyKind
    text: str
    version: str


class Evidence(BaseModel):
    turn_index: int = Field(ge=0)
    speaker_role: str
    role_source: str
    quote: str = Field(min_length=1)


class Finding(BaseModel):
    id: str
    category: Literal['policy_violation', 'unverified_claim', 'insufficient_evidence']
    status: Literal['confirmed', 'needs_review']
    severity: Literal['high', 'medium', 'info']
    title: str
    explanation: str
    evidence: list[Evidence] = Field(default_factory=list)
    policy_id: str | None = None
    missing_evidence: list[str] = Field(default_factory=list)


class ReliabilityReport(BaseModel):
    schema_version: Literal['1'] = '1'
    status: Literal['assessed', 'insufficient_evidence'] = 'insufficient_evidence'
    checked_rule_ids: list[str] = Field(default_factory=list)
    policy_snapshots: list[PolicySnapshot] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


_SENTENCE = re.compile(r'[^.!?\n]+(?:[.!?]+|$)')
_NEGATED_OR_REPORTED = re.compile(
    r"\b(?:not|never|cannot|can't|don't|doesn't|won't|wouldn't|no one|nobody|"
    r"if|unless|might|could|would|example|quoted?|said|says|told)\b", re.IGNORECASE,
)
_QUOTED = re.compile(r'(?:^|\s)["“”]|(?:^|\s)\'[^\']+\'')
_COMPLETED = re.compile(
    r"\b(?:(?:i|we)(?:['’]ve|\s+have)?\s+(?:(?:already|just|successfully)\s+){0,2}"
    r"(?:processed|completed|issued|sent)\s+(?:(?:your|the|a)\s+)?refund\b|"
    r"your\s+refund\s+(?:has\s+been|is|was)\s+(?:processed|completed|issued|sent)\b)",
    re.IGNORECASE,
)
_REQUEST = re.compile(
    r"\b(?:(?:i\s+(?:want|need|would like)|(?:can|could|may)\s+i)\b.{0,55}\b(?:speak|talk)\b|"
    r"(?:please\s+)?(?:transfer|connect)\s+me\b).{0,50}\b(?:human|supervisor|manager|person|representative)\b",
    re.IGNORECASE,
)
_REFUSAL = re.compile(
    r"\b(?:(?:i|we)\s+(?:cannot|can't|won't|will not)\s+(?:transfer|connect|escalate)\b|"
    r"you\s+(?:cannot|can't|will not|won't)\s+(?:speak|talk)\b.{0,30}\b(?:human|supervisor|manager|person)\b)",
    re.IGNORECASE,
)
_TRANSFER_OFFER = re.compile(
    r"\b(?:(?:i|we)(?:'ll|\s+will)|let me)\s+(?:transfer|connect)\s+you\b|"
    r"\bi(?:'m| am)\s+(?:transferring|connecting)\s+you\b", re.IGNORECASE,
)


def _sentences(text: str) -> list[str]:
    return [match.group().strip() for match in _SENTENCE.finditer(text) if match.group().strip()]


def _direct_statement(sentence: str) -> bool:
    return not ('?' in sentence or _NEGATED_OR_REPORTED.search(sentence) or _QUOTED.search(sentence))


def _same_day_guarantee(sentence: str) -> bool:
    normalized = sentence.lower().replace('’', "'")
    if '?' in sentence or _QUOTED.search(sentence) or re.search(
        r"\b(?:if|unless|might|could|would|example|quoted?|said|says|told|aren't|isn't|unavailable|impossible|fail|except)\b", normalized,
    ):
        return False
    passive = re.search(r'\byour refund (?:is )?guaranteed (?:to arrive )?today\b', normalized)
    if passive:
        return _direct_statement(sentence[:passive.end()])
    match = re.search(r'\b(?:i|we) (?:can )?(?:guarantee|promise) (?:that )?', normalized)
    if not match:
        return False
    outcome = normalized[match.end():]
    promise = re.match(
        r'(?:(?:a|your|the) )?same[ -]day refunds?\b|'
        r'(?:(?:a|your|the) )?refund (?:today\b|will (?:arrive|be credited|be returned|be paid) today\b)|'
        r"you(?:'ll| will) (?:get|receive|have) (?:your |the |a )?refund\b.{0,45}\btoday\b",
        outcome,
    )
    # Negation must apply to the promise, not a later contrasting time clause.
    return bool(promise and _direct_statement(sentence[:match.end() + promise.end()]))


def _refund_completion(sentence: str) -> bool:
    if not _direct_statement(sentence) or re.search(
        r'\b(?:only after|after approval|upon approval|once approved|when approved|subject to|pending approval)\b',
        sentence, re.IGNORECASE,
    ):
        return False
    return any(not re.match(
        r'\s+(?:request|application|form|paperwork|receipt|confirmation|submission|case|approval|authorization)\b',
        sentence[match.end():], re.IGNORECASE,
    ) for match in _COMPLETED.finditer(sentence))


def _targeted_transfer_offer(sentence: str) -> bool:
    return any(re.match(
        r'\s+(?:directly )?(?:to|with) (?:a |the |our )?(?:human|human agent|supervisor|manager|person|representative)\b',
        sentence[match.end():], re.IGNORECASE,
    ) for match in _TRANSFER_OFFER.finditer(sentence))


def _refuses_requested_transfer(sentence: str) -> bool:
    if ('?' in sentence or _QUOTED.search(sentence) or re.search(
        r'\b(?:said|says|told|example|quote|if|unless|might|would|could)\b', sentence, re.IGNORECASE,
    )):
        return False
    for match in _REFUSAL.finditer(sentence):
        refusal = sentence[match.end():].split(',')[0].split(';')[0]
        if re.fullmatch(r'\s*(?:you(?:\s+(?:directly|now|today|right now))?)?\s*[.!]?', refusal, re.IGNORECASE):
            return True
        if re.match(
            r'\s+(?:you\s+)?(?:directly\s+)?(?:to|with)\s+(?:a\s+|the\s+|our\s+)?'
            r'(?:human|supervisor|manager|person|representative)\b', refusal, re.IGNORECASE,
        ):
            return True
    return False


def _evidence(index: int, turn: dict, quote: str) -> Evidence:
    return Evidence(
        turn_index=index, speaker_role=turn.get('role') or 'unknown',
        role_source=turn.get('role_source') or 'unknown', quote=quote,
    )


def _finding_id(kind: str, policy_id: str | None, evidence: list[Evidence]) -> str:
    payload = [kind, policy_id, [(item.turn_index, item.quote) for item in evidence]]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()[:20]


def _policy_finding(rule: PolicyRule, title: str, explanation: str, evidence: list[Evidence]) -> Finding:
    confirmed = all(item.role_source == 'transcript_label' and item.speaker_role in ('agent', 'customer') for item in evidence)
    return Finding(
        id=_finding_id(rule.kind, rule.id, evidence), category='policy_violation',
        status='confirmed' if confirmed else 'needs_review', severity='high' if confirmed else 'medium',
        title=title, explanation=explanation + (
            '' if confirmed else ' Speaker attribution is inferred or unknown, so confirm the roles before concluding a violation.'
        ), evidence=evidence, policy_id=rule.id,
        missing_evidence=[] if confirmed else ['confirmed_speaker_roles'],
    )


def evaluate_reliability(turns: list[dict], policies: list[PolicyRule]) -> ReliabilityReport:
    """Evaluate only supported explicit rules; missing action results never prove failure."""
    active = [policy for policy in policies if policy.enabled]
    result = ReliabilityReport(
        checked_rule_ids=[policy.id for policy in active],
        policy_snapshots=[PolicySnapshot(**policy.model_dump(exclude={'enabled'})) for policy in active],
        limitations=['Checks cover explicit English-language patterns only; no matches do not establish overall compliance.'],
    )
    valid_turns = [
        (index, turn) for index, turn in enumerate(turns)
        if isinstance(turn, dict) and isinstance(turn.get('text'), str) and turn['text'].strip()
    ]
    if not valid_turns:
        result.checked_rule_ids = []
        result.limitations.append('No usable transcript turns were supplied.')
        result.findings.append(Finding(
            id=_finding_id('missing_transcript', None, []), category='insufficient_evidence',
            status='needs_review', severity='info', title='Transcript unavailable',
            explanation='There are no usable transcript turns to assess.', missing_evidence=['transcript'],
        ))
        return result
    if not active:
        result.limitations.append('No supported company policies are enabled.')
    elif any(turn.get('role') == 'agent' for _, turn in valid_turns):
        result.status = 'assessed'
    else:
        result.limitations.append('No agent-attributed turns are available to complete policy assessment.')
    if any(turn.get('role') not in ('agent', 'customer') for _, turn in valid_turns):
        result.limitations.append('Some turns have unknown or other speaker roles; attributed matches require review.')

    for index, turn in valid_turns:
        if turn.get('role') not in ('agent', 'unknown', None):
            continue
        for sentence in _sentences(turn['text']):
            if _refund_completion(sentence):
                evidence = [_evidence(index, turn, sentence)]
                result.findings.append(Finding(
                    id=_finding_id('refund_completion', None, evidence), category='unverified_claim',
                    status='needs_review', severity='medium', title='Refund completion is unverified',
                    explanation='The speaker claims a refund completed. No external action result is available to verify it; this does not mean the refund failed.',
                    evidence=evidence, missing_evidence=['action_result'],
                ))
            if not _same_day_guarantee(sentence):
                continue
            for rule in active:
                if rule.kind == 'no_same_day_refund_guarantee':
                    result.findings.append(_policy_finding(
                        rule, 'Forbidden same-day refund guarantee',
                        'An explicit same-day refund guarantee contradicts this enabled unconditional policy.',
                        [_evidence(index, turn, sentence)],
                    ))

    for rule in active:
        if rule.kind != 'honor_escalation_request':
            continue
        request: Evidence | None = None
        for index, turn in valid_turns:
            role = turn.get('role') or 'unknown'
            for sentence in _sentences(turn['text']):
                if role in ('customer', 'unknown'):
                    if re.search(r"\b(?:never mind|don't need|do not need)\b", sentence, re.IGNORECASE):
                        request = None
                    elif _REQUEST.search(sentence) and not re.search(
                        r"\b(?:don't|do not|not|never|said|says|example|quote|if|unless)\b", sentence, re.IGNORECASE,
                    ) and not _QUOTED.search(sentence):
                        request = _evidence(index, turn, sentence)
                if role in ('agent', 'unknown') and request and index > request.turn_index:
                    if _targeted_transfer_offer(sentence):
                        request = None
                    elif _refuses_requested_transfer(sentence):
                        result.findings.append(_policy_finding(
                            rule, 'Requested escalation was explicitly refused',
                            'The caller explicitly requested a human or supervisor and a later agent statement explicitly refused that request.',
                            [request, _evidence(index, turn, sentence)],
                        ))
                        request = None
                    elif _TRANSFER_OFFER.search(sentence):
                        request = None
    return result
