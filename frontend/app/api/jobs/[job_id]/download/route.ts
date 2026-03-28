import { NextResponse } from "next/server";

const FASTAPI_URL = process.env.FASTAPI_URL || "http://127.0.0.1:8000";

export const dynamic = "force-dynamic";

export async function GET(
  _req: Request,
  context: { params: { job_id: string } }
) {
  const { job_id } = context.params;

  try {
    const res = await fetch(`${FASTAPI_URL}/api/jobs/${job_id}/download`, { cache: 'no-store' });
    
    if (!res.ok) {
        return NextResponse.json({ error: "Failed to download zip" }, { status: res.status });
    }
    
    return new Response(res.body, {
      status: 200,
      headers: {
        "Content-Type": "application/zip",
        "Content-Disposition": `attachment; filename="codecrew_${job_id}.zip"`,
      },
    });
  } catch (err) {
    return NextResponse.json({ error: "Backend uncreachable" }, { status: 500 });
  }
}
