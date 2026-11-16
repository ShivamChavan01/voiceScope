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
    r"(?:the|your)\s+money\s+has\s+been\s+returned\s+to\s+your\s+card\b|"
    r"your\s+refund\s+(?:has\s+been|is|was)\s+(?:processed|completed|issued|sent)\b)",
    re.IGNORECASE,
)
_REQUEST = re.compile(
    r"\b(?:(?:i\s+(?:want|need|would like)|(?:can|could|may)\s+i|please\s+let\s+me)\b.{0,55}\b(?:speak|talk)\b|"
    r"(?:please\s+)?(?:transfer|connect)\s+me\b|i\s+(?:want|need)\s+(?:a|the)\s+).{0,50}\b(?:human|supervisor|manager|team\s+lead|person|representative)\b",
    re.IGNORECASE,
)
_REFUSAL = re.compile(
    r"\b(?:(?:i|we)\s+(?:will not|won't)\s+let\s+you\s+(?:speak|talk)\b.{0,30}\b(?:human|supervisor|manager|team\s+lead|person)\b|"
    r"(?:i|we)\s+(?:cannot|can't|won't|will not)\s+(?:transfer|connect|escalate)\b|"
    r"you\s+(?:cannot|can't|will not|won't)\s+(?:speak|talk)\b.{0,30}\b(?:human|supervisor|manager|team\s+lead|person)\b)",
    re.IGNORECASE,
)
_TRANSFER_OFFER = re.compile(
    r"\b(?:(?:i|we)(?:'ll|\s+(?:will|can))|let me)\s+(?:transfer|connect)\s+you\b|"
    r"\bi(?:'m| am)\s+(?:transferring|connecting)\s+you\b", re.IGNORECASE,
)


def _sentences(text: str) -> list[str]:
    return [match.group().strip() for match in _SENTENCE.finditer(text) if match.group().strip()]


def _direct_statement(sentence: str) -> bool:
    return not ('?' in sentence or _NEGATED_OR_REPORTED.search(sentence) or _QUOTED.search(sentence))


_CLOCK = r"(?:[1-9]|1[0-2]|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
_SAME_DAY = r"(?:today|same[ -]day|by (?:midnight|eod|end of (?:the )?day)|before (?:five|5)(?: (?:pm|p\.m\.))?)"
_RECEIPT = r"(?:arrive|reach you|hit your account|be credited|be returned|be paid)"
_HINGLISH_REFUND_GUARANTEE = re.compile(
    r'(?:main|mai|hum) guarantee (?:karta|karti|karte) (?:hoon|hun|hain) ki '
    r'aapka refund aaj mil (?:jayega|jaayega)[.!]?', re.IGNORECASE,
)
_PROMISE_TRANSCRIPTION = re.compile(r'\b(?:garuntee|guarentee)\b', re.IGNORECASE)


def _same_day_guarantee(sentence: str) -> bool:
    normalized = sentence.lower().replace('’', "'")
    if _HINGLISH_REFUND_GUARANTEE.fullmatch(' '.join(normalized.split())):
        return True
    if '?' in sentence or _QUOTED.search(sentence) or re.search(
        r"\b(?:if|unless|might|could|would|example|quoted?|said|says|told|aren't|isn't|unavailable|impossible|fail|except)\b", normalized,
    ):
        return False
    if re.search(
        r'\b(?:before ' + _CLOCK + r'(?: (?:pm|this evening))?|by (?:midnight|eod|end of (?:the )?day))'
        r'[, ]+(?:tomorrow|next \w+|on \w+)\b', normalized,
    ):
        return False
    passive = re.search(r'\byour refund (?:is )?guaranteed (?:to arrive )?' + _SAME_DAY + r'\b', normalized)
    if passive:
        return _direct_statement(sentence[:passive.end()])
    match = re.search(r'\b(?:i|we) (?:(?:can|will) )?(?:(?:guarantee|promise) |assure you )(?:that )?', normalized)
    if not match:
        return False
    outcome = normalized[match.end():]
    promise = re.match(
        r'(?:(?:a|your|the) )?same[ -]day refunds?\b|'
        r'(?:(?:a|your|the) )?(?:refund|money) (?:' + _SAME_DAY + r'\b|will ' + _RECEIPT + r' (?:by )?' + _SAME_DAY + r'\b)|'
        r"you(?:'ll| will) (?:get|receive|have) (?:your |the |a )?refund\b.{0,45}\btoday\b",
        outcome,
    )
    # Negation must apply to the promise, not a later contrasting time clause.
    return bool(promise and _direct_statement(sentence[:match.end() + promise.end()]))


