"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { createJob } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

export default function HomePage() {
  const router = useRouter();
  const [script, setScript] = useState("");
  const [voiceId, setVoiceId] = useState("");
  const [avatarRef, setAvatarRef] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const { job_id } = await createJob({
        script,
        voice_id: voiceId || undefined,
        avatar_ref: avatarRef || undefined,
      });
      router.push(`/jobs/${job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-6 px-6 py-16">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Dolos</h1>
        <p className="text-sm text-slate-500">Type a script, generate a talking-head video.</p>
      </div>

      <form className="space-y-4" onSubmit={handleSubmit}>
        <div className="space-y-1">
          <label className="text-sm font-medium text-slate-700" htmlFor="script">
            Script
          </label>
          <Textarea
            id="script"
            required
            rows={8}
            placeholder="Write what you want the avatar to say..."
            value={script}
            onChange={(e) => setScript(e.target.value)}
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1">
            <label className="text-sm font-medium text-slate-700" htmlFor="voice">
              Voice ID (optional)
            </label>
            <Input id="voice" value={voiceId} onChange={(e) => setVoiceId(e.target.value)} />
          </div>
          <div className="space-y-1">
            <label className="text-sm font-medium text-slate-700" htmlFor="avatar">
              Avatar image URL (optional)
            </label>
            <Input id="avatar" value={avatarRef} onChange={(e) => setAvatarRef(e.target.value)} />
          </div>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <Button type="submit" disabled={submitting || !script.trim()} className="w-full">
          {submitting ? "Starting..." : "Generate"}
        </Button>
      </form>
    </main>
  );
}
