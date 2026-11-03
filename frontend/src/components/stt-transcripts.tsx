import { audioTime, type STTTranscript } from '../lib/stt-quality';

type Props = {
  bolna: STTTranscript;
  reference: STTTranscript | null;
  onSeek: (seconds: number) => void;
  inferredRoles?: Record<string, 'caller' | 'agent'>;
};

export function STTTranscripts({ bolna, reference, onSeek, inferredRoles = {} }: Props) {
  const sourceTitle = bolna.source === 'synthetic' ? 'Synthetic source transcript' : 'Bolna transcript';
  const referenceTitle = reference?.source === 'synthetic' ? 'Synthetic comparison fixture' : reference?.human_verified ? 'Human-verified reference' : 'Deepgram reference';
  return <section className="review-stack">
    <div className="review-section-heading"><h3>Compare transcripts</h3><span>Read each source independently</span></div>
    <p className="review-description">Messages are grouped by source. Rows are not time-aligned; timestamps appear only where supplied.</p>
    <div className="stt-transcript-columns">
      {[{ title: sourceTitle, transcript: bolna }, { title: referenceTitle, transcript: reference }].map(({ title, transcript }) => <section className="stt-transcript-panel" key={title} aria-label={title}>
        <h4>{title}</h4>
        {!transcript?.segments.length ? <p className="review-description">{title === 'Bolna transcript' ? 'Original transcript unavailable.' : 'No reference transcript is available yet.'}</p> : <ol className="conversation stt-transcript-messages" aria-label={`${title} messages`}>
          {transcript.segments.map((segment, index) => <li className={`conversation-message conversation-message-${segment.role}`} key={index}>
            <div className="conversation-content">
              <span className="conversation-speaker">{segment.role === 'unknown' ? `${segment.speaker} · ${inferredRoles[segment.speaker] ? `inferred ${inferredRoles[segment.speaker]}` : 'role unknown'}` : segment.role === 'caller' ? 'Caller' : 'Agent'}</span>
              <div className="conversation-bubble"><p>{segment.text}</p></div>
              {segment.start === null ? <span className="stt-message-time">Timing unavailable</span> : <button className="stt-message-time evidence-jump" aria-label={`Listen to ${title} at ${audioTime(segment.start)}`} onClick={() => { if (segment.start !== null) onSeek(segment.start); }}>{audioTime(segment.start)}</button>}
            </div>
          </li>)}
        </ol>}
      </section>)}
    </div>
  </section>;
}
