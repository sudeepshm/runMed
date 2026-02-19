"use client";

import { useState, useCallback } from "react";
import { useDropzone, type FileRejection } from "react-dropzone";
import { Upload, FileCheck, AlertCircle, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface VCFDropzoneProps {
    onFileSelect: (file: File) => void;
    selectedFile: File | null;
    onClear: () => void;
}

export default function VCFDropzone({ onFileSelect, selectedFile, onClear }: VCFDropzoneProps) {
    const [error, setError] = useState<string | null>(null);

    const onDrop = useCallback((acceptedFiles: File[], rejectedFiles: FileRejection[]) => {
        setError(null);

        if (rejectedFiles.length > 0) {
            setError("Invalid file. Please upload a .vcf file under 5MB.");
            return;
        }

        const file = acceptedFiles[0];
        if (!file) return;

        // Validate extension
        if (!file.name.toLowerCase().endsWith(".vcf")) {
            setError("File must have a .vcf extension.");
            return;
        }

        // Validate size
        if (file.size > 5 * 1024 * 1024) {
            setError("File exceeds 5MB limit.");
            return;
        }

        // Read header to validate VCF format
        const reader = new FileReader();
        reader.onload = (e) => {
            const text = e.target?.result as string;
            if (!text.startsWith("##fileformat=VCF")) {
                setError("Invalid VCF format. File must start with ##fileformat=VCFv4.2");
                return;
            }
            onFileSelect(file);
        };
        reader.readAsText(file.slice(0, 500));
    }, [onFileSelect]);

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        accept: { "text/plain": [".vcf"] },
        maxSize: 5 * 1024 * 1024,
        maxFiles: 1,
        multiple: false,
    });

    if (selectedFile) {
        return (
            <div className={cn(
                "relative rounded-xl border-2 border-solid p-5",
                "border-green-500/40 bg-green-500/5"
            )}>
                <button
                    onClick={onClear}
                    className="absolute top-3 right-3 p-1 rounded-lg hover:bg-white/10 transition-colors"
                    aria-label="Remove file"
                >
                    <X size={16} className="text-[var(--text-secondary)]" />
                </button>
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-green-500/15 flex items-center justify-center">
                        <FileCheck size={20} className="text-green-400" />
                    </div>
                    <div>
                        <p className="text-sm font-medium text-[var(--text-primary)]">{selectedFile.name}</p>
                        <p className="text-xs text-[var(--text-secondary)]">
                            {(selectedFile.size / 1024).toFixed(1)} KB — Ready for analysis
                        </p>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div>
            <div
                {...getRootProps()}
                className={cn(
                    "rounded-xl border-2 border-dashed p-8 text-center cursor-pointer transition-all duration-200",
                    isDragActive
                        ? "border-[var(--accent-blue)] bg-[var(--accent-blue)]/5 scale-[1.01]"
                        : "border-[var(--border-default)] bg-[var(--bg-input)] hover:border-[var(--accent-blue)]/50 hover:bg-[var(--bg-card-hover)]"
                )}
            >
                <input {...getInputProps()} id="vcf-upload" />
                <div className="flex flex-col items-center gap-3">
                    <div className={cn(
                        "w-12 h-12 rounded-xl flex items-center justify-center transition-colors",
                        isDragActive ? "bg-[var(--accent-blue)]/15" : "bg-[var(--bg-card)]"
                    )}>
                        <Upload size={22} className={isDragActive ? "text-[var(--accent-blue)]" : "text-[var(--text-muted)]"} />
                    </div>
                    <div>
                        <p className="text-sm font-medium text-[var(--text-primary)]">
                            {isDragActive ? "Drop your VCF file here" : "Drag & drop your VCF file"}
                        </p>
                        <p className="text-xs text-[var(--text-muted)] mt-1">
                            or <span className="text-[var(--accent-blue)] underline">browse files</span> — .vcf format, max 5MB
                        </p>
                    </div>
                </div>
            </div>

            {error && (
                <div className="mt-3 flex items-center gap-2 text-sm text-red-400 bg-red-500/10 rounded-lg px-3 py-2">
                    <AlertCircle size={14} />
                    <span>{error}</span>
                </div>
            )}
        </div>
    );
}
