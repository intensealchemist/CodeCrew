import { NextResponse } from "next/server";
import { jobStore } from "@/lib/job-store";
import fs from "fs/promises";
import path from "path";

export const dynamic = "force-dynamic";

export async function GET(
  _req: Request,
  context: { params: { job_id: string; filepath: string[] } }
) {
  const { job_id, filepath } = context.params;

  try {
    const jobDir = jobStore.getJobDir(job_id);
    // Join all path segments to support nested files like src/utils/helper.py
    const relativePath = filepath.join("/");
    const targetPath = path.join(jobDir, relativePath);

    // Prevent directory traversal
    const resolvedTarget = path.resolve(targetPath);
    const resolvedJobDir = path.resolve(jobDir);
    if (!resolvedTarget.startsWith(resolvedJobDir)) {
      return NextResponse.json({ error: "Invalid path" }, { status: 400 });
    }

    const content = await fs.readFile(targetPath, "utf-8");
    return NextResponse.json({ content });
  } catch (err) {
    return NextResponse.json({ error: "File not found" }, { status: 404 });
  }
}