def _uncertain_refund_guarantee(text: str) -> bool:
    parts = _sentences(text)
    for sentence in parts:
        normalized = _PROMISE_TRANSCRIPTION.sub('guarantee', sentence)
        if normalized != sentence and _same_day_guarantee(normalized):
            return True
    for timing, assurance in zip(parts, parts[1:]):
        if re.fullmatch(
            r'(?:(?:your|the|a) )?refund ' + _SAME_DAY + r'[.!]', timing, re.IGNORECASE,
        ) and re.fullmatch(r'(?:guaranteed|i (?:guarantee|promise) it)[.!]?', assurance, re.IGNORECASE):
            return True
    return False


def _contextual_guarantee_question(text: str) -> bool:
    # Require both questions to have one topic. Extra questions make assent ambiguous.
    questions = _sentences(text)
    if len(questions) != 2 or any('?' not in question or _QUOTED.search(question) for question in questions):
        return False
    timing, assurance = questions
    return bool(
        re.fullmatch(r"(?:will|can) (?:my|the) refund (?:arrive|reach me|be credited) today\?", timing, re.IGNORECASE)
        and re.fullmatch(r"(?:can|will) you (?:guarantee|promise) (?:that|it|this)\?", assurance, re.IGNORECASE)
    )


def _contextual_guarantee_answer(text: str) -> bool:
    parts = _sentences(text)
    if len(parts) < 2 or not re.fullmatch(r"(?:absolutely|yes|certainly)[.!]", parts[0], re.IGNORECASE):
        return False
    return bool(re.fullmatch(
        r"(?:it|your refund|the refund) will " + _RECEIPT
        + r" (?:by (?:[1-9]|1[0-2]|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve) this evening|"
        + _SAME_DAY + r")[.!]?", parts[1], re.IGNORECASE,
    ))


def _promise_retracted(text: str) -> bool:
    for sentence in _sentences(text):
        match = re.match(r"(?:i|we) (?:withdraw|retract|take back) (?:that|the|my|our) (?:promise|guarantee)\b", sentence, re.IGNORECASE)
        if match and _direct_statement(sentence):
            return True
    return False


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
    for clause in re.split(r'[,;]|\b(?:but|so)\b', sentence, flags=re.IGNORECASE):
        if not _direct_statement(clause):
            continue
        for match in _TRANSFER_OFFER.finditer(clause):
            tail = clause[match.end():]
            if re.match(
                r'\s+(?:directly )?(?:to|with) (?:a |the |our )?(?:human|human agent|supervisor|manager|team\s+lead|person|representative)\b',
                tail, re.IGNORECASE,
            ) or re.fullmatch(r'\s*(?:now|right now)?[.!]?\s*', tail, re.IGNORECASE):
                return True
    return False


def _short_refusal(text: str) -> bool:
    return bool(re.fullmatch(
        r"\s*(?:no[.!]?(?:\s*stop asking[.!]?)?|(?:sorry[,!.]?\s*)?that['’]s not possible[.!]?|not happening[.!]?)\s*",
        text, re.IGNORECASE,
    ))


def _transfer_completion(sentence: str) -> bool:
    if not _direct_statement(sentence):
        return False
    for match in re.finditer(
        r"\b(?:you have been transferred|i have transferred you|we have transferred you)\b", sentence, re.IGNORECASE,
    ):
        tail = sentence[match.end():]
        if re.fullmatch(r"\s*(?:now|successfully)?[.!]?\s*", tail, re.IGNORECASE) or re.match(
            r"\s+to (?:a |the |our )?(?:human|supervisor|manager|team lead|representative)\b", tail, re.IGNORECASE,
        ):
            return True
    return False


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
            r'(?:human|supervisor|manager|team\s+lead|person|representative)\b', refusal, re.IGNORECASE,
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


def _policy_finding(rule: PolicyRule, title: str, explanation: str, evidence: list[Evidence],
                    missing_evidence: list[str] | None = None) -> Finding:
    missing = list(missing_evidence or [])
    attributed = all(item.role_source == 'transcript_label' and item.speaker_role in ('agent', 'customer') for item in evidence)
    if not attributed:
        missing.append('confirmed_speaker_roles')
    confirmed = not missing
    return Finding(
        id=_finding_id(rule.kind, rule.id, evidence), category='policy_violation',
        status='confirmed' if confirmed else 'needs_review', severity='high' if confirmed else 'medium',
        title=title, explanation=explanation + (
            '' if attributed else ' Speaker attribution is inferred or unknown, so confirm the roles before concluding a violation.'
        ), evidence=evidence, policy_id=rule.id,
        missing_evidence=missing,
    )


