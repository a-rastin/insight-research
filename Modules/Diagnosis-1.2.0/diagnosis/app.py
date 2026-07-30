"""Standalone FastAPI app for the Diagnosis module."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import router
from .config import settings
from .readiness import check_readiness

app = FastAPI(
    title="Insight - Diagnosis",
    version="0.1.0",
    description="DSM-5-TR schizophrenia criteria checklist. Clinician-controlled diagnostic support.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_methods=["GET", "PUT", "POST", "OPTIONS"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/health")
def health():
    return {"ok": True, "module": "diagnosis"}


@app.get("/ready")
def ready():
    state = check_readiness()
    if not state["ok"]:
        return JSONResponse(status_code=503, content=state)
    return state
