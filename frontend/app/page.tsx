"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { FormEvent } from "react";
import { Bot, Sparkles, Server, ArrowRight, Loader2, Play } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

const PROVIDERS = ["free_ha", "groq", "cerebras", "openai", "anthropic", "ollama"] as const;
type Provider = (typeof PROVIDERS)[number];

export default function HomePage() {
  const router = useRouter();
  const [task, setTask] = useState<string>("");
  const [provider, setProvider] = useState<Provider>("free_ha");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const examples = [
    { title: "Todo app with auth", icon: <Sparkles className="w-4 h-4" /> },
    { title: "REST API with Flask", icon: <Server className="w-4 h-4" /> },
    { title: "CLI calculator in Python", icon: <Bot className="w-4 h-4" /> },
  ];

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    const trimmed = task.trim();
    if (!trimmed) {
      setError("Please describe what you want to build.");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task: trimmed, llm_provider: provider }),
      });

      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Request failed (${res.status})`);
      }

      const data = (await res.json()) as { job_id: string };
      router.push(`/jobs/${data.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start job.");
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen flex flex-col items-center justify-center p-6 relative overflow-hidden">
      {/* Decorative background elements */}
      <div className="absolute top-0 -left-1/4 w-[500px] h-[500px] bg-primary/20 rounded-full blur-[120px] -z-10 animate-blob mix-blend-screen" />
      <div className="absolute top-1/4 -right-1/4 w-[500px] h-[500px] bg-blue-500/20 rounded-full blur-[120px] -z-10 animate-blob animation-delay-2000 mix-blend-screen" />
      <div className="absolute -bottom-8 left-1/4 w-[500px] h-[500px] bg-purple-500/20 rounded-full blur-[120px] -z-10 animate-blob animation-delay-4000 mix-blend-screen" />

      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, ease: "easeOut" }}
        className="w-full max-w-2xl"
      >
        <div className="text-center mb-10">
          <motion.div 
            initial={{ scale: 0.9 }}
            animate={{ scale: 1 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="inline-flex items-center justify-center p-3 rounded-2xl bg-white/5 border border-white/10 mb-6"
          >
            <Bot className="w-8 h-8 text-primary" />
          </motion.div>
          <motion.h1 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
            className="text-5xl md:text-6xl font-bold tracking-tight mb-4 text-transparent bg-clip-text bg-gradient-to-r from-white via-white/90 to-white/50"
          >
            CodeCrew
          </motion.h1>
          <motion.p 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.4 }}
            className="text-lg text-white/70 max-w-lg mx-auto leading-relaxed"
          >
            Your AI engineering team. Describe what you want to build, and watch the multi-agent crew write the code.
          </motion.p>
        </div>

        <motion.form 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.5 }}
          onSubmit={onSubmit} 
          className="glass-card p-6 md:p-8 rounded-3xl relative"
        >
          <div className="flex flex-col gap-6">
            <div className="relative group">
              <label className="text-sm font-medium text-white/70 mb-2 block ml-1">
                Describe your project
              </label>
              <textarea
                value={task}
                placeholder="e.g. Build a complete Next.js dashboard with a Stripe integration..."
                onChange={(e) => setTask(e.target.value)}
                rows={4}
                className="glass-input w-full resize-none text-lg leading-relaxed pt-4"
              />
            </div>

            <div className="flex flex-col sm:flex-row gap-4 items-center justify-between">
              <div className="w-full sm:w-auto flex items-center gap-3">
                <label className="text-sm font-medium text-white/70">Provider:</label>
                <div className="relative">
                  <select 
                    value={provider} 
                    onChange={(e) => setProvider(e.target.value as Provider)}
                    className="appearance-none bg-white/5 border border-white/10 rounded-xl px-4 py-2 pr-10 text-white focus:outline-none focus:ring-2 focus:ring-primary/50 cursor-pointer"
                  >
                    {PROVIDERS.map((p) => (
                      <option key={p} value={p} className="bg-background text-foreground">
                        {p}
                      </option>
                    ))}
                  </select>
                  <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none">
                    <svg className="w-4 h-4 text-white/50" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path></svg>
                  </div>
                </div>
              </div>

              <motion.button 
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                type="submit" 
                disabled={loading}
                className="primary-button w-full sm:w-auto flex items-center justify-center gap-2 group relative overflow-hidden"
              >
                {/* Glow effect on hover */}
                <div className="absolute inset-0 bg-white/20 translate-y-full group-hover:translate-y-0 transition-transform duration-300 ease-out" />
                <span className="relative z-10 flex items-center gap-2">
                  {loading ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      Deploying Crew...
                    </>
                  ) : (
                    <>
                      <Play className="w-5 h-5 fill-current" />
                      Generate
                    </>
                  )}
                </span>
              </motion.button>
            </div>
            
            <AnimatePresence>
              {error && (
                <motion.div 
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="bg-destructive/10 border border-destructive/20 text-destructive-foreground px-4 py-3 rounded-xl text-sm"
                >
                  {error}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.form>

        <div className="mt-8 flex flex-wrap gap-3 justify-center">
          {examples.map((ex, i) => (
              <motion.button
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.6 + i * 0.1 }}
                whileHover={{ scale: 1.05, backgroundColor: "rgba(255,255,255,0.1)" }}
                whileTap={{ scale: 0.95 }}
                key={ex.title}
                type="button"
                onClick={() => setTask(ex.title)}
                disabled={loading}
                className="glass-button flex items-center gap-2 text-sm"
              >
                {ex.icon}
                {ex.title}
                <ArrowRight className="w-3 h-3 opacity-50 ml-1 transition-transform group-hover:translate-x-1" />
              </motion.button>
          ))}
        </div>
      </motion.div>
    </main>
  );
}
