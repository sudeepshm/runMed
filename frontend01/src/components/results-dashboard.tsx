"use client";

import { useState, useEffect, useRef } from "react";
import {
    CheckCircle2, XCircle, AlertTriangle, HelpCircle,
    ChevronDown, ChevronUp, Copy, Download, Code2,
    Dna, Pill, Shield, ShieldAlert, ShieldX, ShieldCheck,
    Activity, Beaker,
} from "lucide-react";
import { cn, type DrugResult, type RiskLabel } from "@/lib/utils";

/* ── Risk Visual Config ───────────────────────── */
const RISK_CONFIG: Record<RiskLabel, {
    color: string; bg: string; border: string;
    icon: typeof CheckCircle2; label: string;
}> = {
    Safe: { color: "text-green-400", bg: "bg-green-500/10", border: "border-green-500/25", icon: ShieldCheck, label: "Safe" },
    Adjust: { color: "text-amber-400", bg: "bg-amber-500/10", border: "border-amber-500/25", icon: ShieldAlert, label: "Adjust Dosage" },
    Toxic: { color: "text-red-400", bg: "bg-red-500/10", border: "border-red-500/25", icon: ShieldX, label: "Toxic Risk" },
    Ineffective: { color: "text-red-400", bg: "bg-red-500/10", border: "border-red-500/25", icon: XCircle, label: "Ineffective" },
    Unknown: { color: "text-slate-400", bg: "bg-slate-500/10", border: "border-slate-500/25", icon: HelpCircle, label: "Unknown" },
};

const SEVERITY_COLORS: Record<string, string> = {
    critical: "text-red-400",
    high: "text-orange-400",
    moderate: "text-amber-400",
    low: "text-green-400",
};

/* ── Typewriter Hook ─────────────────────────── */
function useTypewriter(text: string, speed: number = 12) {
    const [displayed, setDisplayed] = useState("");
    const [done, setDone] = useState(false);

    useEffect(() => {
        setDisplayed("");
        setDone(false);
        let i = 0;
        const interval = setInterval(() => {
            i++;
            setDisplayed(text.slice(0, i));
            if (i >= text.length) {
                clearInterval(interval);
                setDone(true);
            }
        }, speed);
        return () => clearInterval(interval);
    }, [text, speed]);

    return { displayed, done };
}

