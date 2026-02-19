"""
PharmaGuard — LLM Explanation Generator (Module 6).

Generates scientifically accurate, patient-friendly explanations of
pharmacogenomic findings using Google Gemini API.

Two modes:
  1. GEMINI (when API key configured): Calls gemini-2.0-flash with
     structured prompt + RAG context for rich, contextual explanations.
  2. TEMPLATE (fallback): Generates deterministic template-based
     explanations when no API key is available.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Data classes ──────────────────────────────────────────────────────

@dataclass
class ExplanationInput:
    """Input data for generating an explanation."""
    gene: str
    diplotype: str
    phenotype: str
    phenotype_label: str
    drug: str
    risk_label: str
    severity: str
    recommendation: str
    rag_contexts: List[str]      # Retrieved context chunks
    detected_variants: List[dict]  # [{rsid, genotype, ...}]


@dataclass
class ExplanationOutput:
    """Generated explanation output."""
    summary: str
    mechanism: str
    mode: str = "template"  # "gemini" or "template"


# ── Prompt template ──────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a clinical pharmacogenomics expert AI assistant for the PharmaGuard system.
Your role is to generate clear, scientifically accurate explanations of pharmacogenomic drug-gene interactions for healthcare professionals.

REQUIREMENTS:
1. Be scientifically precise — cite specific enzymes, metabolic pathways, and metabolite names.
2. Explain the biological MECHANISM — how the genetic variant affects protein function, drug metabolism, and clinical outcome.
3. Be concise but thorough — 2-3 sentences for summary, 3-5 sentences for mechanism.
4. Use clinical language appropriate for healthcare professionals.
5. Do NOT hallucinate — only state facts supported by CPIC guidelines and the provided context.
6. Always mention the specific diplotype and phenotype.

Respond in valid JSON format:
{
  "summary": "Brief patient-specific clinical summary",
  "mechanism": "Detailed biological mechanism explanation"
}"""


def _build_user_prompt(inp: ExplanationInput) -> str:
    """Build the user prompt with clinical data and RAG context."""
    context_text = "\n\n".join(inp.rag_contexts) if inp.rag_contexts else "No additional context available."

    variants_text = ", ".join(
        f"{v.get('rsid', '?')} ({v.get('genotype', '?')})"
        for v in inp.detected_variants[:5]
    ) or "None detected"

    return f"""Generate a pharmacogenomic explanation for the following finding:

CLINICAL DATA:
- Gene: {inp.gene}
- Diplotype: {inp.diplotype}
- Phenotype: {inp.phenotype} ({inp.phenotype_label})
- Drug: {inp.drug}
- Risk Label: {inp.risk_label}
- Severity: {inp.severity}
- CPIC Recommendation: {inp.recommendation}
- Detected Variants: {variants_text}

RELEVANT CLINICAL CONTEXT:
{context_text}

Generate a JSON response with "summary" and "mechanism" fields."""


# ── Gemini generator ─────────────────────────────────────────────────

class GeminiGenerator:
    """Generates explanations using Google Gemini API."""

    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.model_name = model_name
        self._model = None
        self._available = False

    def initialize(self) -> bool:
        """Initialize the Gemini model."""
        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            self._model = genai.GenerativeModel(
                model_name=self.model_name,
                generation_config={
                    "temperature": 0.3,
                    "top_p": 0.8,
                    "max_output_tokens": 500,
                    "response_mime_type": "application/json",
                },
                system_instruction=SYSTEM_PROMPT,
            )
            self._available = True
            logger.info("Gemini model initialized: %s", self.model_name)
            return True

        except Exception as exc:
            logger.warning("Gemini initialization failed: %s", exc)
            self._available = False
            return False

    def generate(self, inp: ExplanationInput) -> ExplanationOutput:
        """Generate explanation using Gemini API."""
        if not self._available or not self._model:
            raise RuntimeError("Gemini not initialized")

        prompt = _build_user_prompt(inp)

        try:
            response = self._model.generate_content(prompt)
            text = response.text.strip()

            # Parse JSON response
            data = json.loads(text)

            return ExplanationOutput(
                summary=data.get("summary", ""),
                mechanism=data.get("mechanism", ""),
                mode="gemini",
            )

        except json.JSONDecodeError as exc:
            logger.warning("Gemini returned non-JSON: %s", exc)
            # Try to extract from raw text
            return ExplanationOutput(
                summary=response.text[:300] if response else "Error parsing response.",
                mechanism="",
                mode="gemini",
            )

        except Exception as exc:
            logger.error("Gemini generation failed: %s", exc)
            raise