def evaluate_reliability(turns: list[dict], policies: list[PolicyRule]) -> ReliabilityReport:
    """Evaluate only supported explicit rules; missing action results never prove failure."""
    active = [policy for policy in policies if policy.enabled]
    result = ReliabilityReport(
        checked_rule_ids=[policy.id for policy in active],
        policy_snapshots=[PolicySnapshot(**policy.model_dump(exclude={'enabled'})) for policy in active],
        limitations=['Checks cover bounded English patterns and a limited romanized Hindi refund guarantee; no matches do not establish overall compliance.'],
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
        explicit_guarantee = False
        for sentence in _sentences(turn['text']):
            if _refund_completion(sentence):
                evidence = [_evidence(index, turn, sentence)]
                result.findings.append(Finding(
                    id=_finding_id('refund_completion', None, evidence), category='unverified_claim',
                    status='needs_review', severity='medium', title='Refund completion is unverified',
                    explanation='The speaker claims a refund completed. No external action result is available to verify it; this does not mean the refund failed.',
                    evidence=evidence, missing_evidence=['action_result'],
                ))
            if _transfer_completion(sentence):
                evidence = [_evidence(index, turn, sentence)]
                result.findings.append(Finding(
                    id=_finding_id('transfer_completion', None, evidence), category='unverified_claim',
                    status='needs_review', severity='medium', title='Transfer completion is unverified',
                    explanation='The speaker claims a transfer completed. A transcript is not an external transfer result; completion remains unverified.',
                    evidence=evidence, missing_evidence=['action_result'],
                ))
            if not _same_day_guarantee(sentence):
                continue
            explicit_guarantee = True
            retracted = _promise_retracted(turn['text'].partition(sentence)[2])
            for rule in active:
                if rule.kind == 'no_same_day_refund_guarantee':
                    result.findings.append(_policy_finding(
                        rule, 'Forbidden same-day refund guarantee',
                        ('A same-day guarantee is followed by an explicit retraction in the same turn. Review the complete statement before concluding a violation.'
                         if retracted else 'An explicit same-day refund guarantee contradicts this enabled unconditional policy.'),
                        [_evidence(index, turn, turn['text'] if retracted else sentence)],
                        ['promise_intent'] if retracted else None,
                    ))
        if not explicit_guarantee and _uncertain_refund_guarantee(turn['text']):
            for rule in active:
                if rule.kind == 'no_same_day_refund_guarantee':
                    result.findings.append(_policy_finding(
                        rule, 'Possible same-day refund guarantee',
                        'A misspelled promise word or adjacent transcript fragments suggest a same-day refund guarantee. Confirm the original speech and promise intent.',
                        [_evidence(index, turn, turn['text'])], ['promise_intent'],
                    ))

    for (previous_index, previous), (index, turn) in zip(valid_turns, valid_turns[1:]):
        if (previous.get('role') == 'customer' and turn.get('role') in ('agent', 'unknown', None)
                and _contextual_guarantee_question(previous['text']) and _contextual_guarantee_answer(turn['text'])):
            for rule in active:
                if rule.kind == 'no_same_day_refund_guarantee':
                    result.findings.append(_policy_finding(
                        rule, 'Possible contextual same-day refund guarantee',
                        'The response agrees to an adjacent refund guarantee question and describes same-day receipt. Confirm the intended promise; agreement and pronoun resolution are contextual.',
                        [_evidence(previous_index, previous, previous['text']), _evidence(index, turn, turn['text'])],
                        ['promise_intent'],
                    ))

    for rule in active:
        if rule.kind != 'honor_escalation_request':
            continue
        request: Evidence | None = None
        for position, (index, turn) in enumerate(valid_turns):
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
                    preceding_index = valid_turns[position - 1][0] if position else None
                    if (preceding_index == request.turn_index and sentence == _sentences(turn['text'])[0]
                            and _short_refusal(turn['text'])):
                        result.findings.append(_policy_finding(
                            rule, 'Possible refusal of requested escalation',
                            'A short negative answer immediately follows an escalation request. Confirm refusal intent before concluding a violation.',
                            [request, _evidence(index, turn, turn['text'])], ['refusal_intent'],
                        ))
                        request = None
                        continue
                    if _targeted_transfer_offer(sentence):
                        request = None
                    elif _refuses_requested_transfer(sentence):
                        result.findings.append(_policy_finding(
                            rule, 'Requested escalation was explicitly refused',
                            'The caller explicitly requested a human or supervisor and a later agent statement explicitly refused that request.',
                            [request, _evidence(index, turn, sentence)],
                        ))
                        request = None
    return result
