import { JobView } from "@/components/job-view";

export default async function JobPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-6 px-6 py-16">
      <h1 className="text-xl font-semibold text-slate-900">Generating video</h1>
      <JobView jobId={id} />
    </main>
  );
}
