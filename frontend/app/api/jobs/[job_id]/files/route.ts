import { NextResponse } from "next/server";
import { jobStore } from "@/lib/job-store";
import fs from "fs/promises";
import path from "path";

export const dynamic = "force-dynamic";

async function getFilesRecursively(dir: string, baseDir: string): Promise<string[]> {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  const files: string[] = [];

  for (const entry of entries) {
    if (
      entry.name === "job_state.json" || 
      entry.name.startsWith(".") ||
      entry.name.endsWith(".pack") ||
      entry.name.endsWith(".gz") ||
      entry.name.endsWith(".zip") ||
      entry.name === "node_modules" ||
      entry.name === "__pycache__"
    ) continue;
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await getFilesRecursively(fullPath, baseDir)));
    } else {
      files.push(path.relative(baseDir, fullPath).replace(/\\/g, "/"));
    }
  }
  return files;
}

export async function GET(
  _req: Request,
  context: { params: { job_id: string } }
) {
  const jobId = context.params.job_id;
  try {
    const jobDir = jobStore.getJobDir(jobId);
    
    // Check if dir exists
    await fs.access(jobDir);
    
    const files = await getFilesRecursively(jobDir, jobDir);
    return NextResponse.json({ files });
  } catch (err) {
    return NextResponse.json({ error: "Job files not found" }, { status: 404 });
  }
}
