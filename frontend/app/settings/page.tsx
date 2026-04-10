"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Save, Settings as SettingsIcon, ArrowLeft, Trash2 } from "lucide-react";

type Provider = "free_ha" | "groq" | "cerebras" | "openai" | "ollama" | "llama.cpp" | "bitnet";

const PROVIDERS: Provider[] = ["free_ha", "groq", "cerebras", "openai", "ollama", "llama.cpp", "bitnet"];

export default function SettingsPage() {
  const [defaultProvider, setDefaultProvider] = useState<Provider>("ollama");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("codecrew_default_provider");
    if (stored && PROVIDERS.includes(stored as Provider)) {
      setDefaultProvider(stored as Provider);
    }
  }, []);

  function save() {
    localStorage.setItem("codecrew_default_provider", defaultProvider);
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  }

  function clearAuth() {
    localStorage.removeItem("codecrew_token");
  }

  return (
    <main className="min-h-screen p-6 md:p-12">
      <div className="w-full max-w-3xl mx-auto space-y-6">
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-2 text-sm text-white/50 hover:text-white transition-colors mb-4 group"
          >
            <ArrowLeft className="w-4 h-4 transition-transform group-hover:-translate-x-1" />
            Back to Dashboard
          </Link>

          <div className="flex items-center justify-between">
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
              <SettingsIcon className="w-7 h-7 text-primary" />
              Settings
            </h1>
          </div>
        </motion.div>

        <div className="glass-card rounded-2xl border border-white/10 p-6 space-y-4">
          <div>
            <div className="text-sm font-semibold text-white/80">Default LLM Provider</div>
            <div className="text-sm text-white/50 mt-1">
              Used as the initial selection on the home page.
            </div>
          </div>

          <select
            value={defaultProvider}
            onChange={(e) => setDefaultProvider(e.target.value as Provider)}
            className="w-full rounded-xl bg-black/30 border border-white/10 px-4 py-2 outline-none focus:border-primary/60"
          >
            {PROVIDERS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>

          <div className="flex items-center gap-2">
            <button onClick={save} className="primary-button flex items-center gap-2">
              <Save className="w-4 h-4" />
              {saved ? "Saved" : "Save"}
            </button>
            <button onClick={clearAuth} className="secondary-button flex items-center gap-2">
              <Trash2 className="w-4 h-4" />
              Clear Login Token
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}
