"use client";

import { useState, useRef, KeyboardEvent } from "react";
import { X, Plus, Search } from "lucide-react";
import { cn, KNOWN_DRUGS } from "@/lib/utils";

interface DrugInputProps {
    drugs: string[];
    onChange: (drugs: string[]) => void;
}

export default function DrugInput({ drugs, onChange }: DrugInputProps) {
    const [input, setInput] = useState("");
    const [showSuggestions, setShowSuggestions] = useState(false);
    const inputRef = useRef<HTMLInputElement>(null);

    const suggestions = KNOWN_DRUGS.filter(
        (d) => d.toLowerCase().includes(input.toLowerCase()) && !drugs.includes(d)
    ).slice(0, 6);

    const addDrug = (drug: string) => {
        const normalized = drug.trim().toUpperCase();
        if (normalized && !drugs.includes(normalized)) {
            onChange([...drugs, normalized]);
        }
        setInput("");
        setShowSuggestions(false);
        inputRef.current?.focus();
    };

    const removeDrug = (drug: string) => {
        onChange(drugs.filter((d) => d !== drug));
    };

    const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
        if (e.key === "Enter" || e.key === ",") {
            e.preventDefault();
            if (input.trim()) addDrug(input);
        } else if (e.key === "Backspace" && !input && drugs.length > 0) {
            removeDrug(drugs[drugs.length - 1]);
        }
    };

    return (
        <div className="relative">
            <label className="block text-sm font-medium text-[var(--text-secondary)] mb-2">
                Drugs to Analyze
            </label>

            <div
                className={cn(
                    "flex flex-wrap items-center gap-2 rounded-xl border-2 px-3 py-2.5 min-h-[48px] transition-colors",
                    "border-[var(--border-default)] bg-[var(--bg-input)]",
                    "focus-within:border-[var(--accent-blue)]"
                )}
                onClick={() => inputRef.current?.focus()}
            >
                {drugs.map((drug) => (
                    <span
                        key={drug}
                        className={cn(
                            "inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold",
                            "bg-[var(--accent-blue)]/15 text-[var(--accent-blue)] border border-[var(--accent-blue)]/25"
                        )}
                    >
                        {drug}
                        <button
                            onClick={(e) => { e.stopPropagation(); removeDrug(drug); }}
                            className="hover:text-white transition-colors"
                            aria-label={`Remove ${drug}`}
                        >
                            <X size={12} />
                        </button>
                    </span>
                ))}

                <div className="flex items-center gap-1 flex-1 min-w-[120px]">
                    <Search size={14} className="text-[var(--text-muted)] shrink-0" />
                    <input
                        ref={inputRef}
                        type="text"
                        value={input}
                        onChange={(e) => { setInput(e.target.value); setShowSuggestions(true); }}
                        onKeyDown={handleKeyDown}
                        onFocus={() => setShowSuggestions(true)}
                        onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
                        placeholder={drugs.length === 0 ? "Type drug name (e.g. WARFARIN)..." : "Add more..."}
                        className="flex-1 bg-transparent border-none outline-none text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)]"
                        id="drug-input"
                    />
                </div>
            </div>

            <p className="mt-1.5 text-xs text-[var(--text-muted)]">
                Press Enter or comma to add. {drugs.length > 0 && `${drugs.length} drug${drugs.length > 1 ? "s" : ""} selected.`}
            </p>

            {/* Suggestions dropdown */}
            {showSuggestions && input.length > 0 && suggestions.length > 0 && (
                <div className="absolute z-50 w-full mt-1 py-1 rounded-xl border border-[var(--border-default)] bg-[var(--bg-card)] shadow-xl shadow-black/30">
                    {suggestions.map((drug) => (
                        <button
                            key={drug}
                            onMouseDown={() => addDrug(drug)}
                            className="w-full text-left px-3 py-2 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-card-hover)] flex items-center gap-2 transition-colors"
                        >
                            <Plus size={12} className="text-[var(--accent-blue)]" />
                            {drug}
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}
