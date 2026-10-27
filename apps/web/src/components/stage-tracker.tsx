import { JobStage, STAGE_ORDER } from "@dolos/shared";

import { Progress } from "@/components/ui/progress";

const LABELS: Record<JobStage, string> = {
  [JobStage.Queued]: "Queued",
  [JobStage.Tts]: "Generating voice",
  [JobStage.Lipsync]: "Lip-syncing",
  [JobStage.Animating]: "Animating",
  [JobStage.Compositing]: "Compositing",
  [JobStage.Done]: "Done",
  [JobStage.Failed]: "Failed",
};

export function StageTracker({ stage }: { stage: JobStage }) {
  if (stage === JobStage.Failed) {
    return <p className="text-sm font-medium text-red-600">Generation failed</p>;
  }

  const currentIndex = STAGE_ORDER.indexOf(stage);
  const progress = ((currentIndex + 1) / STAGE_ORDER.length) * 100;

  return (
    <div className="space-y-3">
      <Progress value={progress} />
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
        {STAGE_ORDER.map((s, i) => (
          <li
            key={s}
            className={
              i < currentIndex
                ? "text-slate-400 line-through"
                : i === currentIndex
                  ? "font-semibold text-slate-900"
                  : "text-slate-400"
            }
          >
            {LABELS[s]}
          </li>
        ))}
      </ul>
    </div>
  );
}
