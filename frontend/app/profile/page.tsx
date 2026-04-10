"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ArrowLeft, User, Calendar, BarChart3, ShieldAlert } from "lucide-react";

type MeResponse = {
  id: number;
  username: string;
  created_at: string | null;
  job_summary: {
    running: number;
    completed: number;
    failed: number;
    pending: number;
  };
};

export default function ProfilePage() {
  const [token, setToken] = useState<string | null>(null);
  const [me, setMe] = useState<MeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setToken(localStorage.getItem("codecrew_token"));
  }, []);

  useEffect(() => {
    if (!token) return;
    fetch("/api/me", {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    })
      .then((r) => r.json().then((d) => ({ ok: r.ok, d })))
      .then(({ ok, d }) => {
        if (!ok) throw new Error(d?.detail || d?.error || "Failed to load profile");
        setMe(d as MeResponse);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Profile error"));
  }, [token]);

  return (
    <main className="min-h-screen p-6 md:p-12">
      <div className="w-full max-w-4xl mx-auto space-y-6">
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-2 text-sm text-white/50 hover:text-white transition-colors mb-4 group"
          >
            <ArrowLeft className="w-4 h-4 transition-transform group-hover:-translate-x-1" />
            Back to Dashboard
          </Link>

          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
            <User className="w-7 h-7 text-primary" />
            Profile
          </h1>
        </motion.div>

        {!token && (
          <div className="glass-card rounded-2xl border border-white/10 p-6 text-white/70">
            <div className="flex items-center gap-2 text-white mb-2">
              <ShieldAlert className="w-5 h-5 text-primary" />
              Login Required
            </div>
            <p className="mb-4">Please login to view profile details.</p>
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

        {me && (
          <div className="glass-card rounded-3xl border border-white/10 p-6 space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="rounded-2xl border border-white/10 bg-black/20 p-5">
                <div className="text-xs text-white/50">Username</div>
                <div className="text-xl font-bold mt-1">{me.username}</div>
              </div>
              <div className="rounded-2xl border border-white/10 bg-black/20 p-5">
                <div className="flex items-center gap-2 text-xs text-white/50">
                  <Calendar className="w-4 h-4" />
                  Account Created
                </div>
                <div className="text-sm text-white/80 mt-2">
                  {me.created_at ? new Date(me.created_at).toLocaleString() : ""}
                </div>
              </div>
            </div>

            <div>
              <div className="flex items-center gap-2 text-white/80 font-semibold">
                <BarChart3 className="w-5 h-5 text-primary" />
                Job Summary
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3">
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                  <div className="text-xs text-white/50">Running</div>
                  <div className="text-2xl font-bold mt-1">{me.job_summary.running}</div>
                </div>
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                  <div className="text-xs text-white/50">Completed</div>
                  <div className="text-2xl font-bold mt-1">{me.job_summary.completed}</div>
                </div>
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                  <div className="text-xs text-white/50">Failed</div>
                  <div className="text-2xl font-bold mt-1">{me.job_summary.failed}</div>
                </div>
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                  <div className="text-xs text-white/50">Pending</div>
                  <div className="text-2xl font-bold mt-1">{me.job_summary.pending}</div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
