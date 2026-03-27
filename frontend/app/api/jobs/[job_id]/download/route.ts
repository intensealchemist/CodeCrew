import { NextResponse } from "next/server";
import { jobStore } from "@/lib/job-store";
import fs from "fs/promises";
import path from "path";
import archiver from "archiver";
import { PassThrough } from "stream";

export const dynamic = "force-dynamic";

export async function GET(
  _req: Request,
  context: { params: { job_id: string } }
) {
  const { job_id } = context.params;

  try {
    const jobDir = jobStore.getJobDir(job_id);
    await fs.access(jobDir); // Check if exists

    // We can't use Next.js standard NextResponse to stream archiver easily without a custom ReadStream, 
    // but we can create a PassThrough stream.
    const passThrough = new PassThrough();
    const archive = archiver("zip", { zlib: { level: 9 } });

    archive.on("error", (err) => {
      passThrough.destroy(err);
    });

    archive.pipe(passThrough);

    // Append files from directory, ignoring job_state.json
    archive.glob("**/*", { 
      cwd: jobDir, 
      ignore: ["job_state.json", ".*", ".*/**"] 
    });

    archive.finalize();

    // @ts-ignore
    return new Response(passThrough, {
      status: 200,
      headers: {
        "Content-Type": "application/zip",
        "Content-Disposition": `attachment; filename="codecrew_${job_id}.zip"`,
      },
    });
  } catch (err) {
    return NextResponse.json({ error: "Failed to download zip" }, { status: 500 });
  }
}
