/** Wait for actual media readiness and seeking; a queued currentTime is not proof of a seek. */
export function createAudioSeeker(audio: HTMLMediaElement, onError: (message: string) => void, timeoutMs = 10000) {
  let pending: AbortController | null = null;
  let disposed = false;
  const wait = (event: string, ready: () => boolean, signal: AbortSignal) => new Promise<void>((resolve, reject) => {
    const done = () => { if (ready()) { cleanup(); resolve(); } };
    const failed = () => { cleanup(); reject(new Error('Audio is unavailable.')); };
    const aborted = () => { cleanup(); reject(new Error('Superseded seek.')); };
    const timer = setTimeout(failed, timeoutMs);
    const cleanup = () => {
      clearTimeout(timer);
      audio.removeEventListener(event, done);
      audio.removeEventListener('error', failed);
      signal.removeEventListener('abort', aborted);
    };
    audio.addEventListener(event, done);
    audio.addEventListener('error', failed);
    signal.addEventListener('abort', aborted, { once: true });
    if (signal.aborted) aborted();
    else if (audio.error) failed();
    else done();
  });
  return {
    async seek(time: number) {
      pending?.abort();
      if (disposed) return;
      const operation = new AbortController();
      pending = operation;
      const { signal } = operation;
      try {
        if (!Number.isFinite(time) || time < 0) throw new Error('Invalid audio timestamp.');
        await wait('loadedmetadata', () => audio.readyState >= 1, signal);
        if (!Number.isFinite(audio.duration) || time >= audio.duration) throw new Error('Timestamp is outside this recording.');
        if (signal.aborted) return;
        audio.currentTime = time;
        await wait('seeked', () => !audio.seeking && Math.abs(audio.currentTime - time) < .05, signal);
        if (!signal.aborted) await audio.play();
      } catch {
        if (!signal.aborted) onError('Audio could not seek to this timestamp. Check the recording or retry playback.');
      }
    },
    dispose() { disposed = true; pending?.abort(); },
  };
}
