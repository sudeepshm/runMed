"use client";

import { useState } from "react";
import {
  Shield, Loader2, AlertCircle, Dna,
  Activity, Beaker, ArrowRight,
} from "lucide-react";
import { cn, API_BASE, type AnalysisResponse, type DrugResult } from "@/lib/utils";
import DrugInput from "@/components/drug-input";
import VCFDropzone from "@/components/vcf-dropzone";
import ResultsDashboard from "@/components/results-dashboard";
import Parallax from "@/components/parallax";

type AppState = "input" | "loading" | "results" | "error";

export default function Home() {
  const [state, setState] = useState<AppState>("input");
  const [drugs, setDrugs] = useState<string[]>([]);
  const [vcfFile, setVcfFile] = useState<File | null>(null);
  const [patientId, setPatientId] = useState("PATIENT_001");
  const [results, setResults] = useState<DrugResult[]>([]);
  const [error, setError] = useState<string>("");
  const [loadingStep, setLoadingStep] = useState("");

  const canSubmit = drugs.length > 0 && vcfFile !== null;

  const handleSubmit = async () => {
    if (!canSubmit || !vcfFile) return;

    setState("loading");
    setError("");

    const steps = [
      "Uploading VCF file...",
      "Parsing genomic variants...",
      "Matching star alleles...",
      "Querying CPIC guidelines...",
      "Retrieving clinical context...",
      "Generating AI explanations...",
    ];

    // Animate loading steps
    let stepIdx = 0;
    setLoadingStep(steps[0]);
    const stepInterval = setInterval(() => {
      stepIdx++;
      if (stepIdx < steps.length) {
        setLoadingStep(steps[stepIdx]);
      }
    }, 800);

    try {
      const formData = new FormData();
      formData.append("vcf_file", vcfFile);
      formData.append("patient_id", patientId);
      formData.append("drugs", drugs.join(","));

      const response = await fetch(`${API_BASE}/analyze`, {
        method: "POST",
        body: formData,
      });

      clearInterval(stepInterval);

      if (!response.ok) {
        const errData = await response.json().catch(() => ({ detail: "Server error" }));
        throw new Error(errData.detail || `HTTP ${response.status}`);
      }

      const data: AnalysisResponse = await response.json();

      if (data.status !== "success") {
        throw new Error(data.errors?.join(", ") || "Analysis failed");
      }

      setResults(data.results);
      setState("results");
    } catch (err: unknown) {
      clearInterval(stepInterval);
      setError(err instanceof Error ? err.message : "An unexpected error occurred");
      setState("error");
    }
  };

  const handleReset = () => {
    setState("input");
    setDrugs([]);
    setVcfFile(null);
    setResults([]);
    setError("");
  };

  return (
    <div className="min-h-screen">
      {/* ── Header ──────────────────────────────── */}
      <header className="border-b border-[var(--border-default)] bg-[var(--bg-secondary)]/80 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[var(--accent-blue)] to-[var(--accent-purple)] flex items-center justify-center">
              <Shield size={18} className="text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-[var(--text-primary)] tracking-tight">PharmaGuard</h1>
              <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-widest">Pharmacogenomics Analysis</p>
            </div>
          </div>

          {state === "results" && (
            <button
              onClick={handleReset}
              className="px-4 py-2 rounded-xl text-sm font-medium border border-[var(--border-default)] hover:bg-[var(--bg-card-hover)] transition-colors"
            >
              New Analysis
            </button>
          )}
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8 relative">
        <Parallax />
        {/* ── Input State ─────────────────────────── */}
        {state === "input" && (
          <div className="max-w-2xl mx-auto space-y-8 animate-fade-in-up">
            {/* Hero */}
            <div className="text-center space-y-3 pt-8">
              <div className="flex items-center justify-center gap-2">
                <Dna size={28} className="text-[var(--accent-cyan)]" />
                <Activity size={24} className="text-[var(--accent-purple)]" />
                <Beaker size={26} className="text-[var(--accent-blue)]" />
              </div>
              <h2 className="text-3xl font-bold bg-gradient-to-r from-[var(--accent-blue)] via-[var(--accent-cyan)] to-[var(--accent-purple)] bg-clip-text text-transparent">
                Pharmacogenomic Risk Analysis
              </h2>
              <p className="text-[var(--text-secondary)] text-sm max-w-md mx-auto">
                Upload a VCF file and select drugs to receive AI-powered
                pharmacogenomic risk assessments with clinical explanations.
              </p>
            </div>

            {/* Patient ID */}
            <div>
              <label className="block text-sm font-medium text-[var(--text-secondary)] mb-2">
                Patient ID
              </label>
              <input
                type="text"
                value={patientId}
                onChange={(e) => setPatientId(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl border-2 border-[var(--border-default)] bg-[var(--bg-input)] text-sm text-[var(--text-primary)] focus:border-[var(--accent-blue)] focus:outline-none transition-colors"
                placeholder="e.g. PATIENT_001"
                id="patient-id"
              />
            </div>

            {/* Drug Input */}
            <DrugInput drugs={drugs} onChange={setDrugs} />

            {/* VCF Upload */}
            <div>
              <label className="block text-sm font-medium text-[var(--text-secondary)] mb-2">
                VCF File
              </label>
              <VCFDropzone
                onFileSelect={setVcfFile}
                selectedFile={vcfFile}
                onClear={() => setVcfFile(null)}
              />
            </div>

            {/* Submit */}
            <button
              onClick={handleSubmit}
              disabled={!canSubmit}
              className={cn(
                "w-full py-3.5 rounded-xl text-sm font-semibold flex items-center justify-center gap-2 transition-all duration-200",
                canSubmit
                  ? "bg-gradient-to-r from-[var(--accent-blue)] to-[var(--accent-purple)] text-white hover:opacity-90 shadow-lg shadow-blue-500/20"
                  : "bg-[var(--bg-card)] text-[var(--text-muted)] cursor-not-allowed border border-[var(--border-default)]"
              )}
              id="submit-analysis"
            >
              <Shield size={16} />
              Analyze Pharmacogenomics
              <ArrowRight size={16} />
            </button>
          </div>
        )}

        {/* ── Loading State ───────────────────────── */}
        {state === "loading" && (
          <div className="flex flex-col items-center justify-center py-32 space-y-6 animate-fade-in-up">
            <div className="relative">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-[var(--accent-blue)] to-[var(--accent-purple)] flex items-center justify-center">
                <Loader2 size={28} className="text-white animate-spin" />
              </div>
              <div className="absolute -bottom-1 -right-1 w-5 h-5 rounded-full bg-[var(--accent-cyan)] animate-pulse" />
            </div>
            <div className="text-center">
              <h3 className="text-lg font-bold text-[var(--text-primary)]">Processing Analysis</h3>
              <p className="text-sm text-[var(--accent-cyan)] mt-2 font-medium">{loadingStep}</p>
            </div>
            {/* Animated steps */}
            <div className="w-80 space-y-2">
              {[
                "Parsing genomic variants",
                "Matching star alleles",
                "Querying CPIC guidelines",
                "Generating AI explanations",
              ].map((step, i) => (
                <div key={step} className="flex items-center gap-3">
                  <div className={cn(
                    "w-2 h-2 rounded-full transition-colors duration-500",
                    loadingStep.toLowerCase().includes(step.split(" ")[0].toLowerCase())
                      ? "bg-[var(--accent-cyan)]"
                      : i < 2 ? "bg-green-400" : "bg-[var(--border-default)]"
                  )} />
                  <span className="text-xs text-[var(--text-muted)]">{step}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Error State ─────────────────────────── */}
        {state === "error" && (
          <div className="max-w-lg mx-auto py-20 text-center space-y-6 animate-fade-in-up">
            <div className="w-16 h-16 mx-auto rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center">
              <AlertCircle size={28} className="text-red-400" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-[var(--text-primary)]">Analysis Failed</h3>
              <p className="text-sm text-red-400 mt-2">{error}</p>
            </div>
            <button
              onClick={handleReset}
              className="px-6 py-2.5 rounded-xl text-sm font-medium bg-[var(--bg-card)] border border-[var(--border-default)] hover:bg-[var(--bg-card-hover)] transition-colors"
            >
              Try Again
            </button>
          </div>
        )}

        {/* ── Results State ───────────────────────── */}
        {state === "results" && (
          <div className="animate-fade-in-up">
            <ResultsDashboard results={results} patientId={patientId} />
          </div>
        )}
      </main>

      {/* ── Footer ──────────────────────────────── */}
      <footer className="border-t border-[var(--border-default)] mt-16">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between text-xs text-[var(--text-muted)]">
          <span>PharmaGuard © 2026 — Pharmacogenomics Clinical Decision Support</span>
          <span>CPIC Guidelines · PharmVar · dbSNP</span>
        </div>
      </footer>
    </div>
  );
}
