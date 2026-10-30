'use client';

import type { StreamEvent } from '@/lib/api';
import { processingProgress } from '@/lib/reliability';
import { Mic, Brain, FileText, Check, AlertCircle } from 'lucide-react';

const STAGES = [
  { key: 'transcription', label: 'Transcribing', icon: Mic },
  { key: 'analysis', label: 'Analyzing', icon: Brain },
  { key: 'report', label: 'Reporting', icon: FileText },
];

export function UploadProgress({ events, error }: { events: StreamEvent[]; error?: string }) {
  const progress = processingProgress(events, error);
  if (!events.some(event => event.event === 'started') && !error) return null;
  return <div className="upload-progress" aria-live="polite">
    {STAGES.map(({ key, label, icon: Icon }) => {
      const done = progress.completedStages.includes(key);
      return <div key={key} className={`upload-stage ${done ? 'done' : ''} ${progress.activeStage === key ? 'active' : ''}`}><div className="upload-stage-icon">{done ? <Check className="h-4 w-4" /> : <Icon className="h-4 w-4" />}</div><span className="upload-stage-label">{label}</span></div>;
    })}
    {progress.terminal && <div className={`upload-stage ${progress.terminal === 'failed' ? 'error' : progress.terminal === 'review' ? 'review-progress' : 'done'}`}><div className="upload-stage-icon">{progress.terminal === 'complete' ? <Check className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}</div><span className="upload-stage-label">{progress.message}</span></div>}
  </div>;
}
