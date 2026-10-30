'use client';

import { useEffect, useRef, useState } from 'react';
import { evaluateSTT, generateSTTReference, prepareSTTReview, retrieveSTTRecording } from '../lib/api';
import { savedSTTSetup, parseReviewInput, type STTState } from '../lib/stt-quality';
import { STTResults } from './stt-results';
import { STTTranscripts } from './stt-transcripts';

type State = {kind:'loading'} | {kind:'error'; message:string} | {kind:'ready'; data:STTState};

export function STTReviewPanel({ runId }: {runId:string}) {
  const [state,setState]=useState<State>({kind:'loading'});
  const [reload,setReload]=useState(0);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState<string|null>(null);
  const [scope,setScope]=useState('unknown');
  const [scopeConfirmed,setScopeConfirmed]=useState(false);
  const [mapping,setMapping]=useState<Record<string,string>>({});
  const [mappingConfirmed,setMappingConfirmed]=useState(false);
  const [target,setTarget]=useState('caller_only');
  const [annotations,setAnnotations]=useState('');
  const [human,setHuman]=useState('');
  const player=useRef<HTMLAudioElement>(null);
  useEffect(()=>{
    let active=true;
    prepareSTTReview(runId).then(data=>{if(active){const saved=savedSTTSetup(data);setScope(saved.scope);setScopeConfirmed(saved.scopeConfirmed);setMapping(saved.mapping);setMappingConfirmed(saved.mappingConfirmed);setState({kind:'ready',data});}}).catch(error=>{if(active)setState({kind:'error',message:error instanceof Error?error.message:'STT review unavailable.'});});
    return ()=>{active=false;};
  },[runId,reload]);
  const retrieve=async()=>{
    setBusy(true);setError(null);
    try{setState({kind:'ready',data:await retrieveSTTRecording(runId)});}catch(error){setError(error instanceof Error?error.message:'Recording retrieval failed.');}finally{setBusy(false);}
  };
  const create=async()=>{
    setBusy(true);setError(null);
    try{setState({kind:'ready',data:await generateSTTReference(runId)});}catch(error){setError(error instanceof Error?error.message:'Reference transcription failed.');}finally{setBusy(false);}
  };
  const compare=async()=>{
    setBusy(true);setError(null);
    try{
      const body={recording_scope:scope,scope_confirmed:scopeConfirmed,target,speaker_roles:Object.fromEntries(Object.entries(mapping).filter(([,role])=>role !== 'unknown')),speaker_mapping_confirmed:mappingConfirmed,...(annotations.trim()?{bolna_annotations:parseReviewInput(annotations)}:{}),...(human.trim()?{human_reference:parseReviewInput(human)}:{})};
      setState({kind:'ready',data:await evaluateSTT(runId,body)});
    }catch(error){setError(error instanceof Error?error.message:'Comparison failed.');}finally{setBusy(false);}
  };
  const seek=(time:number)=>{
    if(!player.current){setError('Original recording is unavailable.');return;}
    player.current.currentTime=time;
    void player.current.play().catch(()=>setError('Audio playback could not start. Use the recording controls to listen.'));
  };
  if(state.kind==='loading')return <div className="review-empty" role="status">Preparing post-call STT review with Deepgram…</div>;
  if(state.kind==='error')return <div className="review-error" role="alert"><p>{state.message}</p><button className="btn btn-ghost" onClick={()=>{setState({kind:'loading'});setReload(value=>value+1);}}>Retry STT review</button></div>;
  const {data}=state;
  const ids=[...new Set(data.reference?.segments.map(segment=>segment.speaker) || [])];
  return <div className="review-stack">
    <div className="review-section-heading"><h3>Post-call STT quality</h3><span>Original audio and transcript evidence</span></div>
    <p className="review-description">Compare the Bolna transcript with a separate Deepgram pass or a reference verified by a human. Automatic differences require listening and review.</p>
    {error && <div className="review-error" role="alert">{error}</div>}
    {data.review && <STTResults review={data.review} onSeek={seek} />}
    {data.reference && data.bolna.segments.some(segment=>segment.start===null) && <p className="review-note">Reference ready. Bolna turn timings are missing, so an aligned score is not available yet. Listen and inspect both transcripts below.</p>}
    {!data.audio.available && <section className="review-policy-form"><h3>Original recording</h3><p className="review-description">Retrieve the completed recording from Bolna for private listening or human verification. This action does not send audio to an STT provider.</p><button className="btn btn-ghost" disabled={busy} onClick={()=>void retrieve()}>Retrieve original recording</button></section>}
    {data.audio.available && <section className="stt-audio"><h4>Original recording</h4><audio ref={player} controls preload="metadata" src={`/api/v1/runs/${encodeURIComponent(runId)}/stt-review/audio`} onError={()=>setError('The private recording is unavailable or expired.')} /><p className="review-description">{data.audio.channels === null?'Channel count unavailable':`${data.audio.channels} audio channels`} · channel count does not establish caller isolation.</p></section>}
    {!data.reference && <section className="review-policy-form"><h3>Create an automatic reference</h3><p className="review-description">This sends the completed recording to Deepgram, the existing STT provider. References are prepared automatically when this review opens and reused after reload. This uses the completed recording. No provider fallback is used.</p>{!data.provider.configured && <p className="review-inline-error">Deepgram is not configured. A human-verified reference can be supplied after the original recording is available.</p>}<button className="btn btn-primary" disabled={busy||!data.provider.configured} onClick={()=>void create()}>{busy?'Preparing reference…':'Create Deepgram reference'}</button></section>}
    <STTTranscripts bolna={data.bolna} reference={data.reference} onSeek={seek} />
    <details className="stt-comparison-setup"><summary>Set up a scored comparison</summary><p className="review-description">Confirm speakers, add timing annotations, or supply a human-verified reference. These steps establish comparable evidence.</p><section className="review-policy-form"><h3>Confirm comparable speech</h3><label>Recording contains<select aria-label="Recording speaker coverage" value={scope} onChange={event=>{setScope(event.target.value);setScopeConfirmed(false);}}><option value="unknown">Unknown</option><option value="caller_only">Caller audio only</option><option value="mixed">Mixed caller and agent audio</option></select></label><label className="review-checkbox"><input type="checkbox" checked={scopeConfirmed} onChange={event=>setScopeConfirmed(event.target.checked)} />I confirmed the recording coverage by listening.</label><label>Compare<select aria-label="Transcript comparison scope" value={target} onChange={event=>setTarget(event.target.value)}><option value="caller_only">Caller speech only</option><option value="mixed">Caller and agent speech</option></select></label>
      {data.reference?.source==='deepgram' && ids.map(id=><label key={id}>{id}<select aria-label={`Role for ${id}`} value={mapping[id]||'unknown'} onChange={event=>{setMapping(previous=>({...previous,[id]:event.target.value}));setMappingConfirmed(false);}}><option value="unknown">Role unknown</option><option value="caller">Caller</option><option value="agent">Agent</option></select></label>)}
      {data.reference?.source==='deepgram' && <label className="review-checkbox"><input type="checkbox" checked={mappingConfirmed} onChange={event=>setMappingConfirmed(event.target.checked)} />I confirmed these speaker roles from the recording.</label>}
      {data.bolna.segments.some(segment=>segment.start===null) && <p className="review-inline-error">Bolna timestamps are missing. You can inspect discrepancies, but no aligned rate will be shown until valid timing annotations are provided.</p>}
      <details><summary className="stt-input-summary">Debugging: timing annotations and human reference</summary><p className="review-description">Optional transcript JSON. Timing annotations must preserve the original Bolna words and roles. A human reference must include the exact recording hash, human_verified: true, and verified_by after listening.</p><p className="policy-version">Recording SHA-256: {data.audio.sha256||'Recording not retrieved'}</p><label>Bolna timing annotations<textarea aria-label="Bolna timing annotations JSON" rows={6} value={annotations} onChange={event=>setAnnotations(event.target.value)} /></label><button className="btn btn-ghost" onClick={()=>setAnnotations(JSON.stringify(data.bolna,null,2))}>Load original words for annotation</button><label>Human-verified reference<textarea aria-label="Human verified reference JSON" rows={6} value={human} onChange={event=>setHuman(event.target.value)} /></label></details>
      <button className="btn btn-primary" disabled={busy||!data.reference&&!human.trim()} onClick={()=>void compare()}>{busy?'Comparing…':'Compare transcripts'}</button>
    </section></details>
  </div>;
}
