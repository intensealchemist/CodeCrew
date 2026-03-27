import { jobStore } from "@/lib/job-store";
import fs from "fs/promises";
import path from "path";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET(
  req: Request,
  context: { params: { job_id: string } }
) {
  const jobId = context?.params?.job_id;
  if (!jobId) {
    return new Response("Missing job_id", { status: 400 });
  }

  const job = jobStore.getJob(jobId);

  const stream = new ReadableStream({
    async start(controller) {
      function sendEvent(type: string, data: any) {
        controller.enqueue(`data: ${JSON.stringify({ type, ...data })}\n\n`);
      }

      if (!job) {
        // Job not in memory. Check if it's on disk.
        try {
          const jobDir = jobStore.getJobDir(jobId);
          const stateData = await fs.readFile(path.join(jobDir, "job_state.json"), "utf-8");
          const state = JSON.parse(stateData);
          sendEvent("job_status", { status: state.status });
          if (state.status === "failed") {
            sendEvent("error", { message: state.error_message });
          } else if (state.status === "completed") {
            sendEvent("files_ready", {});
          }
          sendEvent("done", {});
          controller.close();
        } catch {
          sendEvent("error", { message: "Job not found" });
          controller.close();
        }
        return;
      }

      // Send current state
      sendEvent("job_status", { status: job.state.status });
      if (job.state.current_agent) {
        sendEvent("agent", { agent: job.state.current_agent });
      }

      // Send recent logs
      for (const log of job.logs) {
        sendEvent("log", { message: log });
      }

      if (job.state.status !== "running") {
        if (job.state.status === "failed") sendEvent("error", { message: job.state.error_message });
        if (job.state.status === "completed") sendEvent("files_ready", {});
        sendEvent("done", {});
        controller.close();
        return;
      }

      // Listen for updates
      const onLog = (msg: string) => sendEvent("log", { message: msg });
      const onAgent = (agent: string) => sendEvent("agent", { agent });
      const onStatus = (status: string) => sendEvent("job_status", { status });
      const onError = (message: string) => sendEvent("error", { message });
      const onFilesReady = () => sendEvent("files_ready", {});
      const onDone = () => {
        sendEvent("done", {});
        try { controller.close(); } catch {}
      };

      job.emitter.on("log", onLog);
      job.emitter.on("agent", onAgent);
      job.emitter.on("job_status", onStatus);
      job.emitter.on("error", onError);
      job.emitter.on("files_ready", onFilesReady);
      job.emitter.on("done", onDone);

      req.signal.addEventListener("abort", () => {
        job.emitter.off("log", onLog);
        job.emitter.off("agent", onAgent);
        job.emitter.off("job_status", onStatus);
        job.emitter.off("error", onError);
        job.emitter.off("files_ready", onFilesReady);
        job.emitter.off("done", onDone);
      });
    }
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "Connection": "keep-alive",
    },
  });
}
