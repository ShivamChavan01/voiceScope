import assert from 'node:assert/strict';import {test} from 'node:test';import {readFile} from 'node:fs/promises';import ts from 'typescript';import {createElement} from 'react';import {renderToStaticMarkup} from 'react-dom/server';
const source=await readFile(new URL('../src/components/overview-coverage.tsx',import.meta.url),'utf8');let js=ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.ESNext}}).outputText;js=js.replaceAll('"react/jsx-runtime"',JSON.stringify(import.meta.resolve('react/jsx-runtime')));
const {OverviewCoverage}=await import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'));
test('assessment coverage always names its real-only denominator, including an all-synthetic dataset',()=>{
 for(const [real_calls,legacy_calls] of [[0,0],[6,3],[1,1]]){
  const html=renderToStaticMarkup(createElement(OverviewCoverage,{summary:{real_calls,legacy_calls}})).replace(/<!--.*?-->/g,'');assert.match(html,/Real inputs without a structured policy assessment:/);assert.match(html,new RegExp(`${legacy_calls} of ${real_calls}`));assert.match(html,/Synthetic examples are excluded/);assert.doesNotMatch(html,/fully compliant/);
 }
});
