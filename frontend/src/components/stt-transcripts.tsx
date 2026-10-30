import { audioTime, type STTTranscript } from '../lib/stt-quality';

type Props = {
  bolna: STTTranscript;
  reference: STTTranscript | null;
  onSeek: (seconds: number) => void;
};

export function STTTranscripts({ bolna, reference, onSeek }: Props) {
  return <section className="review-stack">
    <div className="review-section-heading"><h3>Compare transcripts</h3><span>Read each source independently</span></div>
    <p className="review-description">Messages are grouped by source. Rows are not time-aligned; timestamps appear only where supplied.</p>
    <div className="stt-transcript-columns">
      {[{ title: 'Bolna transcript', transcript: bolna }, { title: reference?.human_verified ? 'Human-verified reference' : 'Deepgram reference', transcript: reference }].map(({ title, transcript }) => <section className="stt-transcript-panel" key={title} aria-label={title}>
        <h4>{title}</h4>
        {!transcript?.segments.length ? <p className="review-description">{title === 'Bolna transcript' ? 'Original transcript unavailable.' : 'No reference transcript is available yet.'}</p> : <ol className="conversation stt-transcript-messages" aria-label={`${title} messages`}>
          {transcript.segments.map((segment, index) => <li className={`conversation-message conversation-message-${segment.role}`} key={index}>
            <div className="conversation-content">
              <span className="conversation-speaker">{segment.role === 'unknown' ? `${segment.speaker} · role unknown` : segment.role === 'caller' ? 'Caller' : 'Agent'}</span>
              <div className="conversation-bubble"><p>{segment.text}</p></div>
              {segment.start === null ? <span className="stt-message-time">Timing unavailable</span> : <button className="stt-message-time evidence-jump" aria-label={`Listen to ${title} at ${audioTime(segment.start)}`} onClick={() => { if (segment.start !== null) onSeek(segment.start); }}>{audioTime(segment.start)}</button>}
            </div>
          </li>)}
        </ol>}
      </section>)}
    </div>
  </section>;
}
