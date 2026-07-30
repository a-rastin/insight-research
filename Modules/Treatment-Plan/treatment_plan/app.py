from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Any
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from .config import Settings
from .edit_ledger import (
    InMemoryPlanEditStore,
    InvalidEdit,
    PlanEditLedger,
    PlanFinalized,
    PlanNotFound,
    PreconditionFailed,
    PreconditionRequired,
    ReasonRequired,
)
from .finalization import (
    AuthoritativeContextUnavailable,
    FinalizationCommand,
    FinalizationError,
    IdempotencyConflict,
    PlanFinalizer,
    SafetyRecalculationFailed,
)
from .logging import configure_logging
from .observability import Observability
from .repository import InMemoryRepository, Repository
from .sqlite_edit_store import SQLitePlanEditStore
from .sqlite_repository import SQLiteRepository
from .security import AccessDenied, AuthenticationUnavailable, Capability, HttpAuthenticationAdapter, Security, Session


def create_app(
    settings: Settings | None = None,
    repository: Repository | None = None,
    security: Security | None = None,
    plan_ledger: PlanEditLedger | None = None,
    plan_finalizer: PlanFinalizer | None = None,
    observability: Observability | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    configure_logging(settings.log_level)
    observability = observability or Observability()
    repository = repository or SQLiteRepository(settings.database_path)
    if plan_ledger is None:
        edit_store = InMemoryPlanEditStore() if isinstance(repository, InMemoryRepository) else SQLitePlanEditStore(settings.database_path)
        plan_ledger = PlanEditLedger(edit_store)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        repository.migrate()
        app.state.repository = repository
        yield

    app = FastAPI(title="INSIGHT Treatment Plan", version="0.1.0", lifespan=lifespan)
    app.state.observability = observability

    @app.middleware("http")
    async def correlate(request: Request, call_next):
        with observability.bind(request.headers.get("x-correlation-id")) as correlation_id:
            started = time.monotonic()
            try:
                response = await call_next(request)
            except Exception:
                observability.metric("tp_http_latency_ms", (time.monotonic() - started) * 1000,
                                     labels={"module": "app", "outcome": "failure"})
                raise
            outcome = "failure" if response.status_code >= 500 else "success"
            observability.metric("tp_http_latency_ms", (time.monotonic() - started) * 1000,
                                 labels={"module": "app", "outcome": outcome})
            response.headers["X-Correlation-ID"] = correlation_id
            return response

    if security is None and settings.authentication_session_url:
        security = Security(HttpAuthenticationAdapter(settings.authentication_session_url))

    def authorized_session(request: Request, capability: Capability, csrf_token: str | None = None) -> Session:
        if settings.auth_stub_enabled:
            if capability in {Capability.AUDIT_READ, Capability.SUPPORT_READ}:
                raise HTTPException(401, "development session is not authorized for protected operations")
            return Session(                request.headers.get("x-development-actor", "standalone-developer"),
                frozenset({"psychiatrist"}),
                datetime.max.replace(tzinfo=timezone.utc),
                request.headers.get("x-csrf-token", "development-csrf"),
                session_id=request.headers.get("x-development-session", "development-session"),
            )
        if security is None:
            raise HTTPException(503, "authentication integration is not configured")
        try:
            session = security.authorize(request.headers.get("cookie", ""), capability, csrf_token)
            if capability == Capability.PLAN_MUTATE and not session.session_id.strip():
                raise HTTPException(503, "Authentication did not provide a session identifier")
            return session
        except AccessDenied as exc:
            raise HTTPException(401, str(exc)) from exc
        except AuthenticationUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc

    def actor(request: Request) -> str:
        return authorized_session(request, Capability.SESSION).user_id

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/ready")
    def ready():
        if not repository.ping():
            raise HTTPException(503, "repository unavailable")
        mode = "development-stub" if settings.auth_stub_enabled else ("rest" if security else "disabled")
        return {"status": "ready", "authMode": mode}

    @app.get("/api/treatment-plan/v1/session")
    def session(current_actor: str = Depends(actor)):
        return {"actor": current_actor, "mode": "development-stub" if settings.auth_stub_enabled else "rest"}

    @app.get("/api/treatment-plan/v1/plans/{plan_id}")
    def read_plan(plan_id: str, request: Request):
        authorized_session(request, Capability.PLAN_READ)
        try:
            view = plan_ledger.get(plan_id)
        except PlanNotFound as exc:
            raise HTTPException(404, str(exc)) from exc
        return JSONResponse(view.to_dict(), headers={"ETag": view.etag, "X-Schema-Version": "1.1.0"})

    @app.patch("/api/treatment-plan/v1/plans/{plan_id}/draft")
    def edit_draft(
        plan_id: str,
        body: dict[str, Any],
        request: Request,
        if_match: str | None = Header(default=None, alias="If-Match"),
        csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    ):
        current_session = authorized_session(request, Capability.PLAN_MUTATE, csrf_token)
        allowed_fields = {"operation", "path", "after", "reason"}
        unknown = sorted(set(body) - allowed_fields)
        if unknown:
            raise HTTPException(422, "unsupported edit fields: " + ", ".join(unknown))
        if "operation" not in body or "path" not in body:
            raise HTTPException(422, "operation and path are required")
        if body["operation"] in {"add", "replace"} and "after" not in body:
            raise HTTPException(422, "after is required for add and replace")
        try:
            view = plan_ledger.edit(
                plan_id,
                expected_etag=if_match,
                actor_id=current_session.user_id,
                session_id=current_session.session_id,
                path=body["path"],
                operation=body["operation"],
                after=body.get("after"),
                reason=body.get("reason"),
            )
        except PreconditionRequired as exc:
            raise HTTPException(428, str(exc)) from exc
        except PreconditionFailed as exc:
            raise HTTPException(412, str(exc)) from exc
        except PlanNotFound as exc:
            raise HTTPException(404, str(exc)) from exc
        except (ReasonRequired, InvalidEdit) as exc:
            raise HTTPException(422, str(exc)) from exc
        return JSONResponse(view.to_dict(), headers={"ETag": view.etag, "X-Schema-Version": "1.1.0"})

    @app.post("/api/treatment-plan/v1/plans/{plan_id}/finalize", status_code=201)
    async def finalize_plan(
        plan_id: str,
        body: dict[str, Any],
        request: Request,
        if_match: str | None = Header(default=None, alias="If-Match"),
        csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        request_id: str | None = Header(default=None, alias="X-Request-ID"),
        correlation_id: str | None = Header(default=None, alias="X-Correlation-ID"),
    ):
        current_session = authorized_session(request, Capability.PLAN_MUTATE, csrf_token)
        if plan_finalizer is None:
            raise HTTPException(503, "authoritative finalization is not configured")
        unknown = sorted(set(body) - {"attestation"})
        if unknown:
            raise HTTPException(422, "unsupported finalization fields: " + ", ".join(unknown))
        if "attestation" not in body:
            raise HTTPException(422, "attestation is required")
        command = FinalizationCommand(
            actor_id=current_session.user_id,
            session_id=current_session.session_id,
            attestation=body["attestation"],
            request_id=request_id or "",
            correlation_id=observability.correlation_id,
            idempotency_key=idempotency_key or "",
        )
        try:
            final_plan = await plan_finalizer.finalize(
                plan_id,
                expected_etag=if_match,
                command=command,
                reauthorize=lambda: authorized_session(
                    request, Capability.PLAN_MUTATE, csrf_token
                ),
            )
        except PreconditionRequired as exc:
            raise HTTPException(428, str(exc)) from exc
        except PreconditionFailed as exc:
            raise HTTPException(412, str(exc)) from exc
        except PlanNotFound as exc:
            raise HTTPException(404, str(exc)) from exc
        except AuthoritativeContextUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        except (IdempotencyConflict, PlanFinalized, SafetyRecalculationFailed) as exc:
            raise HTTPException(409, str(exc)) from exc
        except FinalizationError as exc:
            raise HTTPException(422, str(exc)) from exc
        return JSONResponse(
            final_plan,
            status_code=201,
            headers={"Idempotency-Key": command.idempotency_key, "X-Schema-Version": "1.0.0"},
        )

    @app.get("/api/treatment-plan/v1/plans/{plan_id}/provenance")
    def read_plan_provenance(plan_id: str, request: Request):
        authorized_session(request, Capability.PLAN_READ)
        try:
            record = plan_ledger.get_finalization(plan_id)
        except PlanNotFound as exc:
            raise HTTPException(404, str(exc)) from exc
        if record is None:
            return JSONResponse([], headers={"X-Schema-Version": "1.0.0"})
        final_plan = record.get("finalPlan", {})
        provenance = final_plan.get("provenance") if isinstance(final_plan, dict) else None
        if not isinstance(provenance, dict):
            raise HTTPException(500, "stored finalization provenance is invalid")
        return JSONResponse([provenance], headers={"X-Schema-Version": "1.0.0"})

    @app.get("/api/treatment-plan/v1/plans/{plan_id}/audit")
    def read_plan_audit(plan_id: str, request: Request):
        current_session = authorized_session(request, Capability.AUDIT_READ)
        events = [event.to_dict() for event in observability.audit_events(entity_id=plan_id)]
        observability.audit("audit.retrieve", "success", actor_id=current_session.user_id, entity_id=plan_id)
        return JSONResponse(events, headers={"X-Schema-Version": "1.0.0"})

    @app.get("/api/treatment-plan/v1/observability/dashboard")
    def observability_dashboard(request: Request):
        authorized_session(request, Capability.SUPPORT_READ)
        return observability.dashboard()

    @app.get("/metrics", response_class=PlainTextResponse)
    def metrics(request: Request):
        authorized_session(request, Capability.SUPPORT_READ)
        return observability.prometheus()

    frontend = Path(__file__).parents[1] / "frontend" / "dist"
    if frontend.exists():
        app.mount("/assets", StaticFiles(directory=frontend / "assets"), name="assets")

        @app.get("/modules/treatment-plan", include_in_schema=False)
        def module_shell():
            return FileResponse(frontend / "index.html")
    return app


app = create_app()




