import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFile} from 'node:fs/promises';
import ts from 'typescript';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {parseSTTState,isSTTReview,sttMetric,audioTime,parseReviewInput} from '../src/lib/stt-quality.ts';

const segment={text:'I do want a refund',speaker:'caller',role:'caller',start:0,end:3};
const transcript={source:'bolna',scope:'caller_only',segments:[segment],audio_sha256:null,human_verified:false,verified_by:null};
const finding={start:0,end:3,role:'caller',bolna_text:segment.text,reference_text:'I do not want a refund',category:['negation'],severity:'high',status:'needs_review',confidence:'low',confidence_basis:'Automatic reference; listen to the recording.',explanation:'The transcripts disagree.'};
const review={schema_version:'1',status:'completed',reference_source:'deepgram',reference_human_verified:false,verified_by:null,metric_kind:'estimated_disagreement',metric_value:1/6,edits:{substitutions:0,deletions:1,insertions:0,reference_words:6},compared_groups:1,findings:[finding],issues:[],limitations:['Model agreement does not prove accuracy.']};
const state={review,reference:null,bolna:transcript,audio:{available:true,sha256:'a'.repeat(64),channels:1,duration_seconds:10,scope:'unknown',scope_basis:'Not established'},provider:{name:'deepgram',configured:true,requires_consent:true}};

test('STT state validates untrusted API data and rejects misleading metrics',()=>{
  assert.deepEqual(parseSTTState(state),state);
  for(const value of [null,{}, {...state,review:{...review,metric_kind:'wer'}},{...state,review:{...review,metric_kind:'wer',reference_human_verified:true}},{...state,review:{...review,findings:[{...finding,status:'confirmed_error'}]}},{...state,review:{...review,metric_value:-1}},{...state,review:{...review,status:'partial'}},{...state,bolna:{...transcript,segments:[{...segment,end:null}]}},{...state,audio:{...state.audio,channels:0}},{...state,reference:{...transcript,source:'human',human_verified:false}}]) assert.throws(()=>parseSTTState(value),/invalid or unsupported/);
  assert.equal(isSTTReview({...review,reference_source:'human',reference_human_verified:true,verified_by:'Reviewer',metric_kind:'wer',findings:[{...finding,status:'confirmed_error'}]}),true);
  assert.equal(isSTTReview({...review,schema_version:'future'}),false);
  assert.equal(isSTTReview({...review,edits:{...review.edits,deletions:0}}),false);
  assert.equal(isSTTReview({...review,edits:null}),false);
});

test('labels distinguish human WER, estimated disagreement and unavailable scores',()=>{
  assert.deepEqual(sttMetric(review),{label:'Estimated transcript disagreement',value:'16.7%'});
  assert.equal(sttMetric({...review,metric_kind:'wer',metric_value:3}).value,'300.0%');
  assert.match(sttMetric({...review,metric_kind:'wer'}).label,/human-verified/);
  assert.equal(sttMetric({...review,metric_value:null,metric_kind:null}).value,'Not scored');
  assert.equal(audioTime(61.25),'1:01.3');
  assert.equal(audioTime(null),'Timestamp unavailable');
  assert.equal(audioTime(59.96),'1:00.0');
  assert.equal(audioTime(0),'0:00.0');
  assert.deepEqual(parseReviewInput('{"source":"human"}'),{source:'human'});
  assert.throws(()=>parseReviewInput('{'),/JSON is invalid/);
});

