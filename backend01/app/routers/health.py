"""
PharmaGuard — Health check router.
"""

from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "ok",
        "service": "PharmaGuard API",
        "version": "0.1.0",
    }
