import { spawn, ChildProcess } from "child_process";
import fs from "fs/promises";
import path from "path";
import { EventEmitter } from "events";
import { randomUUID } from "crypto";
import readline from "readline";

export interface JobState {
  id: string;
  task: string;
  provider: string;
  status: "running" | "completed" | "failed";
  current_agent: string | null;
  error_message: string | null;
  created_at: number;
}

const JOBS_DIR = process.env.CODECREW_JOBS_DIR
  ? path.resolve(process.env.CODECREW_JOBS_DIR)
  : path.resolve(process.cwd(), "..", "codecrew_jobs");

// Next.js fast refresh clears module-level variables. We must use globalThis.
const globalForJobStore = globalThis as unknown as {
  activeJobs: Map<string, {
    state: JobState;
    process?: ChildProcess;
    emitter: EventEmitter;
    logs: string[];
  }>;
};

const activeJobs = globalForJobStore.activeJobs || new Map();
if (process.env.NODE_ENV !== "production") globalForJobStore.activeJobs = activeJobs;

export const jobStore = {
  async init() {
    await fs.mkdir(JOBS_DIR, { recursive: true });
  },

  getJobDir(jobId: string) {
    return path.join(JOBS_DIR, jobId);
  },

  async createJob(task: string, provider: string): Promise<string> {
    await this.init();
    const jobId = randomUUID();
    const jobDir = this.getJobDir(jobId);
    await fs.mkdir(jobDir, { recursive: true });

    const state: JobState = {
      id: jobId,
      task,
      provider,
      status: "running",
      current_agent: null,
      error_message: null,
      created_at: Date.now(),
    };

    activeJobs.set(jobId, {
      state,
      emitter: new EventEmitter(),
      logs: [],
    });

    // Write initial state to disk so it can be recovered/polled if memory is lost
    await fs.writeFile(path.join(jobDir, "job_state.json"), JSON.stringify(state, null, 2)).catch(() => {});

    this._startJob(jobId);
    return jobId;
  },

  getJob(jobId: string) {
    return activeJobs.get(jobId);
  },

  _startJob(jobId: string) {
    const job = activeJobs.get(jobId);
    if (!job) return;

    const { state, emitter, logs } = job;
    const jobDir = this.getJobDir(jobId);

    // Assuming we are running from frontend folder, python CLI is in the PATH if activated.
    // Or we should run `codecrew` directly. We'll pass `--output-dir` and environment variables.
    
    // We launch it in the parent directory where pyproject.toml might live or just let it run.
    const runDir = path.resolve(process.cwd(), "..");
    
    // Explicitly point to the virtual environment binary
    const isWin = process.platform === "win32";
    const exePath = isWin
      ? path.join(runDir, ".venv", "Scripts", "codecrew.exe")
      : path.join(runDir, ".venv", "bin", "codecrew");
    
    // Prepare env variables
    const env = { ...process.env, LLM_PROVIDER: state.provider, DO_NOT_TRACK: "True", ANONYMIZED_TELEMETRY: "False" };

    const child = spawn(
      exePath,
      [
        "--task", state.task,
        "--output-dir", jobDir,
      ],
      {
        cwd: runDir, // Run in D:/GH/CodeCrew
        env,
        // Do NOT use shell: true on Windows — cmd.exe joins args into a string
        // and re-splits on spaces, breaking multi-word task descriptions.
        // The explicit .exe path works fine without shell mode.
        windowsHide: true,
      }
    );

    job.process = child;

    const handleStdout = (data: Buffer) => {
      const text = data.toString("utf-8");
      
      // Basic heuristic to find agent names:
      // CodeCrew CLI prints things like: "Agent: Researcher", "Task:...", "Working..."
      // Or we can just capture the logs.
      const lines = text.split("\n");
      for (let line of lines) {
        line = line.replace(/\r/g, "");
        if (!line.trim()) continue;
        
        // Save log
        logs.push(line);
        if (logs.length > 2000) logs.shift(); // keep last 2000
        emitter.emit("log", line);

        // Detect agent
        const agentMatch = line.match(/^## \[([^\]]+)\]/);
        const knownAgents = [
          "Researcher",
          "SpecValidator",
          "Architect",
          "FilePlanner",
          "Coder",
          "QAAgent",
          "ReadmeAgent",
        ];
        if (agentMatch && knownAgents.includes(agentMatch[1])) {
          state.current_agent = agentMatch[1];
          emitter.emit("agent", state.current_agent);
        } else {
          const fallback = knownAgents.find((agent) => line.toLowerCase().includes(agent.toLowerCase()));
          if (fallback) {
            state.current_agent = fallback;
            emitter.emit("agent", state.current_agent);
          }
        }
        
        // Next.js SSE format relies on these emits
      }
    };

    child.stdout.on("data", handleStdout);
    child.stderr.on("data", handleStdout);

    child.on("close", (code) => {
      if (code === 0) {
        state.status = "completed";
      } else {
        state.status = "failed";
        state.error_message = state.error_message || `Process exited with code ${code}`;
      }
      emitter.emit("job_status", state.status);
      emitter.emit("files_ready");
      emitter.emit("done");
      
      // Save state
      fs.writeFile(path.join(jobDir, "job_state.json"), JSON.stringify(state, null, 2)).catch(() => {});
    });
    
    child.on("error", (err) => {
      state.status = "failed";
      state.error_message = err.message;
      emitter.emit("error", err.message);
      emitter.emit("job_status", state.status);
      emitter.emit("done");
    });
  }
};