const source=await readFile(new URL('../src/components/stt-results.tsx',import.meta.url),'utf8');
const js=ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.ESNext}}).outputText.replaceAll('"react/jsx-runtime"',JSON.stringify(import.meta.resolve('react/jsx-runtime'))).replaceAll("'../lib/stt-quality'",JSON.stringify(new URL('../src/lib/stt-quality.ts',import.meta.url).href));
const {STTResults}=await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`);
const render=value=>renderToStaticMarkup(createElement(STTResults,{review:value,onSeek(){}}));

test('STT evidence renders both texts, timestamp, severity and uncertainty',()=>{
  const html=render(review);
  for(const pattern of [/Estimated transcript disagreement/,/16.7%/,/Needs human review/,/negation/,/high/,/Listen at 0:00.0/,/I do want a refund/,/I do not want a refund/,/Confidence:.*low/,/Model agreement/]) assert.match(html.replace(/<[^>]*>/g,''),pattern);
  assert.doesNotMatch(html,/Confirmed STT error|WER/);
  const partial=render({...review,status:'partial',metric_kind:null,metric_value:null,findings:[{...finding,start:null,end:null}],issues:['Timestamps are missing.']});
  assert.match(partial,/Not scored/);
  assert.match(partial,/Timestamp unavailable/);
  assert.doesNotMatch(partial,/Listen at|No differences/);
  assert.match(render({...review,metric_kind:'wer',reference_human_verified:true,verified_by:'Test reviewer',findings:[{...finding,status:'confirmed_error'}]}),/Confirmed STT error/);
  assert.match(render({...review,findings:[]}),/Model agreement does not prove accuracy/);
});

test('STT API helpers select the authorized provider and preserve encoded IDs and errors',async()=>{
  const source=await readFile(new URL('../src/lib/api.ts',import.meta.url),'utf8');
  const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext}}).outputText.replace('"./stt-quality"',JSON.stringify(new URL('../src/lib/stt-quality.ts',import.meta.url).href)).replace('"./reliability"',JSON.stringify(new URL('../src/lib/reliability.ts',import.meta.url).href));
  const api=await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
  const original=globalThis.fetch;
  const calls=[];
  try{
    globalThis.fetch=async(url,options)=>{calls.push({url,options});return new Response(JSON.stringify(state));};
    await api.getSTTReview('a/b');
    assert.equal(calls[0].url,'/api/v1/runs/a%2Fb/stt-review');
    assert.equal(calls[0].options.method,undefined);
    await api.retrieveSTTRecording('run');
    assert.match(calls[1].url,/\/recording$/);
    assert.equal(calls[1].options.body,undefined);
    await api.generateSTTReference('run');
    assert.deepEqual(JSON.parse(calls[2].options.body),{provider:'deepgram'});
    await api.evaluateSTT('run',{scope_confirmed:false});
    assert.equal(calls[3].options.body,'{"scope_confirmed":false}');
    globalThis.fetch=async()=>new Response(JSON.stringify({detail:'Private STT review requires an access-controlled frontend.'}),{status:403});
    await assert.rejects(api.getSTTReview('run'),/access-controlled/);
    globalThis.fetch=async()=>new Response('{}');
    await assert.rejects(api.getSTTReview('run'),/invalid or unsupported/);
  }finally{globalThis.fetch=original;}
});

test('opening a real STT review prepares missing references automatically and respects existing results',async()=>{
  const source=await readFile(new URL('../src/lib/api.ts',import.meta.url),'utf8');
  const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext}}).outputText.replace('"./stt-quality"',JSON.stringify(new URL('../src/lib/stt-quality.ts',import.meta.url).href)).replace('"./reliability"',JSON.stringify(new URL('../src/lib/reliability.ts',import.meta.url).href));
  const api=await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
  const original=globalThis.fetch;
  const automatic={...state,review:null,reference:{...transcript,source:'deepgram',audio_sha256:'a'.repeat(64)}};
  const cases=[
    {name:'real call',id:'real-call',initial:{...state,review:null},posts:1},
    {name:'cached',id:'real-call',initial:automatic,posts:0},
    {name:'provider outage',id:'real-call',initial:{...state,review:{...review,status:'failed',metric_kind:null,metric_value:null}},posts:0},
    {name:'missing credentials',id:'real-call',initial:{...state,provider:{...state.provider,configured:false}},posts:0},
    {name:'synthetic demo',id:'demo-call',initial:{...state,review:null},posts:0},
    {name:'missing original',id:'real-call',initial:{...state,bolna:{...transcript,segments:[]}},posts:0},
  ];
  try{
    for(const scenario of cases){
      const posts=[];
      globalThis.fetch=async(url,options)=>{
        if(options.method==='POST'){
          posts.push({url,body:JSON.parse(options.body)});
          return new Response(JSON.stringify(automatic));
        }
        return new Response(JSON.stringify(scenario.initial));
      };
      const result=await api.prepareSTTReview(scenario.id);
      assert.equal(posts.length,scenario.posts,scenario.name);
      if(scenario.posts){
        assert.deepEqual(posts[0].body,{provider:'deepgram'});
        assert.equal(result.reference.source,'deepgram');
      }else assert.deepEqual(result,scenario.initial);
    }
  }finally{globalThis.fetch=original;}
});

const transcriptSource=await readFile(new URL('../src/components/stt-transcripts.tsx',import.meta.url),'utf8');
const transcriptJS=ts.transpileModule(transcriptSource,{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.ESNext}}).outputText.replaceAll('"react/jsx-runtime"',JSON.stringify(import.meta.resolve('react/jsx-runtime'))).replaceAll("'../lib/stt-quality'",JSON.stringify(new URL('../src/lib/stt-quality.ts',import.meta.url).href));
const {STTTranscripts}=await import(`data:text/javascript;base64,${Buffer.from(transcriptJS).toString('base64')}`);
const renderTranscripts=(bolna,reference)=>renderToStaticMarkup(createElement(STTTranscripts,{bolna,reference,onSeek(){}}));

test('full STT sources render as message panels with honest speaker and timing labels',()=>{
  const bolna={...transcript,segments:[{...segment,start:null,end:null,text:'Caller <words>'},{...segment,role:'agent',text:'Agent reply',start:null,end:null}]};
  const reference={...transcript,source:'deepgram',segments:[{...segment,role:'unknown',speaker:'dg_0'}]};
  const html=renderTranscripts(bolna,reference);
  for(const pattern of [/aria-label="Bolna transcript messages"/,/aria-label="Deepgram reference messages"/,/conversation-message-caller/,/conversation-message-agent/,/conversation-message-unknown/,/dg_0 · role unknown/,/Caller &lt;words&gt;/,/Timing unavailable/,/Listen to Deepgram reference at 0:00.0/,/Rows are not time-aligned/])assert.match(html,pattern);
  assert.doesNotMatch(html,/<strong>dg_0.*Caller|Confirmed STT error/);
});

test('missing sources and human references do not acquire automatic provenance',()=>{
  const empty=renderTranscripts({...transcript,segments:[]},null);
  assert.match(empty,/Original transcript unavailable/);
  assert.match(empty,/No reference transcript is available yet/);
  assert.doesNotMatch(empty,/<li|Listen to/);
  const human=renderTranscripts(transcript,{...transcript,source:'human',human_verified:true,verified_by:'Reviewer'});
  assert.match(human,/Human-verified reference messages/);
  assert.doesNotMatch(human,/Deepgram reference/);
});

test('blocked reviews do not render an empty discrepancy count as a completed assessment',()=>{
  const html=render({...review,status:'blocked',metric_kind:null,metric_value:null,findings:[],compared_groups:0,issues:['Speaker coverage is unknown.']});
  assert.match(html,/Not scored/);
  assert.match(html,/Speaker coverage is unknown/);
  assert.doesNotMatch(html,/Transcript discrepancies|0 findings|No differences/);
  assert.match(html,/<details[^>]*><summary>Scoring details and limitations/);
});

test('saved setup reuses confirmed coverage and roles without guessing unknown speakers',async()=>{
  const {savedSTTSetup}=await import('../src/lib/stt-quality.ts');
  assert.deepEqual(savedSTTSetup(state),{scope:'unknown',scopeConfirmed:false,mapping:{},mappingConfirmed:false});
  const known={...state,audio:{...state.audio,scope:'mixed'},reference:{...transcript,source:'deepgram',scope:'mixed',segments:[{...segment,speaker:'dg_9'}, {...segment,speaker:'dg_2',role:'agent'}]}};
  assert.deepEqual(savedSTTSetup(known),{scope:'mixed',scopeConfirmed:true,mapping:{dg_9:'caller',dg_2:'agent'},mappingConfirmed:true});
  assert.equal(savedSTTSetup({...known,reference:{...known.reference,segments:[{...segment,role:'unknown'}]}}).mappingConfirmed,false);
});

test('display diff highlights changed words while preserving both sources and bounded work',async()=>{
  const {disagreementParts}=await import('../src/lib/stt-quality.ts');
  for(const [a,b] of [['I want a refund','I do not want a refund'],['Refund $10','Refund $100'],['same','same'],['','hello'],['word '.repeat(1000),'other '.repeat(1000)]]){
    const parts=disagreementParts(a,b);
    assert.equal(parts[0].map(p=>p.text).join(''),a);
    assert.equal(parts[1].map(p=>p.text).join(''),b);
    assert.equal(parts.flat().some(p=>p.changed),a!==b);
  }
  const html=render(review);
  assert.match(html,/<mark class="stt-disagreement">not<\/mark>/);
  assert.match(html,/not transcription accuracy/);
});
