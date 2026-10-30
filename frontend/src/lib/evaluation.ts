import type { Run } from "./api";

type VerdictInput = Pick<Run, "run_id" | "status" | "hallucination_detected" | "layer_scores" | "evaluation">;

export function runVerdict(run: VerdictInput): string {
  if (run.run_id.startsWith("demo-")) return "Synthetic demo";
  if (run.status === "failed") return "Evaluation failed";
  if (run.status === "partial" || run.evaluation?.harness?.validation_passed === false) return "Needs review";
  if (Object.values(run.layer_scores ?? {}).some((value) => !Number.isFinite(value) || value < 0 || value > 1)) return "Invalid legacy scores";
  return run.hallucination_detected ? "Model flagged" : "Not flagged · unverified";
}

export function validScore(value: number | null): number | null {
  return value != null && Number.isFinite(value) && value >= 0 && value <= 1 ? value : null;
}

export function layerStatus(score: number | null): "pass" | "warning" | "fail" | "na" | "invalid" {
  if (score == null) return "na";
  if (!Number.isFinite(score) || score < 0 || score > 100) return "invalid";
  if (score >= 80) return "pass";
  if (score >= 50) return "warning";
  return "fail";
}

type SpeakerTurn = NonNullable<Run["transcript_speakers"]>[number];

export function speakerLabel(turn: SpeakerTurn): string {
  const role = turn.role === "agent" ? "Agent" : turn.role === "customer" ? "Customer" : turn.role === "other" ? "Other" : null;
  if (role == null) return `Speaker ${turn.speaker} · role unknown`;
  if (turn.role_source === "transcript_label") return role;
  if (turn.role_source === "model_inference") return `${role} · inferred`;
  return `${role} · unverified`;
}
