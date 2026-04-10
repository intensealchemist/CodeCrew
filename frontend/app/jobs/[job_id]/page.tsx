"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  CheckCircle2, 
  CircleDashed, 
  Loader2, 
  XCircle, 
  TerminalSquare, 
  FileCode2,
  ArrowRight,
  Trash2,
  LayoutDashboard
} from "lucide-react";

type JobStatus = "running" | "completed" | "failed";
type AgentLabel =
  | "Researcher"
  | "SpecValidator"
  | "Architect"
  | "FilePlanner"
  | "Coder"
  | "QAAgent"
  | "ReadmeAgent"
  | null;
type PipelineAgent = Exclude<AgentLabel, null>;
type TerminalAgent = PipelineAgent | "System";

const PIPELINE_STEPS: PipelineAgent[] = [
  "Researcher",
  "SpecValidator",
  "Architect",
  "FilePlanner",
  "Coder",
  "QAAgent",
  "ReadmeAgent",
];

export default function JobPage({ params }: { params: { job_id: string } }) {
  const jobId = params.job_id;

  const [task, setTask] = useState<string>("");
  const [status, setStatus] = useState<JobStatus>("running");
  const [currentAgent, setCurrentAgent] = useState<AgentLabel>(null);
  const [logsByAgent, setLogsByAgent] = useState<Record<string, string[]>>({
    System: [],
  });
  const [activeTerminal, setActiveTerminal] = useState<TerminalAgent>("System");
  const [filesReady, setFilesReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorDetails, setErrorDetails] = useState<string | null>(null);
  const [token] = useState<string | null>(
    typeof window === "undefined" ? null : localStorage.getItem("codecrew_token"),
  );
  const [deleting, setDeleting] = useState(false);

  const errorDetailsFetchedRef = useRef(false);
  const streamAgentRef = useRef<TerminalAgent>("System");

  const sourceRef = useRef<EventSource | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const currentIdx = useMemo(() => {
    if (!currentAgent) return -1;
    return PIPELINE_STEPS.indexOf(currentAgent);
  }, [currentAgent]);

  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [activeTerminal, logsByAgent]);

  useEffect(() => {
    let alive = true;

    fetch(`/api/jobs/${jobId}`)
      .then((r) => r.json())
      .then((data) => {
        if (!alive) return;
        setTask(data.task ?? "");
        setStatus(data.status ?? "running");
        setCurrentAgent(data.current_agent ?? null);
        if (typeof data.current_agent === "string") {
          const restoredAgent = data.current_agent as PipelineAgent;
          streamAgentRef.current = restoredAgent;
          setActiveTerminal(restoredAgent);
        }

        if (data.status === "failed" && data.error_message) {
          const full = String(data.error_message);
          setError(full.slice(0, 200));
          setErrorDetails(full);
          errorDetailsFetchedRef.current = true;
        }
      })
      .catch(() => {});

    const source = new EventSource(`/api/jobs/${jobId}/stream`);
    sourceRef.current = source;

    source.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as { type?: string; [k: string]: any };
        const type = msg.type;

        if (type === "log" && typeof msg.message === "string") {
          const agentForLog = streamAgentRef.current || "System";
          setLogsByAgent((prev) => ({
            ...prev,
            [agentForLog]: [...(prev[agentForLog] ?? []), msg.message].slice(-500),
          }));
        } else if (type === "agent" && typeof msg.agent === "string") {
          const nextAgent = msg.agent as PipelineAgent;
          streamAgentRef.current = nextAgent;
          setCurrentAgent(nextAgent);
          setActiveTerminal(nextAgent);
        } else if (type === "job_status" && typeof msg.status === "string") {
          setStatus(msg.status as JobStatus);
        } else if (type === "files_ready") {
          setFilesReady(true);
        } else if (type === "error") {
          setError(String(msg.message ?? "Job error"));
          if (!errorDetailsFetchedRef.current) {
            errorDetailsFetchedRef.current = true;
            fetch(`/api/jobs/${jobId}`)
              .then((r) => r.json())
              .then((data) => {
                if (!alive) return;
                if (data?.error_message) setErrorDetails(String(data.error_message));
              })
              .catch(() => {});
          }
        } else if (type === "done") {
          source.close();
        }
      } catch {
        // Ignore malformed
      }
    };

    source.onerror = () => {
      if (!alive) return;
    };

    return () => {
      alive = false;
      source.close();
    };
  }, [jobId]);

  const visibleLogs = useMemo(() => {
    return logsByAgent[activeTerminal] ?? [];
  }, [activeTerminal, logsByAgent]);

  async function deleteJob() {
    if (deleting) return;
    const ok = window.confirm("Delete this job and its generated files?");
    if (!ok) return;
    setDeleting(true);
    try {
      await fetch(`/api/jobs/${jobId}/delete`, {
        method: "DELETE",
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      });
      window.location.href = token ? "/dashboard" : "/";
    } finally {
      setDeleting(false);
    }
  }

  return (
    <main className="min-h-screen p-6 md:p-12 relative flex flex-col items-center">
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden -z-10 pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[500px] h-[500px] bg-primary/20 rounded-full blur-[120px] animate-blob mix-blend-screen" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[500px] h-[500px] bg-blue-500/20 rounded-full blur-[120px] animate-blob animation-delay-2000 mix-blend-screen" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-purple-500/10 rounded-full blur-[120px] animate-blob animation-delay-4000 mix-blend-screen" />
      </div>

      <div className="w-full max-w-5xl space-y-8 mt-8">
        <motion.div 
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col md:flex-row md:items-end justify-between gap-4"
        >
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/5 border border-white/10 text-xs font-medium text-white/70 mb-4">
              <div className={`w-2 h-2 rounded-full ${status === 'running' ? 'bg-primary animate-pulse' : status === 'failed' ? 'bg-destructive' : 'bg-green-500'}`} />
              Job: {jobId.split("-")[0]}...
            </div>

          <div className="flex items-center gap-2">
            {token ? (
              <Link href="/dashboard" className="secondary-button flex items-center gap-2">
                <LayoutDashboard className="w-4 h-4" />
                Dashboard
              </Link>
            ) : null}
            <button
              onClick={deleteJob}
              disabled={deleting}
              className="secondary-button flex items-center gap-2"
              title="Delete job"
            >
              <Trash2 className="w-4 h-4" />
              {deleting ? "Deleting..." : "Delete"}
            </button>
          </div>
            <h1 className="text-3xl md:text-4xl font-bold tracking-tight text-white mb-2">Live Pipeline Run</h1>
            <p className="text-lg text-white/60 max-w-2xl line-clamp-2">
              <span className="font-semibold text-white/80">Task:</span> {task || "Loading..."}
            </p>
          </div>

          <AnimatePresence>
            {filesReady && status === "completed" && (
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                whileHover={{ scale: 1.05 }}
              >
                <Link
                  href={`/jobs/${jobId}/files`}
                  className="primary-button flex items-center gap-2 shadow-lg shadow-primary/20"
                >
                  <FileCode2 className="w-5 h-5" />
                  View Generated Files
                  <ArrowRight className="w-4 h-4 ml-1" />
                </Link>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>

        {error && (
          <motion.div 
             initial={{ opacity: 0, height: 0 }}
             animate={{ opacity: 1, height: "auto" }}
             className="bg-destructive/10 border border-destructive/20 text-destructive-foreground px-4 py-3 rounded-xl text-sm flex items-center gap-2"
          >
            <XCircle className="w-4 h-4" />
            <div className="flex flex-col gap-1">
              <span>
                <b>Error:</b> {error}
              </span>
              {errorDetails ? (
                <pre className="text-xs text-white/50 whitespace-pre-wrap max-h-64 overflow-auto">
                  {errorDetails}
                </pre>
              ) : null}
            </div>
          </motion.div>
        )}

        <div className="grid grid-cols-1 xl:grid-cols-[340px_1fr] gap-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="glass-card rounded-3xl p-4 md:p-5"
          >
            <div className="space-y-3">
              {PIPELINE_STEPS.map((label, idx) => {
                const isDone =
                  idx < currentIdx ||
                  (status === "completed" && currentIdx >= 0 && idx <= currentIdx);
                const isActive = status === "running" && idx === currentIdx;
                const isFailed = status === "failed" && idx === currentIdx;
                return (
                  <div
                    key={label}
                    className={`
                      rounded-xl px-4 py-3 border flex items-center justify-between transition-colors
                      ${isActive ? "bg-primary/15 border-primary/50" : ""}
                      ${isDone ? "bg-green-500/10 border-green-500/30" : ""}
                      ${isFailed ? "bg-destructive/10 border-destructive/30" : ""}
                      ${!isActive && !isDone && !isFailed ? "bg-white/5 border-white/10" : ""}
                    `}
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-black/20">
                        {isDone && <CheckCircle2 className="w-4 h-4 text-green-400" />}
                        {isActive && <Loader2 className="w-4 h-4 text-primary animate-spin" />}
                        {isFailed && <XCircle className="w-4 h-4 text-destructive" />}
                        {!isActive && !isDone && !isFailed && <CircleDashed className="w-4 h-4 text-white/40" />}
                      </div>
                      <div className="text-sm font-semibold text-white/90">{label}</div>
                    </div>
                    <div className="text-[10px] uppercase tracking-wider text-white/50">
                      {status === "failed" && idx === currentIdx ? "Failed" : isDone ? "Done" : isActive ? "Active" : "Waiting"}
                    </div>
                  </div>
                );
              })}
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="glass-card rounded-3xl overflow-hidden flex flex-col shadow-[0_20px_50px_rgba(0,0,0,0.5)] border border-white/10"
          >
            <div className="bg-[#1e1e1e]/60 backdrop-blur-md border-b border-white/5 py-3 px-6 flex items-center gap-3">
              <div className="flex gap-2 mr-2">
                <div className="w-3 h-3 rounded-full bg-red-500/80 shadow-[0_0_10px_rgba(239,68,68,0.5)]" />
                <div className="w-3 h-3 rounded-full bg-yellow-500/80 shadow-[0_0_10px_rgba(234,179,8,0.5)]" />
                <div className="w-3 h-3 rounded-full bg-green-500/80 shadow-[0_0_10px_rgba(34,197,94,0.5)]" />
              </div>
              <TerminalSquare className="w-5 h-5 text-white/50" />
              <span className="text-sm font-semibold text-white/70">Live Thought-Action Terminals</span>
            </div>

            <div className="px-4 pt-4 pb-2 flex flex-wrap gap-2 border-b border-white/5 bg-black/10">
              <button
                onClick={() => setActiveTerminal("System")}
                className={`
                  px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors
                  ${activeTerminal === "System" ? "bg-primary/20 border-primary/50 text-primary" : "bg-white/5 border-white/10 text-white/60 hover:bg-white/10"}
                `}
              >
                System ({logsByAgent.System?.length ?? 0})
              </button>
              {PIPELINE_STEPS.map((agent) => (
                <button
                  key={agent}
                  onClick={() => setActiveTerminal(agent)}
                  className={`
                    px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors
                    ${activeTerminal === agent ? "bg-primary/20 border-primary/50 text-primary" : "bg-white/5 border-white/10 text-white/60 hover:bg-white/10"}
                  `}
                >
                  {agent} ({logsByAgent[agent]?.length ?? 0})
                </button>
              ))}
            </div>

            <div className="bg-[#0A0A0B]/90 backdrop-blur-md p-6 h-[420px] overflow-y-auto font-mono text-sm leading-relaxed scroll-smooth scrollbar-hide">
              {visibleLogs.length ? (
                <div className="space-y-1">
                  {visibleLogs.map((log, i) => (
                    <div key={`${activeTerminal}-${i}`} className="text-white/80 break-words hover:bg-white/5 px-2 py-1 rounded">
                      <span className="text-primary/60 mr-2 opacity-50">{">"}</span>{log}
                    </div>
                  ))}
                  {status === "running" && activeTerminal === currentAgent && (
                    <div className="text-primary/80 animate-pulse mt-4 px-2">
                      <span className="mr-2">{">"}</span> Agent is thinking...
                    </div>
                  )}
                  <div ref={logsEndRef} />
                </div>
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-white/30 gap-3">
                  <TerminalSquare className="w-8 h-8 opacity-50" />
                  <p>No events for {activeTerminal} yet.</p>
                </div>
              )}
            </div>
          </motion.div>
        </div>
      </div>
    </main>
  );
}
