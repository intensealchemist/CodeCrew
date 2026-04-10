const FASTAPI_URL = process.env.FASTAPI_URL || "http://127.0.0.1:8000";

export const dynamic = "force-dynamic";
export const revalidate = 0;
export const maxDuration = 3600;

export async function GET(
  req: Request,
  context: { params: { job_id: string } }
) {
  const jobId = context.params.job_id;
  if (!jobId) {
    return new Response("Missing job_id", { status: 400 });
  }

  try {
    const res = await fetch(`${FASTAPI_URL}/api/jobs/${jobId}/stream`, {
      method: "GET",
      // Forward AbortSignal to disconnect upstream if user unmounts/closes
      signal: req.signal,
    });

    if (!res.ok) {
      return new Response("Failed to fetch stream from backend", { status: res.status });
    }

    return new Response(res.body, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
      },
    });
  } catch (err) {
    return new Response("Stream error", { status: 500 });
  }
}
