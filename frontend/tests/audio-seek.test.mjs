import assert from 'node:assert/strict';
import {test} from 'node:test';
import {createAudioSeeker} from '../src/lib/audio-seek.ts';

class Audio extends EventTarget {
  readyState=1; duration=4; error=null; seeking=false; position=0; played=[];
  get currentTime(){return this.position;}
  set currentTime(value){this.seeking=true;this.position=value;queueMicrotask(()=>{this.seeking=false;this.dispatchEvent(new Event('seeked'));});}
  async play(){this.played.push(this.position);}
}
test('seeking waits for metadata and seek completion before playback',async()=>{
  const a=new Audio();a.readyState=0;a.duration=NaN;const errors=[];const seeker=createAudioSeeker(a,e=>errors.push(e));const result=seeker.seek(.6);await new Promise(r=>setTimeout(r,5));assert.deepEqual(a.played,[]);
  a.readyState=1;a.duration=4;a.dispatchEvent(new Event('loadedmetadata'));await result;assert.deepEqual(a.played,[.6]);assert.deepEqual(errors,[]);seeker.dispose();
});
test('rapid and repeated seeks use the latest timestamp, including zero and near end',async()=>{
  const a=new Audio();const errors=[];const s=createAudioSeeker(a,e=>errors.push(e));await Promise.all([s.seek(.6),s.seek(1.2),s.seek(2)]);assert.equal(a.currentTime,2);assert.equal(a.played.at(-1),2);
  for(const t of [2,0,3.95,.6]){await s.seek(t);assert.equal(a.currentTime,t);assert.equal(a.played.at(-1),t)}assert.deepEqual(errors,[]);s.dispose();
});
test('invalid and missing timestamps, failed media, timeouts and rejected playback cannot silently start at zero',async()=>{
  for(const value of [-1,NaN,undefined,Infinity,4,10]){const a=new Audio();const errors=[];const s=createAudioSeeker(a,e=>errors.push(e),10);await s.seek(value);assert.equal(errors.length,1);assert.deepEqual(a.played,[]);s.dispose()}
  for(const kind of ['error','timeout','play']){const a=new Audio();const errors=[];if(kind==='error')a.error={code:4};if(kind==='timeout')a.readyState=0;if(kind==='play')a.play=async()=>{throw Error('not allowed')};const s=createAudioSeeker(a,e=>errors.push(e),10);await s.seek(.6);assert.equal(errors.length,1);s.dispose()}
});
test('unmounting or changing source cancels pending seeks without stale errors or playback',async()=>{
  const a=new Audio();a.readyState=0;const errors=[];const s=createAudioSeeker(a,e=>errors.push(e));const pending=s.seek(.6);s.dispose();a.readyState=1;a.dispatchEvent(new Event('loadedmetadata'));await pending;await s.seek(1);assert.deepEqual(a.played,[]);assert.deepEqual(errors,[]);
});