# ── Template generator (fallback) ────────────────────────────────────

class TemplateGenerator:
    """Deterministic template-based explanation generator (no API needed)."""

    # Phenotype descriptions
    PHENOTYPE_DESC = {
        "UM": "ultra-rapid metabolizer, meaning they process this drug much faster than normal",
        "RM": "rapid metabolizer, meaning they process this drug faster than normal",
        "EM": "normal (extensive) metabolizer with typical drug processing capability",
        "NM": "normal metabolizer with typical drug processing capability",
        "IM": "intermediate metabolizer, meaning they process this drug more slowly than normal",
        "PM": "poor metabolizer, meaning they have significantly reduced ability to process this drug",
        "NF": "normal transporter function",
        "DF": "decreased transporter function, leading to altered drug disposition",
        "PF": "poor transporter function, leading to significantly altered drug disposition",
    }

    # Risk explanations
    RISK_DESC = {
        "Safe": "Standard dosing is appropriate for this patient based on their pharmacogenomic profile.",
        "Adjust": "Dose adjustment is recommended based on the patient's altered drug metabolism.",
        "Toxic": "This drug poses a significant toxicity risk for this patient due to their genetic profile. Alternative therapy should be strongly considered.",
        "Ineffective": "This drug is likely to be ineffective for this patient due to their genetic profile. An alternative drug should be selected.",
        "Unknown": "No specific pharmacogenomic guideline exists for this drug-gene combination.",
    }

    # Mechanism templates per gene
    GENE_MECHANISMS = {
        "CYP2D6": "CYP2D6 is a cytochrome P450 enzyme responsible for metabolizing approximately 25% of clinically used drugs. The {diplotype} diplotype results in {phenotype_label} status. {risk_specific} The enzyme's altered activity directly affects the rate of drug biotransformation, impacting both efficacy and safety profiles.",
        "CYP2C19": "CYP2C19 is a key drug-metabolizing enzyme in the cytochrome P450 superfamily. The {diplotype} diplotype confers {phenotype_label} status, altering the enzyme's catalytic efficiency. {risk_specific} This directly impacts the pharmacokinetics of CYP2C19 substrates, affecting therapeutic outcomes.",
        "CYP2C9": "CYP2C9 metabolizes drugs with narrow therapeutic indices, including warfarin and phenytoin. The {diplotype} diplotype indicates {phenotype_label} status, with reduced S-warfarin 7-hydroxylation capacity. {risk_specific} Altered CYP2C9 activity significantly affects drug clearance and steady-state concentrations.",
        "CYP3A5": "CYP3A5 contributes to the metabolism of tacrolimus and other immunosuppressants. The {diplotype} diplotype determines CYP3A5 expression status ({phenotype_label}). {risk_specific} CYP3A5 expression directly influences tacrolimus trough concentrations and dosing requirements.",
        "DPYD": "Dihydropyrimidine dehydrogenase (DPD), encoded by DPYD, is the rate-limiting enzyme in fluoropyrimidine catabolism, inactivating approximately 80% of administered 5-FU. The {diplotype} diplotype results in {phenotype_label} DPD activity. {risk_specific} Reduced DPD activity leads to prolonged exposure to cytotoxic fluoropyrimidine metabolites.",
        "TPMT": "Thiopurine S-methyltransferase (TPMT) catalyzes the methylation and inactivation of thiopurine drugs. The {diplotype} diplotype results in {phenotype_label} TPMT activity. {risk_specific} Reduced TPMT activity shifts metabolism toward cytotoxic thioguanine nucleotide accumulation, increasing myelosuppression risk.",
        "SLCO1B1": "SLCO1B1 encodes the OATP1B1 hepatic uptake transporter critical for statin disposition. The {diplotype} diplotype confers {phenotype_label}. {risk_specific} Altered OATP1B1 function affects hepatic statin uptake, modifying systemic exposure and myopathy risk.",
    }

    def generate(self, inp: ExplanationInput) -> ExplanationOutput:
        """Generate a template-based explanation."""
        pheno_desc = self.PHENOTYPE_DESC.get(
            inp.phenotype, f"{inp.phenotype} metabolizer"
        )
        risk_desc = self.RISK_DESC.get(inp.risk_label, self.RISK_DESC["Unknown"])

        # Summary
        summary = (
            f"Patient carries the {inp.gene} {inp.diplotype} diplotype, classified as "
            f"{inp.phenotype} ({inp.phenotype_label}). "
            f"This patient is a {pheno_desc}. "
            f"For {inp.drug}: {risk_desc}"
        )

        # Mechanism
        risk_specific = self._get_risk_specific(inp)
        mech_template = self.GENE_MECHANISMS.get(
            inp.gene,
            "The {diplotype} diplotype results in {phenotype_label} status. {risk_specific}"
        )
        mechanism = mech_template.format(
            diplotype=inp.diplotype,
            phenotype_label=inp.phenotype_label,
            risk_specific=risk_specific,
        )

        return ExplanationOutput(
            summary=summary,
            mechanism=mechanism,
            mode="template",
        )

    def _get_risk_specific(self, inp: ExplanationInput) -> str:
        """Get risk-label-specific mechanism text."""
        if inp.risk_label == "Toxic":
            return f"The patient's genetic profile leads to drug accumulation or excessive active metabolite formation, creating a significant toxicity risk with {inp.drug}."
        elif inp.risk_label == "Ineffective":
            return f"The patient's genetic profile results in insufficient active metabolite formation or excessive drug clearance, rendering {inp.drug} therapeutically ineffective."
        elif inp.risk_label == "Adjust":
            return f"The patient's altered metabolism necessitates dose adjustment of {inp.drug} to achieve optimal therapeutic levels while minimizing adverse effects."
        else:
            return f"The patient's normal metabolic capacity allows standard {inp.drug} dosing with expected therapeutic outcomes."


