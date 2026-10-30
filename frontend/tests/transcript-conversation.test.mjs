import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

const source = await readFile(new URL('../src/components/transcript-conversation.tsx', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.ESNext } }).outputText
  .replaceAll('"react/jsx-runtime"', JSON.stringify(import.meta.resolve('react/jsx-runtime')))
  .replaceAll("'lucide-react'", JSON.stringify(import.meta.resolve('lucide-react')))
  .replaceAll("'../lib/evaluation'", JSON.stringify(new URL('../src/lib/evaluation.ts', import.meta.url).href));
const { TranscriptConversation } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
const render = (run, highlightedTurn = null) => renderToStaticMarkup(createElement(TranscriptConversation, { run, highlightedTurn, registerTurn() {} }));

test('transcript renders caller and agent messages without repeated turn metadata', () => {
  const html = render({ transcript_speakers: [
    { speaker: 0, role: 'customer', role_source: 'transcript_label', text: 'Hello <agent>' },
    { speaker: 1, role: 'agent', role_source: 'transcript_label', text: 'Hello\nHow can I help?' },
  ] });
  assert.match(html, /conversation-message-caller/);
  assert.match(html, /conversation-message-agent/);
  assert.match(html, />Caller</);
  assert.match(html, /Hello &lt;agent&gt;/);
  assert.match(html, /Hello\nHow can I help\?/);
  assert.equal((html.match(/role="listitem"/g) || []).length, 2);
  assert.doesNotMatch(html, /attributed turns|Turn 1|Roles from transcript/);
});

test('inferred and unknown roles remain honest and evidence keeps its original index', () => {
  const html = render({ transcript_speakers: [
    { speaker: 4, role: 'agent', role_source: 'model_inference', text: 'Maybe' },
    { speaker: 9, label: 'Customer', text: 'Unknown' },
  ] }, 1);
  assert.match(html, /Agent · inferred/);
  assert.match(html, /Speaker 9 · role unknown/);
  assert.match(html, /conversation-message-unknown/);
  assert.match(html, /data-turn-index="1" class="conversation-bubble turn-highlighted"/);
  assert.equal((html.match(/Linked evidence/g) || []).length, 1);
});

test('raw transcripts and missing transcripts do not invent speakers', () => {
  assert.match(render({ transcript_speakers: null, evaluation: { raw_transcript: 'Original text' } }), /Speaker labels unavailable.*Original text/);
  assert.match(render({ transcript_speakers: [], transcript_preview: 'Legacy preview' }), /Legacy preview/);
  assert.match(render({ transcript_speakers: null }), /Transcript unavailable/);
  assert.doesNotMatch(render({ transcript_speakers: null }), /conversation-message/);
});