/* ── Single Result Card ──────────────────────── */
function ResultCard({ result, index }: { result: DrugResult; index: number }) {
    const [expanded, setExpanded] = useState(false);
    const [showJSON, setShowJSON] = useState(false);
    const [copied, setCopied] = useState(false);

    const risk = result.risk_assessment;
    const config = RISK_CONFIG[risk.risk_label as RiskLabel] || RISK_CONFIG.Unknown;
    const Icon = config.icon;

    const summary = result.llm_generated_explanation?.summary || "";
    const mechanism = result.llm_generated_explanation?.mechanism || "";
    const { displayed: typedSummary, done: summaryDone } = useTypewriter(summary, 8);
    const { displayed: typedMechanism } = useTypewriter(
        expanded && summaryDone ? mechanism : "", 6
    );

    const copyJSON = () => {
        navigator.clipboard.writeText(JSON.stringify(result, null, 2));
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const downloadJSON = () => {
        const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${result.drug}_analysis.json`;
        a.click();
        URL.revokeObjectURL(url);
    };

    return (
        <div
            className={cn(
                "rounded-2xl border overflow-hidden transition-all duration-300",
                "animate-fade-in-up",
                config.border, config.bg
            )}
            style={{ animationDelay: `${index * 100}ms` }}
        >
            {/* Header */}
            <div className="px-5 py-4 flex items-center justify-between">
                <div className="flex items-center gap-4">
                    {/* Risk Icon */}
                    <div className={cn("w-11 h-11 rounded-xl flex items-center justify-center", config.bg, "border", config.border)}>
                        <Icon size={22} className={config.color} />
                    </div>

                    {/* Drug + Gene */}
                    <div>
                        <div className="flex items-center gap-2">
                            <Pill size={14} className="text-[var(--accent-purple)]" />
                            <h3 className="text-base font-bold text-[var(--text-primary)]">{result.drug}</h3>
                            <span className={cn("px-2 py-0.5 rounded-md text-xs font-bold", config.bg, config.color, "border", config.border)}>
                                {config.label}
                            </span>
                        </div>
                        <div className="flex items-center gap-3 mt-1">
                            <span className="flex items-center gap-1 text-xs text-[var(--text-secondary)]">
                                <Dna size={12} className="text-[var(--accent-cyan)]" />
                                {result.pharmacogenomic_profile.primary_gene}
                            </span>
                            <span className="px-2 py-0.5 rounded-md text-xs font-mono font-bold bg-[var(--accent-cyan)]/10 text-[var(--accent-cyan)] border border-[var(--accent-cyan)]/20">
                                {result.pharmacogenomic_profile.diplotype}
                            </span>
                            <span className="text-xs text-[var(--text-muted)]">
                                {result.pharmacogenomic_profile.phenotype}
                            </span>
                        </div>
                    </div>
                </div>

                {/* Confidence + Severity */}
                <div className="flex items-center gap-3">
                    <div className="text-right">
                        <div className="flex items-center gap-1">
                            <Activity size={12} className={SEVERITY_COLORS[risk.severity] || "text-slate-400"} />
                            <span className={cn("text-xs font-semibold uppercase", SEVERITY_COLORS[risk.severity] || "text-slate-400")}>
                                {risk.severity}
                            </span>
                        </div>
                        <div className="text-xs text-[var(--text-muted)] mt-0.5">
                            {(risk.confidence_score * 100).toFixed(0)}% confidence
                        </div>
                    </div>
                    <button
                        onClick={() => setExpanded(!expanded)}
                        className="p-2 rounded-lg hover:bg-white/5 transition-colors"
                        aria-label={expanded ? "Collapse" : "Expand"}
                    >
                        {expanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                    </button>
                </div>
            </div>

            {/* AI Summary (always visible, typewriter effect) */}
            <div className="px-5 pb-3">
                <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
                    {typedSummary}
                    {!summaryDone && <span className="inline-block w-0.5 h-4 bg-[var(--accent-blue)] animate-pulse ml-0.5 align-middle" />}
                </p>
            </div>

            {/* Expanded Content */}
            {expanded && (
                <div className="px-5 pb-5 space-y-4 border-t border-white/5 pt-4">
                    {/* Mechanism */}
                    {mechanism && (
                        <div>
                            <h4 className="text-xs font-semibold uppercase text-[var(--accent-purple)] mb-2 flex items-center gap-1.5">
                                <Beaker size={12} /> Biological Mechanism
                            </h4>
                            <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
                                {typedMechanism}
                                {typedMechanism.length < mechanism.length && (
                                    <span className="inline-block w-0.5 h-4 bg-[var(--accent-purple)] animate-pulse ml-0.5 align-middle" />
                                )}
                            </p>
                        </div>
                    )}

                    {/* Detected Variants */}
                    {result.detected_variants.length > 0 && (
                        <div>
                            <h4 className="text-xs font-semibold uppercase text-[var(--text-muted)] mb-2">
                                Detected Variants ({result.detected_variants.length})
                            </h4>
                            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
                                {result.detected_variants.map((v, i) => (
                                    <div key={i} className="px-3 py-2 rounded-lg bg-white/3 border border-white/5 text-xs">
                                        <span className="font-mono font-bold text-[var(--accent-cyan)]">{v.rsid}</span>
                                        <span className="text-[var(--text-muted)] ml-2">{v.genotype || "N/A"}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Actions */}
                    <div className="flex items-center gap-2 pt-2">
                        <button
                            onClick={copyJSON}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-white/5 hover:bg-white/10 border border-white/10 transition-colors"
                        >
                            <Copy size={12} />
                            {copied ? "Copied!" : "Copy JSON"}
                        </button>
                        <button
                            onClick={downloadJSON}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-white/5 hover:bg-white/10 border border-white/10 transition-colors"
                        >
                            <Download size={12} />
                            Download
                        </button>
                        <button
                            onClick={() => setShowJSON(!showJSON)}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-white/5 hover:bg-white/10 border border-white/10 transition-colors"
                        >
                            <Code2 size={12} />
                            {showJSON ? "Hide" : "View"} Raw JSON
                        </button>
                    </div>

                    {/* Raw JSON */}
                    {showJSON && (
                        <pre className="p-4 rounded-xl bg-black/30 border border-white/5 text-xs font-mono text-[var(--accent-cyan)] overflow-x-auto max-h-80">
                            {JSON.stringify(result, null, 2)}
                        </pre>
                    )}
                </div>
            )}
        </div>
    );
}

/* ── Dashboard ───────────────────────────────── */
interface ResultsDashboardProps {
    results: DrugResult[];
    patientId: string;
}

export default function ResultsDashboard({ results, patientId }: ResultsDashboardProps) {
    const safeCount = results.filter((r) => r.risk_assessment.risk_label === "Safe").length;
    const adjustCount = results.filter((r) => r.risk_assessment.risk_label === "Adjust").length;
    const dangerCount = results.filter((r) =>
        r.risk_assessment.risk_label === "Toxic" || r.risk_assessment.risk_label === "Ineffective"
    ).length;

    const downloadAll = () => {
        const blob = new Blob([JSON.stringify({ status: "success", results }, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${patientId}_pharmaguard_report.json`;
        a.click();
        URL.revokeObjectURL(url);
    };

    return (
        <div className="space-y-6">
            {/* Summary Bar */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <h2 className="text-xl font-bold text-[var(--text-primary)]">
                        Analysis Results
                    </h2>
                    <div className="flex items-center gap-2">
                        {safeCount > 0 && (
                            <span className="px-2.5 py-1 rounded-lg text-xs font-bold bg-green-500/10 text-green-400 border border-green-500/20">
                                {safeCount} Safe
                            </span>
                        )}
                        {adjustCount > 0 && (
                            <span className="px-2.5 py-1 rounded-lg text-xs font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                                {adjustCount} Adjust
                            </span>
                        )}
                        {dangerCount > 0 && (
                            <span className="px-2.5 py-1 rounded-lg text-xs font-bold bg-red-500/10 text-red-400 border border-red-500/20">
                                {dangerCount} Risk
                            </span>
                        )}
                    </div>
                </div>
                <button
                    onClick={downloadAll}
                    className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-medium bg-[var(--accent-blue)]/10 text-[var(--accent-blue)] border border-[var(--accent-blue)]/20 hover:bg-[var(--accent-blue)]/20 transition-colors"
                >
                    <Download size={14} />
                    Download Full Report
                </button>
            </div>

            {/* Result Cards */}
            <div className="space-y-4">
                {results.map((result, i) => (
                    <ResultCard key={`${result.drug}-${i}`} result={result} index={i} />
                ))}
            </div>
        </div>
    );
}
