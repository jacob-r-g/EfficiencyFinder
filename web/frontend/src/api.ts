import type { BatchResult, JobStatus, PipelineSettings } from "./types";

export const CHUNK_SIZE = 8 * 1024 * 1024;

async function check(res: Response): Promise<Response> {
  if (res.ok) return res;
  let detail = res.statusText;
  try {
    const body = await res.json();
    if (typeof body.detail === "string") detail = body.detail;
  } catch {
    /* ignore non-JSON errors */
  }
  throw new Error(detail);
}

export async function createUpload(): Promise<string> {
  const res = await check(await fetch("/api/uploads", { method: "POST" }));
  const data: { upload_id: string } = await res.json();
  return data.upload_id;
}

export async function uploadFile(uploadId: string, file: File): Promise<void> {
  const chunks = Math.max(1, Math.ceil(file.size / CHUNK_SIZE));
  for (let i = 0; i < chunks; i++) {
    const blob = file.slice(i * CHUNK_SIZE, Math.min(file.size, (i + 1) * CHUNK_SIZE));
    const url =
      `/api/uploads/${uploadId}/files/${encodeURIComponent(file.name)}` +
      `?chunk=${i}&chunks=${chunks}`;
    await check(await fetch(url, { method: "PUT", body: blob }));
  }
}

export async function startJob(
  uploadId: string,
  fasta: string,
  fastqs: string[],
  settings: PipelineSettings,
  combineFastqs = false,
): Promise<JobStatus> {
  const res = await check(
    await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        upload_id: uploadId,
        fasta,
        fastqs,
        settings,
        combine_fastqs: combineFastqs,
      }),
    }),
  );
  return res.json();
}

export async function getJob(jobId: string): Promise<JobStatus> {
  const res = await check(await fetch(`/api/jobs/${jobId}`));
  return res.json();
}

export async function getResults(jobId: string): Promise<BatchResult> {
  const res = await check(await fetch(`/api/jobs/${jobId}/results`));
  return res.json();
}

export async function pollJob(
  jobId: string,
  onProgress: (status: JobStatus) => void,
): Promise<JobStatus> {
  for (;;) {
    const status = await getJob(jobId);
    onProgress(status);
    if (status.status === "done" || status.status === "failed") return status;
    await new Promise((r) => setTimeout(r, 400));
  }
}
