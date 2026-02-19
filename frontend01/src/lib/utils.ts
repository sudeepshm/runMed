import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const KNOWN_DRUGS = [
  "CODEINE", "TRAMADOL", "OXYCODONE", "TAMOXIFEN",
  "WARFARIN", "PHENYTOIN", "CELECOXIB",
  "CLOPIDOGREL", "VORICONAZOLE", "OMEPRAZOLE",
  "TACROLIMUS",
  "FLUOROURACIL", "CAPECITABINE",
  "AZATHIOPRINE", "MERCAPTOPURINE", "THIOGUANINE",
  "SIMVASTATIN", "ATORVASTATIN", "ROSUVASTATIN",
];

export type RiskLabel = "Safe" | "Adjust" | "Toxic" | "Ineffective" | "Unknown";

export interface DetectedVariant {
  rsid: string;
  genotype: string | null;
  allelic_depth: string | null;
  clinical_recommendation: string;
}

export interface RiskAssessment {
  risk_label: RiskLabel;
  confidence_score: number;
  severity: string;
}

export interface PharmacogenomicProfile {
  primary_gene: string;
  diplotype: string;
  phenotype: string;
}

export interface LLMExplanation {
  summary: string;
  mechanism: string | null;
}

export interface QualityMetrics {
  vcf_parsing_success: boolean;
  total_variants_extracted: number;
  pharmacogenes_found: number;
}

export interface DrugResult {
  "patient id": string;
  drug: string;
  timestamp: string;
  risk_assessment: RiskAssessment;
  pharmacogenomic_profile: PharmacogenomicProfile;
  detected_variants: DetectedVariant[];
  llm_generated_explanation: LLMExplanation;
  quality_metrics: QualityMetrics;
}

export interface AnalysisResponse {
  status: string;
  results: DrugResult[];
  errors: string[];
}
