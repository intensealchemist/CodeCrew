import { NextResponse } from "next/server";
import { jobStore } from "@/lib/job-store";
import fs from "fs/promises";
import path from "path";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET(
  _req: Request,
  context: { params: { job_id: string } },
) {
  const jobId = context?.params?.job_id;
  if (!jobId) {
    return NextResponse.json({ error: "Missing job_id" }, { status: 400 });
  }

  const job = jobStore.getJob(jobId);
  if (job) {
    return NextResponse.json(job.state);
  }

  // Not in memory, try to read from disk
  try {
    const jobDir = jobStore.getJobDir(jobId);
    const stateData = await fs.readFile(path.join(jobDir, "job_state.json"), "utf-8");
    return NextResponse.json(JSON.parse(stateData));
  } catch (err) {
    return NextResponse.json({ error: "Job not found" }, { status: 404 });
  }
}
