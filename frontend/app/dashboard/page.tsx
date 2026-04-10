"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  History,
  LogOut,
  RefreshCw,
  ArrowRight,
  Play,
  ShieldAlert,
  CheckCircle2,
  XCircle,
  Clock3,
  Settings,
  Info,
  User,
  BarChart3,
} from "lucide-react";

type JobItem = {
  job_id: string;
  task: string;
  llm_provider: string;
  status: string;
  created_at: string | null;
};

function statusIcon(status: string) {
  if (status === "completed") return <CheckCircle2 className="w-4 h-4 text-green-400" />;
  if (status === "failed") return <XCircle className="w-4 h-4 text-red-400" />;
  if (status === "running") return <Play className="w-4 h-4 text-primary" />;
  return <Clock3 className="w-4 h-4 text-white/40" />;
}

export default function DashboardPage() {
  const [token, setToken] = useState<string | null>(null);
  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setToken(localStorage.getItem("codecrew_token"));
  }, []);

  async function loadJobs(currentToken: string) {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/me/jobs", {
        headers: {
          Authorization: `Bearer ${currentToken}`,
        },
        cache: "no-store",
      });
      const data = (await res.json()) as any;
      if (!res.ok) {
        throw new Error(data?.detail || data?.error || "Failed to load jobs");
      }
      setJobs((data?.jobs ?? []) as JobItem[]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load jobs");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!token) return;
    loadJobs(token);
  }, [token]);

  const grouped = useMemo(() => {
    const by = { running: 0, completed: 0, failed: 0, other: 0 };
    for (const j of jobs) {
      if (j.status === "running") by.running++;
      else if (j.status === "completed") by.completed++;
      else if (j.status === "failed") by.failed++;
      else by.other++;
    }
    return by;
  }, [jobs]);

  function logout() {
    localStorage.removeItem("codecrew_token");
    setToken(null);
    setJobs([]);
  }

  return (
    <main className="min-h-screen p-6 md:p-12">
      <div className="w-full max-w-6xl mx-auto space-y-8">
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col md:flex-row md:items-center justify-between gap-4"
        >
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/5 border border-white/10 text-xs font-medium text-white/70 mb-4">
              <History className="w-4 h-4" />
              Job Dashboard
            </div>
            <h1 className="text-3xl font-bold tracking-tight">Your Generation History</h1>
            <p className="text-white/60 mt-2">
              View your past runs, status, and open results.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Link href="/" className="secondary-button flex items-center gap-2">
              <Play className="w-4 h-4" />
              New Run
              <ArrowRight className="w-4 h-4" />
            </Link>
            <Link href="/profile" className="secondary-button flex items-center gap-2">
              <User className="w-4 h-4" />
              Profile
            </Link>
            <Link href="/analytics" className="secondary-button flex items-center gap-2">
              <BarChart3 className="w-4 h-4" />
              Analytics
            </Link>
            <Link href="/settings" className="secondary-button flex items-center gap-2">
              <Settings className="w-4 h-4" />
              Settings
            </Link>
            <Link href="/about" className="secondary-button flex items-center gap-2">
              <Info className="w-4 h-4" />
              About
            </Link>
            <button onClick={logout} className="secondary-button flex items-center gap-2">
              <LogOut className="w-4 h-4" />
              Logout
            </button>
          </div>
        </motion.div>

        {!token && (
          <div className="glass-card rounded-2xl border border-white/10 p-6 text-white/70">
            <div className="flex items-center gap-2 text-white mb-2">
              <ShieldAlert className="w-5 h-5 text-primary" />
              Login Required
            </div>
            <p className="mb-4">You need to login to see your job history.</p>
            <Link className="primary-button inline-flex items-center gap-2" href="/login">
              <ArrowRight className="w-4 h-4" />
              Go to Login
            </Link>
          </div>
        )}

        {token && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="grid grid-cols-2 md:grid-cols-4 gap-3"
          >
            <div className="glass-card rounded-2xl border border-white/10 p-4">
              <div className="text-xs text-white/50">Running</div>
              <div className="text-2xl font-bold mt-1">{grouped.running}</div>
            </div>
            <div className="glass-card rounded-2xl border border-white/10 p-4">
              <div className="text-xs text-white/50">Completed</div>
              <div className="text-2xl font-bold mt-1">{grouped.completed}</div>
            </div>
            <div className="glass-card rounded-2xl border border-white/10 p-4">
              <div className="text-xs text-white/50">Failed</div>
              <div className="text-2xl font-bold mt-1">{grouped.failed}</div>
            </div>
            <div className="glass-card rounded-2xl border border-white/10 p-4">
              <div className="text-xs text-white/50">Other</div>
              <div className="text-2xl font-bold mt-1">{grouped.other}</div>
            </div>
          </motion.div>
        )}

        {token && (
          <div className="glass-card rounded-2xl border border-white/10 overflow-hidden">
            <div className="p-4 border-b border-white/10 flex items-center justify-between">
              <div className="font-semibold text-white/80">Recent Jobs</div>
              <button
                onClick={() => token && loadJobs(token)}
                className="secondary-button flex items-center gap-2"
                disabled={loading}
              >
                <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
                Refresh
              </button>
            </div>

            <div className="p-2">
              <AnimatePresence>
                {error && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className="mx-2 my-2 rounded-xl bg-red-500/10 border border-red-500/20 text-red-200 px-4 py-3 text-sm"
                  >
                    {error}
                  </motion.div>
                )}
              </AnimatePresence>

              {jobs.length === 0 && !loading && !error && (
                <div className="p-6 text-center text-white/40">No jobs yet.</div>
              )}

              <div className="space-y-2">
                {jobs.map((j) => (
                  <Link
                    key={j.job_id}
                    href={`/jobs/${j.job_id}`}
                    className="block rounded-xl border border-white/10 bg-black/20 hover:bg-white/5 transition-colors p-4"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 text-sm text-white/70">
                          {statusIcon(j.status)}
                          <span className="font-mono text-white/60">{j.job_id}</span>
                          <span className="text-white/30">•</span>
                          <span className="text-white/60">{j.llm_provider}</span>
                        </div>
                        <div className="mt-2 text-white font-semibold line-clamp-2">
                          {j.task}
                        </div>
                        <div className="mt-2 text-xs text-white/40">
                          {j.created_at ? new Date(j.created_at).toLocaleString() : ""}
                        </div>
                      </div>
                      <ArrowRight className="w-4 h-4 text-white/40 shrink-0" />
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
