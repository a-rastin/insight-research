"""Standalone FastAPI app for the Diagnosis module."""
from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import router
from .config import settings
from .readiness import check_readiness
from .v2 import PREFIX as V2_PREFIX, headers as v2_headers, problem as v2_problem

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


@app.middleware("http")
async def add_v2_trace_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith(V2_PREFIX):
        for name, value in v2_headers(request).items():
            response.headers.setdefault(name, value)
    return response


@app.exception_handler(HTTPException)
async def diagnosis_http_exception(request: Request, error: HTTPException):
    if not request.url.path.startswith(V2_PREFIX):
        return await http_exception_handler(request, error)
    code = {
        401: "COMMON_AUTHENTICATION_REQUIRED",
        403: "COMMON_FORBIDDEN",
        404: "DIAGNOSIS_RESOURCE_NOT_FOUND",
        409: "DIAGNOSIS_RESOURCE_CONFLICT",
        422: "DIAGNOSIS_REQUEST_INVALID",
        503: "COMMON_DEPENDENCY_UNAVAILABLE",
    }.get(error.status_code, "COMMON_REQUEST_FAILED")
    detail = error.detail if isinstance(error.detail, str) else "The request could not be completed."
    return v2_problem(request, error.status_code, code, detail)


@app.exception_handler(RequestValidationError)
async def diagnosis_validation_exception(request: Request, error: RequestValidationError):
    if not request.url.path.startswith(V2_PREFIX):
        return await request_validation_exception_handler(request, error)
    return v2_problem(request, 422, "COMMON_VALIDATION_FAILED", "The request did not match the diagnosis v2 contract.")


@app.get("/health")
def health():
    return {"ok": True, "module": "diagnosis"}


@app.get("/ready")
def ready():
    state = check_readiness()
    if not state["ok"]:
        return JSONResponse(status_code=503, content=state)
    return state
