import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFile} from 'node:fs/promises';
import ts from 'typescript';
import {NextRequest} from 'next/server.js';

const source=await readFile(new URL('../src/app/api/[...path]/route.ts',import.meta.url),'utf8');
const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext}}).outputText.replaceAll('"next/server"',JSON.stringify(import.meta.resolve('next/server.js')));
async function load(enabled){
  const previous=process.env.STT_REVIEW_PROXY_ENABLED;
  process.env.STT_REVIEW_PROXY_ENABLED=enabled;
  try{return await import(`data:text/javascript;base64,${Buffer.from(compiled+`\n// enabled:${enabled}`).toString('base64')}`);}finally{if(previous===undefined)delete process.env.STT_REVIEW_PROXY_ENABLED;else process.env.STT_REVIEW_PROXY_ENABLED=previous;}
}

test('public shared-key proxy blocks every private STT operation by default',async()=>{
  const api=await load('false');
  const original=globalThis.fetch;
  try{
    globalThis.fetch=async()=>{throw new Error('must not contact backend');};
    for(const suffix of ['','/audio','/recording','/reference']){
      const response=await api.GET(new NextRequest(`http://localhost/api/v1/runs/run/stt-review${suffix}`),{params:Promise.resolve({path:['v1','runs','run','stt-review',...suffix.split('/').filter(Boolean)]})});
      assert.equal(response.status,403);
      assert.match((await response.json()).detail,/access-controlled/);
    }
  }finally{globalThis.fetch=original;}
});

test('private proxy opt-in forwards report access and preserves audio privacy headers',async()=>{
  const api=await load('true');
  const original=globalThis.fetch;
  try{
    globalThis.fetch=async(url,options)=>{
      assert.equal(options.headers.get('X-STT-Review'),'1');
      return new Response('audio',{headers:{'Content-Type':'audio/wav','Cache-Control':'no-store'}});
    };
    const response=await api.GET(new NextRequest('http://localhost/api/v1/runs/run/stt-review/audio'),{params:Promise.resolve({path:['v1','runs','run','stt-review','audio']})});
    assert.equal(await response.text(),'audio');
    assert.equal(response.headers.get('cache-control'),'no-store');
    assert.equal(response.headers.get('content-type'),'audio/wav');
    assert.equal(response.headers.get('content-length'),'5');
  }finally{globalThis.fetch=original;}
});

test('stream proxy preserves a transport failure without closing an already errored controller',async()=>{
  const api=await load('true');
  const original=globalThis.fetch;
  try{
    globalThis.fetch=async()=>new Response(new ReadableStream({start(controller){controller.error(new Error('upstream disconnected'));}}),{headers:{'Content-Type':'text/event-stream'}});
    const response=await api.POST(new NextRequest('http://localhost/api/v1/analyze/stream',{method:'POST',body:'synthetic audio'}),{params:Promise.resolve({path:['v1','analyze','stream']})});
    await assert.rejects(response.text(),/upstream disconnected/);
  }finally{globalThis.fetch=original;}
});

test('encoded and normalized paths cannot bypass the private STT gate',async()=>{
  const api=await load('false');
  const original=globalThis.fetch;
  try{
    globalThis.fetch=async()=>{throw new Error('must not contact backend');};
    for(const path of [
      ['v1','runs','run','%73tt-review','audio'],
      ['v1','runs','run','other','..','stt-review','audio'],
      ['v1','runs','run','other%2f..%2fstt-review','audio'],
      ['v1','runs','run','%2573tt-review','audio'],
    ]){
      const response=await api.GET(new NextRequest('http://localhost/api/v1/runs/run/stt-review/audio'),{params:Promise.resolve({path})});
      assert.equal(response.status,403,JSON.stringify(path));
    }
  }finally{globalThis.fetch=original;}
});
