import { NextResponse } from "next/server";
const FASTAPI_URL = process.env.FASTAPI_URL || "http://127.0.0.1:8000";
const FETCH_TIMEOUT_MS = 5000;
const FETCH_RETRIES = 1;

export const dynamic = "force-dynamic";

export async function GET(
  _req: Request,
  context: { params: { job_id: string; filepath: string[] } }
) {
  const { job_id, filepath } = context.params;
  const relativePath = filepath.join("/");

  try {
    const encodedPath = relativePath
      .split("/")
      .map((segment) => encodeURIComponent(segment))
      .join("/");
    const url = `${FASTAPI_URL}/api/jobs/${job_id}/files/${encodedPath}`;
    let res: Response | null = null;
    let lastError: unknown = null;
    const maxAttempts = FETCH_RETRIES + 1;

    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      try {
        res = await fetch(url, {
          cache: "no-store",
          signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
        });
        break;
      } catch (error) {
        lastError = error;
        if (attempt === maxAttempts - 1) {
          throw error;
        }
      }
    }

    if (!res) {
      throw lastError ?? new Error("Request failed");
    }

    const contentType = res.headers.get("content-type") || "";

    if (!res.ok) {
      const textResponse = res.clone();
      const body = contentType.includes("application/json")
        ? await res.json().catch(() => null)
        : null;
      const detail =
        body &&
        typeof body === "object" &&
        "detail" in body &&
        typeof body.detail === "string"
          ? body.detail
          : null;
      const errorMessage = detail ?? await textResponse.text().catch(() => "Unknown error");
      return NextResponse.json(
        { error: errorMessage || "File not found" },
        { status: res.status }
      );
    }

    if (contentType.includes("application/json")) {
      const data = await res.json();
      return NextResponse.json(data);
    }

    if (contentType.startsWith("text/")) {
      const content = await res.text().catch(() => "");
      return NextResponse.json({ content });
    }

    return NextResponse.json(
      { error: `Binary file preview is not supported for content-type: ${contentType || "unknown"}` },
      { status: 415 }
    );
  } catch (err: unknown) {
    if (err instanceof Error && err.name === "AbortError") {
      return NextResponse.json({ error: "Backend request timed out" }, { status: 504 });
    }
    return NextResponse.json({ error: "Backend network error" }, { status: 502 });
  }
}
