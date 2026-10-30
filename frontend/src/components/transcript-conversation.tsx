import { Bot, UserRound } from 'lucide-react';
import type { Run } from '../lib/api';
import { speakerLabel } from '../lib/evaluation';

type Props = {
  run: Run;
  highlightedTurn: number | null;
  registerTurn: (index: number, element: HTMLDivElement | null) => void;
};

export function TranscriptConversation({ run, highlightedTurn, registerTurn }: Props) {
  const turns = run.transcript_speakers;
  if (!turns?.length) {
    const text = run.evaluation?.raw_transcript || run.transcript_preview;
    return text ? <div className="review-stack"><p className="conversation-fallback-note">Speaker labels unavailable</p><div className="review-raw-transcript">{text}</div></div> : <section className="review-empty"><h3>Transcript unavailable</h3><p>No transcript was persisted for this run.</p></section>;
  }
  return <div className="conversation" role="list" aria-label="Call conversation">
    {turns.map((turn, index) => {
      const side = turn.role === 'agent' ? 'agent' : turn.role === 'customer' ? 'caller' : 'unknown';
      const Icon = side === 'agent' ? Bot : UserRound;
      const label = speakerLabel(turn).replace(/^Customer/, 'Caller');
      return <div role="listitem" className={`conversation-message conversation-message-${side}`} key={index}>
        <div className="conversation-avatar" aria-hidden="true"><Icon size={16} /></div>
        <div className="conversation-content">
          <span className="conversation-speaker">{label}</span>
          <div ref={element => registerTurn(index, element)} data-turn-index={index} className={`conversation-bubble${highlightedTurn === index ? ' turn-highlighted' : ''}`}>
            {highlightedTurn === index && <span className="conversation-evidence">Linked evidence</span>}
            <p>{turn.text}</p>
          </div>
        </div>
      </div>;
    })}
  </div>;
}
