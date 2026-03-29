"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { 
  FileCode2, 
  ChevronRight, 
  Download, 
  Copy, 
  CheckCircle2, 
  ArrowLeft,
  FileText
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

export default function FilesPage({ params }: { params: { job_id: string } }) {
  const jobId = params.job_id;

  const [files, setFiles] = useState<string[]>([]);
  const [activeFile, setActiveFile] = useState<string | null>(null);
  const [content, setContent] = useState<string>("");
  const [loadingContent, setLoadingContent] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetch(`/api/jobs/${jobId}/files`)
      .then((r) => r.json())
      .then((data) => {
        const fileList = data.files || [];
        setFiles(fileList);
        if (fileList.length > 0) {
          setActiveFile(fileList[0]);
        }
      })
      .catch((err) => console.error("Failed to load file list:", err));
  }, [jobId]);

  useEffect(() => {
    if (!activeFile) return;

    setLoadingContent(true);
    fetch(`/api/jobs/${jobId}/files/${encodeURIComponent(activeFile)}`)
      .then((r) => r.json())
      .then((data) => {
        setContent(data.content || "");
      })
      .catch((err) => {
        console.error("Failed to load file content:", err);
        setContent("Error loading file content.");
      })
      .finally(() => {
        setLoadingContent(false);
      });
  }, [jobId, activeFile]);

  const copyToClipboard = () => {
    navigator.clipboard.writeText(content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const handleDownloadZip = () => {
    window.location.href = `/api/jobs/${jobId}/download`;
  };

  return (
    <main className="min-h-screen p-6 md:p-12">
      <div className="w-full max-w-7xl mx-auto space-y-6">
        
        {/* Header */}
        <motion.div 
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col md:flex-row md:items-center justify-between gap-4"
        >
          <div>
            <Link 
              href={`/jobs/${jobId}`}
              className="inline-flex items-center gap-2 text-sm text-white/50 hover:text-white transition-colors mb-4 group"
            >
              <ArrowLeft className="w-4 h-4 transition-transform group-hover:-translate-x-1" />
              Back to Pipeline Run
            </Link>
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
              <FileCode2 className="w-8 h-8 text-primary" />
              Generated Files
            </h1>
          </div>
          <button 
            onClick={handleDownloadZip}
            className="primary-button flex items-center gap-2"
          >
            <Download className="w-4 h-4" />
            Download ZIP
          </button>
        </motion.div>

        {/* Explorer Layout */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="glass-card rounded-2xl border border-white/10 overflow-hidden flex flex-col md:flex-row h-[70vh] min-h-[500px]"
        >
          {/* Sidebar */}
          <div className="md:w-64 bg-black/40 border-r border-white/5 flex flex-col hidden md:flex">
            <div className="p-4 border-b border-white/5 font-semibold text-sm text-white/70">
              Explorer
            </div>
            <div className="flex-1 overflow-y-auto p-2 space-y-1 scrollbar-hide">
              {files.map((f) => {
                const isActive = activeFile === f;
                return (
                  <button
                    key={f}
                    onClick={() => setActiveFile(f)}
                    className={`w-full flex items-center gap-2 px-3 py-2 text-sm rounded-lg transition-colors text-left ${isActive ? 'bg-primary/20 text-primary font-medium' : 'text-white/60 hover:text-white hover:bg-white/5'}`}
                  >
                    <FileText className={`w-4 h-4 ${isActive ? 'text-primary' : 'text-white/40'}`} />
                    <span className="truncate">{f}</span>
                  </button>
                );
              })}
              {files.length === 0 && (
                <div className="p-4 text-center text-sm text-white/30">
                  No files generated yet.
                </div>
              )}
            </div>
          </div>

          {/* Main Editor View */}
          <div className="flex-1 flex flex-col bg-[#0A0A0B]">
            {/* Editor Header */}
            <div className="h-12 border-b border-white/5 px-4 flex items-center justify-between bg-black/20">
              <div className="flex items-center gap-2 text-sm text-white/60">
                <ChevronRight className="w-4 h-4 opacity-50" />
                <span className="font-mono">{activeFile || 'No file selected'}</span>
              </div>
              {activeFile && (
                <button
                  onClick={copyToClipboard}
                  className="p-2 rounded-lg hover:bg-white/10 text-white/60 hover:text-white transition-colors flex items-center gap-2 text-sm"
                  title="Copy Code"
                >
                  {copied ? (
                    <><CheckCircle2 className="w-4 h-4 text-green-500" /> Copied!</>
                  ) : (
                    <><Copy className="w-4 h-4" /> Copy</>
                  )}
                </button>
              )}
            </div>
            
            {/* Editor Content */}
            <div className="flex-1 overflow-auto p-6 scrollbar-hide relative">
              <AnimatePresence mode="wait">
                {loadingContent ? (
                  <motion.div 
                    key="loading"
                    initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                    className="absolute inset-0 flex items-center justify-center text-white/30"
                  >
                    <Download className="w-6 h-6 animate-bounce" />
                  </motion.div>
                ) : (
                  <motion.pre 
                    key={content}
                    initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                    className="font-mono text-[13px] leading-relaxed text-white/80 whitespace-pre-wrap"
                  >
                    {content || (activeFile ? 'File is empty.' : 'Select a file to view its contents.')}
                  </motion.pre>
                )}
              </AnimatePresence>
            </div>
          </div>
        </motion.div>
      </div>
    </main>
  );
}
