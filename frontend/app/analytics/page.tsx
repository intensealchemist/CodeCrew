"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { ArrowLeft, BarChart3, ShieldAlert, TrendingUp } from "lucide-react";

type JobItem = {
  job_id: string;
  task: string;
  llm_provider: string;
  status: string;
  created_at: string | null;
};

export default function AnalyticsPage() {
  const [token, setToken] = useState<string | null>(null);
  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setToken(localStorage.getItem("codecrew_token"));
  }, []);

  useEffect(() => {
    if (!token) return;
    fetch("/api/me/jobs", {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    })
      .then((r) => r.json().then((d) => ({ ok: r.ok, d })))
      .then(({ ok, d }) => {
        if (!ok) throw new Error(d?.detail || d?.error || "Failed to load jobs");
        setJobs((d?.jobs ?? []) as JobItem[]);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Analytics error"));
  }, [token]);

  const stats = useMemo(() => {
    const byProvider = new Map<string, number>();
    const byStatus = new Map<string, number>();
    for (const j of jobs) {
      byProvider.set(j.llm_provider, (byProvider.get(j.llm_provider) ?? 0) + 1);
      byStatus.set(j.status, (byStatus.get(j.status) ?? 0) + 1);
    }
    const providerTop = [...byProvider.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5);
    const statusList = [...byStatus.entries()].sort((a, b) => b[1] - a[1]);
    return { providerTop, statusList, total: jobs.length };
  }, [jobs]);

  return (
    <main className="min-h-screen p-6 md:p-12">
      <div className="w-full max-w-5xl mx-auto space-y-6">
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-2 text-sm text-white/50 hover:text-white transition-colors mb-4 group"
          >
            <ArrowLeft className="w-4 h-4 transition-transform group-hover:-translate-x-1" />
            Back to Dashboard
          </Link>

          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
            <BarChart3 className="w-7 h-7 text-primary" />
            Analytics
          </h1>
          <p className="text-white/60 mt-2">
            Basic job analytics generated from your job history (for internship documentation).
          </p>
        </motion.div>

        {!token && (
          <div className="glass-card rounded-2xl border border-white/10 p-6 text-white/70">
            <div className="flex items-center gap-2 text-white mb-2">
              <ShieldAlert className="w-5 h-5 text-primary" />
              Login Required
            </div>
            <p className="mb-4">Please login to view analytics.</p>
            <Link className="primary-button inline-flex items-center gap-2" href="/login">
              Go to Login
            </Link>
          </div>
        )}

        {error && (
          <div className="rounded-2xl bg-red-500/10 border border-red-500/20 text-red-200 px-4 py-3 text-sm">
            {error}
          </div>
        )}

        {token && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="glass-card rounded-2xl border border-white/10 p-5">
              <div className="text-xs text-white/50">Total Jobs</div>
              <div className="text-3xl font-bold mt-1">{stats.total}</div>
            </div>
            <div className="glass-card rounded-2xl border border-white/10 p-5 md:col-span-2">
              <div className="flex items-center gap-2 text-white/80 font-semibold">
                <TrendingUp className="w-5 h-5 text-primary" />
                Jobs by Status
              </div>
              <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-3">
                {stats.statusList.map(([k, v]) => (
                  <div key={k} className="rounded-xl border border-white/10 bg-black/20 px-4 py-3">
                    <div className="text-xs text-white/50">{k}</div>
                    <div className="text-xl font-bold mt-1">{v}</div>
                  </div>
                ))}
                {stats.statusList.length === 0 ? (
                  <div className="text-white/40 text-sm">No data</div>
                ) : null}
              </div>
            </div>

            <div className="glass-card rounded-2xl border border-white/10 p-5 md:col-span-3">
              <div className="text-white/80 font-semibold">Top LLM Providers</div>
              <div className="mt-3 space-y-2">
                {stats.providerTop.map(([k, v]) => (
                  <div key={k} className="rounded-xl border border-white/10 bg-black/20 px-4 py-3 flex items-center justify-between">
                    <div className="text-white/70 font-mono">{k}</div>
                    <div className="text-white font-semibold">{v}</div>
                  </div>
                ))}
                {stats.providerTop.length === 0 ? (
                  <div className="text-white/40 text-sm">No provider data</div>
                ) : null}
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
