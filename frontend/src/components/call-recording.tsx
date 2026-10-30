'use client';

import { useEffect, useState } from 'react';
import { Headphones, LoaderCircle } from 'lucide-react';
import { getSTTReview, retrieveSTTRecording, type Run } from '../lib/api';

type Recording = { kind: 'loading' } | { kind: 'ready'; available: boolean } | { kind: 'error'; message: string };

/** Listening never prepares a transcription or submits audio to Deepgram. */
export function CallRecording({ run }: { run: Run }) {
  const linked = run.evaluation?.source_call?.platform === 'bolna' && Boolean(run.evaluation.source_call.call_id);
  const [state, setState] = useState<Recording>({ kind: 'loading' });
  useEffect(() => {
    if (!linked) return;
    let active = true;
    getSTTReview(run.run_id).then(data => {
      if (active) setState({ kind: 'ready', available: data.audio.available });
    }).catch(() => {
      if (active) setState({ kind: 'error', message: 'Recording access is unavailable in this workspace.' });
    });
    return () => { active = false; };
  }, [linked, run.run_id]);

  const retrieve = async () => {
    setState({ kind: 'loading' });
    try {
      const data = await retrieveSTTRecording(run.run_id);
      setState(data.audio.available ? { kind: 'ready', available: true } : { kind: 'error', message: 'The original recording could not be retrieved. It may have expired at the source.' });
    } catch {
      setState({ kind: 'error', message: 'Recording access is unavailable. Check access or try again.' });
    }
  };

  return <section className="call-recording" aria-label="Original recording">
    <div className="call-recording-heading"><Headphones size={18} aria-hidden="true" /><strong>Original recording</strong></div>
    {!linked ? <p>Playback is available for linked Bolna recordings.</p> : state.kind === 'loading' ? <p role="status"><LoaderCircle size={14} className="animate-spin" />Loading recording…</p> : state.kind === 'ready' && state.available ?
      <audio controls preload="metadata" src={`/api/v1/runs/${encodeURIComponent(run.run_id)}/stt-review/audio`} onError={() => setState({ kind: 'error', message: 'The recording is unavailable or has expired. Retrieve it again to retry.' })} /> :
      <div className="call-recording-action">{state.kind === 'error' ? <p role="alert">{state.message}</p> : <p>Retrieve the completed recording to listen.</p>}<button className="btn btn-ghost" onClick={() => void retrieve()}>{state.kind === 'error' ? 'Retry recording' : 'Load recording'}</button></div>}
  </section>;
}
