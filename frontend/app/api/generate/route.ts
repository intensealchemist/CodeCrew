import { NextResponse } from "next/server";
import { jobStore } from "@/lib/job-store";

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const task = body.task;
    const provider = body.llm_provider || "free_ha";

    if (!task) {
      return NextResponse.json({ error: "Task is required" }, { status: 400 });
    }

    const jobId = await jobStore.createJob(task, provider);
    
    return NextResponse.json({ job_id: jobId }, { status: 200 });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
