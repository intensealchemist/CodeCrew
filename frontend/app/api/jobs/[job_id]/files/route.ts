import { NextResponse } from "next/server";

const FASTAPI_URL = process.env.FASTAPI_URL || "http://127.0.0.1:8000";

export const dynamic = "force-dynamic";

export async function GET(
  _req: Request,
  context: { params: { job_id: string } }
) {
  const jobId = context.params.job_id;
  try {
    const res = await fetch(`${FASTAPI_URL}/api/jobs/${jobId}/files`, { cache: 'no-store' });
    if (!res.ok) {
        return NextResponse.json({ error: "Files not found" }, { status: res.status });
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch (err) {
    return NextResponse.json({ error: "Backend uncreachable" }, { status: 500 });
  }
}
