"use client";

import { useEffect, useState } from "react";

import { JobStage, JobStatusMessage } from "@dolos/shared";

import { WS_URL } from "@/lib/api";

export function useJobSocket(jobId: string, initial?: JobStatusMessage) {
  const [status, setStatus] = useState<JobStatusMessage | undefined>(initial);

  useEffect(() => {
    const socket = new WebSocket(`${WS_URL}/ws/jobs/${jobId}`);

    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      if (payload.type === "ping") return;
      setStatus(payload as JobStatusMessage);
    };

    return () => socket.close();
  }, [jobId]);

  const isTerminal = status?.stage === JobStage.Done || status?.stage === JobStage.Failed;

  return { status, isTerminal };
}
