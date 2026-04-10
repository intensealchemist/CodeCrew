"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { motion } from "framer-motion";
import { UserPlus, Eye, EyeOff } from "lucide-react";

export default function RegisterPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = (await res.json()) as any;
      if (!res.ok) {
        throw new Error(data?.detail || data?.error || "Registration failed");
      }
      router.push("/login");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center p-6">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-card w-full max-w-md rounded-3xl p-6 border border-white/10"
      >
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold tracking-tight">Register</h1>
          <UserPlus className="w-6 h-6 text-primary" />
        </div>

        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm text-white/70">Username</label>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full rounded-xl bg-black/30 border border-white/10 px-4 py-2 outline-none focus:border-primary/60"
              placeholder="Choose a username"
              required
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm text-white/70">Password</label>
            <div className="relative">
              <input
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                type={show ? "text" : "password"}
                className="w-full rounded-xl bg-black/30 border border-white/10 px-4 py-2 pr-12 outline-none focus:border-primary/60"
                placeholder="Choose a password"
                required
              />
              <button
                type="button"
                onClick={() => setShow((s) => !s)}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-lg hover:bg-white/10 text-white/60"
                title={show ? "Hide" : "Show"}
              >
                {show ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {error && (
            <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-2">
              {error}
            </div>
          )}

          <button
            disabled={loading}
            className="primary-button w-full flex items-center justify-center gap-2"
          >
            <UserPlus className="w-4 h-4" />
            {loading ? "Creating..." : "Create Account"}
          </button>
        </form>

        <div className="mt-6 flex items-center justify-between text-sm text-white/60">
          <Link className="hover:text-white" href="/login">
            Already have an account?
          </Link>
          <Link className="hover:text-white" href="/">
            Back to Home
          </Link>
        </div>
      </motion.div>
    </main>
  );
}
