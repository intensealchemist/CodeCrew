import { NextResponse } from "next/server";

const FASTAPI_URL = process.env.FASTAPI_URL || "http://127.0.0.1:8000";

export const dynamic = "force-dynamic";

export async function DELETE(req: Request, context: { params: { job_id: string } }) {
  const jobId = context.params.job_id;
  const auth = req.headers.get("authorization");

  if (!jobId) {
    return NextResponse.json({ error: "Missing job_id" }, { status: 400 });
  }

  try {
    const res = await fetch(`${FASTAPI_URL}/api/jobs/${jobId}`, {
      method: "DELETE",
      headers: {
        ...(auth ? { Authorization: auth } : {}),
      },
    });

    const data = await res.json().catch(() => null);
    return NextResponse.json(data ?? {}, { status: res.status });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
