import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

const source = await readFile(new URL('../src/components/benchmark-results.tsx', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.ESNext } }).outputText
  .replaceAll('"react/jsx-runtime"', JSON.stringify(import.meta.resolve('react/jsx-runtime')));
const { BenchmarkResults } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
const metrics = { true_positives: 1, false_positives: 0, false_negatives: 1, precision: 1, recall: 0.5, f1: 2/3 };
const finding = {category:'unverified_claim',status:'needs_review',policy_kind:null,severity:'medium',turn_indices:[1],missing_evidence:['action_result']};
const result = {total_cases:2,passed_cases:1,exact_case_accuracy:0.5,supported_cases:1,supported_passed:1,challenge_cases:1,challenge_passed:0,metrics,by_category:{unverified_claim:metrics},dataset_version:'1',dataset_sha256:'abc',limitations:['Synthetic only'],results:[{id:'a',name:'Missed action claim',purpose:'A completion claim needs an action result.',scope:'challenge_paraphrases',passed:false,turns:[{role:'agent',role_source:'model_inference',text:'The money was returned.'}],policies:[],expected_status:'assessed',actual_status:'assessed',expected:[finding],actual:[],evidence_errors:['Invalid quote']}]};

test('benchmark shows failed predictions, denominators and expected evidence', () => {
  const html = renderToStaticMarkup(createElement(BenchmarkResults,{benchmark:result}));
  for (const pattern of [/1\/2/,/50.0%/,/Challenge paraphrases: 0\/1/,/Mismatch/,/unverified claim/,/Evidence turns 2/,/Missing: action result/,/No finding/,/Invalid quote/,/abc/,/The money was returned/,/model inference/]) assert.match(html,pattern);
  assert.doesNotMatch(html,/improvement loop|Auto-tuned/);
});

test('no positives is unmeasured, not a perfect precision score', () => {
  const empty = {true_positives:0,false_positives:0,false_negatives:0,precision:null,recall:null,f1:null};
  const html = renderToStaticMarkup(createElement(BenchmarkResults,{benchmark:{...result,metrics:empty,by_category:{unverified_claim:empty}}}));
  assert.match(html,/Not measured/);
  assert.doesNotMatch(html,/100.0%/);
});

test('benchmark fetch uses the read-only detector endpoint and exposes service errors', async () => {
  const source = await readFile(new URL('../src/lib/api.ts',import.meta.url),'utf8');
  const js = ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext}}).outputText.replace('"./run-summary"',JSON.stringify(new URL('../src/lib/run-summary.ts',import.meta.url).href)).replace('"./stt-quality"',JSON.stringify(new URL('../src/lib/stt-quality.ts',import.meta.url).href)).replace('"./reliability"',JSON.stringify(new URL('../src/lib/reliability.ts',import.meta.url).href));
  const {getPolicyBenchmark} = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`);
  const original=globalThis.fetch;
  try {
    globalThis.fetch=async (url,options)=>{
      assert.equal(url,'/api/v1/loop/benchmark/reliability');
      assert.equal(options.method,undefined);
      return new Response(JSON.stringify(result),{status:200});
    };
    assert.deepEqual(await getPolicyBenchmark(),result);
    globalThis.fetch=async ()=>new Response(JSON.stringify({detail:'Policy benchmark data unavailable or invalid'}),{status:503});
    await assert.rejects(getPolicyBenchmark(),/Policy benchmark data unavailable or invalid/);
  } finally {globalThis.fetch=original;}
});

test('case purpose and only the supplied fictional rule explain relevance', () => {
  const refund = {id:'refund',text:'Agents must never guarantee same-day refunds.'};
  const benchmark = {...result,results:[{...result.results[0],name:'Refund timing',purpose:'A refund estimate must not become a forbidden guarantee.',policies:[refund],turns:[{role:'agent',role_source:'transcript_label',text:'Refunds usually take five to seven business days.'}],expected:[],actual:[],passed:true,evidence_errors:[]}]};
  const html = renderToStaticMarkup(createElement(BenchmarkResults,{benchmark}));
  assert.match(html,/A refund estimate must not become a forbidden guarantee/);
  assert.match(html,/Synthetic test conversation/);
  assert.match(html,/Fictional rule under test/);
  assert.match(html,/Agents must never guarantee same-day refunds/);
  assert.doesNotMatch(html,/supervisor|>Supported pattern</);
  const actionHtml = renderToStaticMarkup(createElement(BenchmarkResults,{benchmark:result}));
  assert.match(actionHtml,/No company policy is supplied/);
  assert.doesNotMatch(actionHtml,/Fictional rule under test/);
});
