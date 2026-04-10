import Link from "next/link";
import { ArrowLeft, Bot, Server, Layers, ShieldCheck } from "lucide-react";

export default function AboutPage() {
  return (
    <main className="min-h-screen p-6 md:p-12">
      <div className="w-full max-w-4xl mx-auto space-y-6">
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-sm text-white/50 hover:text-white transition-colors mb-2 group"
        >
          <ArrowLeft className="w-4 h-4 transition-transform group-hover:-translate-x-1" />
          Back to Home
        </Link>

        <div className="glass-card rounded-3xl border border-white/10 p-8 space-y-6">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">About CodeCrew</h1>
            <p className="text-white/60 mt-2">
              CodeCrew is a multi-agent code generation system with a CLI, FastAPI backend, and Next.js frontend.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="rounded-2xl border border-white/10 bg-black/20 p-5">
              <div className="flex items-center gap-2 text-white/80 font-semibold">
                <Layers className="w-5 h-5 text-primary" />
                Pipeline Stages
              </div>
              <p className="text-sm text-white/55 mt-2">
                Researcher, SpecValidator, Architect, FilePlanner, Coder, QAAgent, ReadmeAgent.
              </p>
            </div>

            <div className="rounded-2xl border border-white/10 bg-black/20 p-5">
              <div className="flex items-center gap-2 text-white/80 font-semibold">
                <Server className="w-5 h-5 text-primary" />
                Backend
              </div>
              <p className="text-sm text-white/55 mt-2">
                Job-based orchestration with streaming logs (SSE) and artifact download.
              </p>
            </div>

            <div className="rounded-2xl border border-white/10 bg-black/20 p-5">
              <div className="flex items-center gap-2 text-white/80 font-semibold">
                <Bot className="w-5 h-5 text-primary" />
                Frontend
              </div>
              <p className="text-sm text-white/55 mt-2">
                Submit prompts, monitor live progress, browse generated files, and download ZIP.
              </p>
            </div>

            <div className="rounded-2xl border border-white/10 bg-black/20 p-5">
              <div className="flex items-center gap-2 text-white/80 font-semibold">
                <ShieldCheck className="w-5 h-5 text-primary" />
                Safety
              </div>
              <p className="text-sm text-white/55 mt-2">
                Output writes are constrained to job output directories; command execution is gated by safety rules.
              </p>
            </div>
          </div>

          <div className="text-xs text-white/35">
            This page is intended to provide extra UI screens for internship documentation.
          </div>
        </div>
      </div>
    </main>
  );
}
