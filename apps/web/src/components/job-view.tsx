"use client";

import { useEffect, useState } from "react";

import { JobStage } from "@dolos/shared";

import { exportJob, getJob } from "@/lib/api";
import { useJobSocket } from "@/hooks/useJobSocket";
import { StageTracker } from "@/components/stage-tracker";
import { Button } from "@/components/ui/button";

export function JobView({ jobId }: { jobId: string }) {
  const { status } = useJobSocket(jobId);
  const [exporting, setExporting] = useState(false);
  const [exportUrl, setExportUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!exporting) return;
    const interval = setInterval(async () => {
      const job = await getJob(jobId);
      if (job.export_url) {
        setExportUrl(job.export_url);
        setExporting(false);
      } else if (job.stage === JobStage.Failed) {
        setError(job.error ?? "Export failed");
        setExporting(false);
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [exporting, jobId]);

  async function handleExport() {
    setError(null);
    setExporting(true);
    try {
      await exportJob(jobId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start export");
      setExporting(false);
    }
  }

  if (!status) {
    return <p className="text-sm text-slate-500">Connecting...</p>;
  }

  return (
    <div className="space-y-6">
      <StageTracker stage={status.stage} />

      {status.error && <p className="text-sm text-red-600">{status.error}</p>}

      {status.preview_url && (
        <div className="space-y-3">
          <video className="w-full rounded-md border border-slate-200" src={status.preview_url} controls />
          <Button onClick={handleExport} disabled={exporting || !!exportUrl} variant="outline">
            {exportUrl ? "Export ready" : exporting ? "Rendering full-res..." : "Export full-res"}
          </Button>
          {exportUrl && (
            <a
              className="block text-sm font-medium text-slate-900 underline"
              href={exportUrl}
              download
            >
              Download export
            </a>
          )}
        </div>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}
