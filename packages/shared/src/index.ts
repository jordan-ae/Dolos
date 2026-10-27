export enum JobStage {
  Queued = "queued",
  Tts = "tts",
  Lipsync = "lipsync",
  Animating = "animating",
  Compositing = "compositing",
  Done = "done",
  Failed = "failed",
}

export interface GenerateRequest {
  script: string;
  voice_id?: string;
  avatar_ref?: string;
}

export interface GenerateResponse {
  job_id: string;
}

export interface JobResponse {
  job_id: string;
  stage: JobStage;
  error?: string | null;
  preview_url?: string | null;
  export_url?: string | null;
  created_at: string;
  updated_at: string;
}

export interface JobStatusMessage {
  job_id: string;
  stage: JobStage;
  error?: string | null;
  preview_url?: string | null;
  export_url?: string | null;
}

export const STAGE_ORDER: JobStage[] = [
  JobStage.Queued,
  JobStage.Tts,
  JobStage.Lipsync,
  JobStage.Animating,
  JobStage.Compositing,
  JobStage.Done,
];