# ── Unified LLM Generator ────────────────────────────────────────────

class LLMGenerator:
    """
    Unified LLM generator that auto-selects Gemini or template mode.
    """

    def __init__(self):
        self.gemini: Optional[GeminiGenerator] = None
        self.template = TemplateGenerator()
        self.active_mode = "template"

    def initialize(self, gemini_api_key: str = "") -> str:
        """Initialize. Returns the active mode."""
        if gemini_api_key:
            self.gemini = GeminiGenerator(gemini_api_key)
            if self.gemini.initialize():
                self.active_mode = "gemini"
                logger.info("LLM Generator: Gemini mode active")
            else:
                self.active_mode = "template"
                logger.info("LLM Generator: Template mode (Gemini init failed)")
        else:
            self.active_mode = "template"
            logger.info("LLM Generator: Template mode (no API key)")

        return self.active_mode

    def generate(self, inp: ExplanationInput) -> ExplanationOutput:
        """Generate an explanation using the best available backend."""
        # Try Gemini first
        if self.active_mode == "gemini" and self.gemini:
            try:
                return self.gemini.generate(inp)
            except Exception as exc:
                logger.warning("Gemini failed, falling back to template: %s", exc)

        # Fallback to template
        return self.template.generate(inp)


# ── Module-level singleton ────────────────────────────────────────────

_generator: Optional[LLMGenerator] = None


def get_llm_generator() -> LLMGenerator:
    """Get or create the LLM generator singleton."""
    global _generator
    if _generator is None:
        _generator = LLMGenerator()

        from app.config import get_settings
        settings = get_settings()
        _generator.initialize(gemini_api_key=settings.GEMINI_API_KEY)

    return _generator


def generate_explanation(inp: ExplanationInput) -> ExplanationOutput:
    """Convenience function: generate explanation using the global generator."""
    gen = get_llm_generator()
    return gen.generate(inp)
