import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFile} from 'node:fs/promises';
import ts from 'typescript';

const source=await readFile(new URL('../src/lib/api.ts',import.meta.url),'utf8');
const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext}}).outputText.replace('"./stt-quality"',JSON.stringify(new URL('../src/lib/stt-quality.ts',import.meta.url).href)).replace('"./reliability"',JSON.stringify(new URL('../src/lib/reliability.ts',import.meta.url).href));
const {analyzeAudioStream,getRuns,getRun}=await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
const file=new File(['synthetic audio'],'test.wav',{type:'audio/wav'});
const sse=text=>new Response(text,{headers:{'content-type':'text/event-stream'}});
async function collect(response){
  const original=globalThis.fetch;
  globalThis.fetch=async()=>response;
  try{const events=[];for await(const event of analyzeAudioStream(file))events.push(event);return events;}finally{globalThis.fetch=original;}
}

test('HTTP 200 with an empty or truncated stream is an error, not upload success',async()=>{
  await assert.rejects(collect(sse('')),/ended before a result/);
  await assert.rejects(collect(sse('data: {"event":"started","run_id":"run"}\n\n')),/ended before a result/);
  await assert.rejects(collect(new Response('{}')),/did not return a progress stream/);
});

test('malformed and incomplete terminal events are never silently ignored',async()=>{
  for(const payload of ['broken','{}','{"event":"complete"}','{"event":"complete","result":{"run_id":"run"}}','{"event":"complete","result":{"run_id":"","status":"completed"}}','{"event":"complete","result":{"run_id":"run","status":"imagined"}}'])await assert.rejects(collect(sse(`data: ${payload}\n\n`)),/invalid progress event|missing result/);
});

test('split UTF-8, CRLF, heartbeat comments and a terminal frame without a trailing newline work',async()=>{
  const bytes=new TextEncoder().encode(': heartbeat\r\n\r\ndata: {"event":"started","run_id":"run-é"}\r\n\r\ndata: {"event":"stage_complete","stage":"transcription"}\r\n\r\ndata: {"event":"complete",\r\ndata: "result":{"run_id":"run-é","status":"partial"}}');
  const stream=new ReadableStream({start(controller){for(const byte of bytes)controller.enqueue(Uint8Array.of(byte));controller.close();}});
  const events=await collect(new Response(stream,{headers:{'content-type':'text/event-stream'}}));
  assert.deepEqual(events,[{event:'started',run_id:'run-é'},{event:'stage_complete',stage:'transcription'},{event:'complete',result:{run_id:'run-é',status:'partial'}}]);
});

test('backend error events remain visible and failed evaluations keep their status',async()=>{
  assert.deepEqual(await collect(sse('data: {"event":"error","detail":"Analysis failed"}\n\n')),[{event:'error',detail:'Analysis failed'}]);
  const events=await collect(sse('data: {"event":"complete","result":{"run_id":"run","status":"failed"}}\n\n'));
  assert.equal(events[0].result.status,'failed');
});

test('HTTP service errors, dropped connections, and aborts cannot become empty success',async()=>{
  await assert.rejects(collect(new Response(JSON.stringify({detail:'Unsupported audio format'}),{status:422})),/Unsupported audio format/);
  const stream=new ReadableStream({start(controller){controller.error(new Error('Connection interrupted'));}});
  await assert.rejects(collect(new Response(stream,{headers:{'content-type':'text/event-stream'}})),/Connection interrupted/);
  const original=globalThis.fetch;
  try{
    globalThis.fetch=async()=>{throw new DOMException('Aborted','AbortError');};
    await assert.rejects(async()=>{for await(const event of analyzeAudioStream(file))void event;},/Analysis timed out/);
  }finally{globalThis.fetch=original;}
});


test('malformed call-list and detail responses become actionable errors',async()=>{
 const original=globalThis.fetch;
 try{
  for(const body of [{},null,{runs:null,total:1},{runs:[{}],total:1},{runs:[],total:-1}]){
   globalThis.fetch=async()=>Response.json(body);
   await assert.rejects(getRuns(),/invalid.*response/i);
  }
  globalThis.fetch=async()=>Response.json({});await assert.rejects(getRun('demo'),/invalid.*response/i);
  globalThis.fetch=async()=>Response.json({runs:[],total:0});assert.deepEqual(await getRuns(),{runs:[],total:0});
 }finally{globalThis.fetch=original}
});


test('call reads time out and propagate a retryable failure instead of waiting forever',async()=>{
 const originalFetch=globalThis.fetch;const originalTimeout=AbortSignal.timeout;
 try{
  AbortSignal.timeout=ms=>{assert.equal(ms,30000);return originalTimeout(5)};
  globalThis.fetch=async(_url,options)=>new Promise((_,reject)=>{options.signal.addEventListener('abort',()=>reject(options.signal.reason),{once:true});setTimeout(()=>{},10)});
  await assert.rejects(getRuns(),{name:'TimeoutError'});await assert.rejects(getRun('demo'),{name:'TimeoutError'});
 }finally{globalThis.fetch=originalFetch;AbortSignal.timeout=originalTimeout}
});
