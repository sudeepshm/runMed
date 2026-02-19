"""
PharmaGuard — FastAPI application entry point.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import health, analysis

# ── Create app ────────────────────────────────────────────────────────

app = FastAPI(
    title="PharmaGuard API",
    description=(
        "Pharmacogenomics risk analysis engine. "
        "Upload a VCF file and a list of drugs to receive "
        "explainable AI-powered clinical recommendations."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS (allow Next.js frontend) ────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register routers ─────────────────────────────────────────────────

app.include_router(health.router)
app.include_router(analysis.router)


# ── Root redirect to docs ────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def root():
    """Redirect root to Swagger docs."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")
