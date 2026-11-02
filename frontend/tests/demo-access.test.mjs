import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFile} from 'node:fs/promises';
import ts from 'typescript';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const source=await readFile(new URL('../src/components/demo-access.tsx',import.meta.url),'utf8');
const js=ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.ESNext}}).outputText.replaceAll("'react'",JSON.stringify(import.meta.resolve('react'))).replaceAll('"react"',JSON.stringify(import.meta.resolve('react'))).replaceAll('"react/jsx-runtime"',JSON.stringify(import.meta.resolve('react/jsx-runtime')));
const {DemoAccessProvider,useReadOnlyDemo}=await import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'));
function Probe(){return createElement('span',null,useReadOnlyDemo()?'read-only':'private')}
test('public read-only UI state is explicitly supplied by server; private behavior is the default',()=>{
 assert.equal(renderToStaticMarkup(createElement(Probe)),'<span>private</span>');
 for(const readOnly of [true,false])assert.equal(renderToStaticMarkup(createElement(DemoAccessProvider,{readOnly},createElement(Probe))),`<span>${readOnly?'read-only':'private'}</span>`);
});
