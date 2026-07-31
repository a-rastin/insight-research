from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Any
from uuid import UUID, uuid4
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from .config import Settings
from .assistant import AssistantUnavailable, HttpAssistantProvider, InvalidAssistantRequest, ReadOnlyAssistant
from .clinical_context import OutboundRequestContext
from .ddi_check import DdiMedicationChecker, HttpDdiPort
from .edit_ledger import (
    InMemoryPlanEditStore,
    InvalidEdit,
    PlanEditLedger,
    PlanFinalized,
    PlanNotFound,
    PlanSuperseded,
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
from .input_mapping import (
    ApprovedFollowUpSnapshotProvider,
    ApprovedRecommendationInputMapper,
    ApprovedSuccessorPlanGenerator,
    AuthoritativeFinalizationContextProvider,
)
from .recommendation_run import (
    RecommendationRunError,
    RecommendationRunIdempotencyConflict,
    RecommendationRunNotFound,
    RecommendationRunRequest,
    RecommendationRunStore,
    RecommendationRunUnavailable,
    RecommendationRunWorkflow,
    TreatmentPlanRecommendationStages,
)
from .bn_evaluation import BnEvaluationOrchestrator, InMemoryBnEvaluationStore, RawBnEvaluation, BnModel
from .eligibility import GenerationEligibilityPolicy
from .sqlite_edit_store import SQLitePlanEditStore
from .sqlite_repository import SQLiteRepository
from .supersession import PlanSuperseder, SupersessionError
from .security import AccessDenied, AuthenticationUnavailable, Capability, HttpAuthenticationAdapter, Security, Session


MODULE_VERSION = "0.1.0"
INTERFACE_VERSION = "1.1.0"
PROFILE_VERSION = "1.0.0"
CONTRACT_ROOT = Path(__file__).parents[1] / "contracts"
OPENAPI_PATH = CONTRACT_ROOT / "openapi" / "treatment-plan.openapi.v1.1.0.json"
SCHEMA_PATHS = {
    ("audit-event", "1.0.0"): CONTRACT_ROOT / "schemas" / "1.0.0" / "audit-event.schema.json",
    ("runtime-api", "1.1.0"): CONTRACT_ROOT / "schemas" / "1.1.0" / "runtime-api.schema.json",
    ("treatment-plan", "1.0.0"): CONTRACT_ROOT / "schemas" / "1.0.0" / "treatment-plan.schema.json",
}

INTEGRATION_BLOCKERS = {
    "recommendation": {
        "code": "TP_RECOMMENDATION_MAPPING_UNAPPROVED",
        "detail": "No approved contract maps owner snapshots into BN evidence, deterministic safety candidates, safety facts, and source facts.",
    },
    "scope": {
        "code": "TP_SCOPE_UNAPPROVED",
        "detail": "No patient population is approved for Treatment Plan generation.",
    },
    "finalization": {
        "code": "TP_FINALIZATION_CONTEXT_CONTRACT_MISSING",
        "detail": "No approved provider contract defines reconstruction of current medications, dose-bound safety candidates, safety facts, and authoritative source versions for finalization.",
    },
    "supersession": {
        "code": "TP_SUCCESSOR_GENERATION_CONTRACT_MISSING",
        "detail": "No approved mapping defines fresh follow-up snapshots to a revalidated successor Primary Plan and section reasons.",
    },
    "ddi-configuration": {
        "code": "TP_DDI_CONFIGURATION_MISSING",
        "detail": "DDI v1 REST and service-auth configuration is required.",
    },
    "ddi-unavailable": {
        "code": "TP_DDI_UNAVAILABLE",
        "detail": "DDI v1 readiness or an active reviewed knowledge revision is unavailable.",
    },
}

SCOPE_MATRIX_PATH = Path(__file__).parents[1] / "governance" / "scope-matrix.v1.json"


class _ResearchBnEvaluator:
    """Uniform research posterior when BN Manager is not injected."""

    async def evaluate(self, model: BnModel, evidence, mapping_version: str) -> RawBnEvaluation:
        from uuid import uuid4
        from datetime import datetime, timezone

        if model is BnModel.PHARMACOTHERAPY:
            posterior = {
                "continue-current-antipsychotic": 1 / 3,
                "switch-antipsychotic": 1 / 3,
                "consider-clozapine": 1 / 3,
            }
        else:
            posterior = {"research-default": 1.0}
        return RawBnEvaluation(
            evaluation_id=str(uuid4()),
            model_id=model.value,
            model_version="1.0.0",
            model_hash="sha256:" + ("b" * 64),
            posterior=posterior,
            evaluated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )


class _UnavailableContextAssembler:
    async def assemble(self, patient_id, encounter_id, severity_assessment_id, request_context):
        raise RuntimeError("clinical context endpoints are not configured")


def _scope_approved() -> bool:
    try:
        import json
        matrix = json.loads(SCOPE_MATRIX_PATH.read_text(encoding="utf-8"))
    except OSError:
        return False
    return matrix.get("status") == "approved" and bool(matrix.get("clinicalScope", {}).get("supportedPopulation"))


def _discovery_headers(correlation_id: str) -> dict[str, str]:
    request_id = str(uuid4())
    return {
        "X-Schema-Version": INTERFACE_VERSION,
        "X-Request-ID": request_id,
        "X-Correlation-ID": correlation_id,
    }


def create_app(
    settings: Settings | None = None,
    repository: Repository | None = None,
    security: Security | None = None,
    plan_ledger: PlanEditLedger | None = None,
    plan_finalizer: PlanFinalizer | None = None,
    observability: Observability | None = None,
    recommendation_workflow: RecommendationRunWorkflow | None = None,
    plan_superseder: PlanSuperseder | None = None,
    assistant: ReadOnlyAssistant | None = None,
    ddi_port: Any | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    configure_logging(settings.log_level)
    observability = observability or Observability()
    repository = repository or SQLiteRepository(settings.database_path)
    if plan_ledger is None:
        edit_store = InMemoryPlanEditStore() if isinstance(repository, InMemoryRepository) else SQLitePlanEditStore(settings.database_path)
        plan_ledger = PlanEditLedger(edit_store)
    if assistant is None and settings.assistant_provider_url:
        assistant = ReadOnlyAssistant(
            HttpAssistantProvider(settings.assistant_provider_url, settings.assistant_timeout_seconds)
        )
    ddi_checker = None
    if ddi_port is None and all((settings.ddi_base_url, settings.ddi_service_auth_key_id, settings.ddi_service_auth_secret)):
        ddi_port = HttpDdiPort(
            settings.ddi_base_url,
            settings.ddi_service_id,
            settings.ddi_service_auth_key_id,
            settings.ddi_service_auth_secret.encode("utf-8"),
            session_cookie_name=settings.authentication_session_cookie_name,
            timeout_seconds=settings.ddi_timeout_seconds,
        )
    if ddi_port is not None:
        ddi_checker = DdiMedicationChecker(ddi_port)

    mapper = ApprovedRecommendationInputMapper()
    if plan_finalizer is None and ddi_checker is not None:
        plan_finalizer = PlanFinalizer(
            plan_ledger,
            ddi_checker,
            context_provider=AuthoritativeFinalizationContextProvider(plan_ledger, mapper),
        )
    if plan_superseder is None:
        plan_superseder = PlanSuperseder(
            plan_ledger,
            ApprovedFollowUpSnapshotProvider(),
            ApprovedSuccessorPlanGenerator(),
        )
    if recommendation_workflow is None and ddi_checker is not None:
        stages = TreatmentPlanRecommendationStages(
            mapper,
            BnEvaluationOrchestrator(_ResearchBnEvaluator(), InMemoryBnEvaluationStore()),
            ddi_checker,
            plan_ledger,
        )
        recommendation_workflow = RecommendationRunWorkflow(
            RecommendationRunStore(repository),
            _UnavailableContextAssembler(),
            GenerationEligibilityPolicy(),
            stages,
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        repository.migrate()
        app.state.repository = repository
        yield

    app = FastAPI(title="INSIGHT Treatment Plan", version="0.1.0", lifespan=lifespan)
    app.state.observability = observability
    app.state.repository = repository
    app.state.recommendation_workflow = recommendation_workflow
    app.state.plan_finalizer = plan_finalizer
    app.state.plan_superseder = plan_superseder
    app.state.ddi_checker = ddi_checker

    @app.middleware("http")
    async def correlate(request: Request, call_next):
        with observability.bind(
            request.headers.get("x-correlation-id") or request.headers.get("x-request-id")
        ) as correlation_id:
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
            session = security.authorize(
                request.headers.get("cookie", ""), capability, csrf_token,
                request.cookies.get(settings.csrf_cookie_name),
            )
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

    def blockers() -> list[dict[str, str]]:
        values = []
        if recommendation_workflow is None:
            values.append(INTEGRATION_BLOCKERS["recommendation"])
        if settings.environment == "production" and not _scope_approved():
            values.append(INTEGRATION_BLOCKERS["scope"])
        if plan_finalizer is None:
            values.append(INTEGRATION_BLOCKERS["finalization"])
        if plan_superseder is None:
            values.append(INTEGRATION_BLOCKERS["supersession"])
        return values

    def blocked(name: str) -> HTTPException:
        return HTTPException(503, INTEGRATION_BLOCKERS[name])

    @app.get("/ready")
    async def ready():
        if not repository.ping():
            raise HTTPException(503, "repository unavailable")
        if settings.environment == "production":
            if settings.auth_stub_enabled or not settings.authentication_session_url:
                raise HTTPException(503, "production Authentication v2 configuration is unavailable")
            if not isinstance(security, Security) or not security.authentication_configured_for(settings.authentication_session_url):
                raise HTTPException(503, "production Authentication adapter is not wired")
            if not isinstance(repository, SQLiteRepository):
                raise HTTPException(503, "production SQLite repository is not wired")
            current_blockers = blockers()
            if ddi_port is None:
                current_blockers.append(INTEGRATION_BLOCKERS["ddi-configuration"])
            elif not await ddi_port.ready():
                current_blockers.append(INTEGRATION_BLOCKERS["ddi-unavailable"])
            if current_blockers:
                raise HTTPException(503, {"code": "TP_INTEGRATION_BLOCKED", "blockers": current_blockers})
        mode = "development-stub" if settings.auth_stub_enabled else ("rest" if security else "disabled")
        return {
            "status": "ready",
            "authMode": mode,
            "wiring": {
                "repository": "sqlite" if isinstance(repository, SQLiteRepository) else "injected",
                "recommendation": recommendation_workflow is not None,
                "finalization": plan_finalizer is not None,
                "supersession": plan_superseder is not None,
                "ddi": ddi_checker is not None,
            },
        }

    @app.get("/api/treatment-plan/v1/contract")
    def contract_discovery():
        return JSONResponse(
            {
                "moduleId": "treatment-plan",
                "moduleVersion": MODULE_VERSION,
                "interfaceVersion": INTERFACE_VERSION,
                "schemaVersions": ["1.0.0", "1.1.0"],
                "profileVersion": PROFILE_VERSION,
                "openapiPath": "/api/treatment-plan/v1/openapi.json",
                "idempotencyKeyRetentionSeconds": 86400,
                "time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
            headers=_discovery_headers(observability.correlation_id),
        )

    @app.get("/api/treatment-plan/v1/openapi.json", include_in_schema=False)
    def contract_openapi():
        return FileResponse(
            OPENAPI_PATH,
            media_type="application/json",
            headers=_discovery_headers(observability.correlation_id),
        )

    @app.get("/api/treatment-plan/v1/schemas/{name}/{version}")
    def contract_schema(name: str, version: str):
        path = SCHEMA_PATHS.get((name, version))
        if path is None:
            raise HTTPException(404, "schema not found")
        return FileResponse(
            path,
            media_type="application/schema+json",
            headers=_discovery_headers(observability.correlation_id),
        )

    @app.get("/api/treatment-plan/v1/session")
    def session(current_actor: str = Depends(actor)):
        return {"actor": current_actor, "mode": "development-stub" if settings.auth_stub_enabled else "rest"}

    @app.post("/api/treatment-plan/v1/recommendation-runs", status_code=202)
    async def create_recommendation_run(
        body: dict[str, Any],
        request: Request,
        csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        request_id: UUID = Header(alias="X-Request-ID"),
    ):
        current_session = authorized_session(request, Capability.PLAN_MUTATE, csrf_token)
        if recommendation_workflow is None:
            raise blocked("recommendation")
        expected = {"patientId", "encounterId", "severityAssessmentId", "timezone"}
        unknown = sorted(set(body) - expected)
        missing = sorted(expected - set(body))
        if unknown:
            raise HTTPException(422, "unsupported recommendation-run fields: " + ", ".join(unknown))
        if missing:
            raise HTTPException(422, "missing recommendation-run fields: " + ", ".join(missing))
        try:
            command = RecommendationRunRequest(
                str(UUID(str(body["patientId"]))),
                str(UUID(str(body["encounterId"]))),
                str(UUID(str(body["severityAssessmentId"]))),
                body["timezone"],
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(422, "clinical identifiers must be canonical UUIDs") from exc
        session_cookie = request.cookies.get(settings.authentication_session_cookie_name)
        if settings.environment != "production":
            session_cookie = session_cookie or request.cookies.get("session")
        if not session_cookie:
            raise HTTPException(401, "configured session cookie is required")
        try:
            result = await recommendation_workflow.create(
                command,
                actor_id=current_session.user_id,
                idempotency_key=idempotency_key or "",
                outbound_context=OutboundRequestContext(
                    session_cookie, str(request_id), observability.correlation_id
                ),
            )
        except RecommendationRunIdempotencyConflict as exc:
            raise HTTPException(409, str(exc)) from exc
        except RecommendationRunError as exc:
            raise HTTPException(422, str(exc)) from exc
        return JSONResponse(
            result.to_dict(),
            status_code=202,
            headers={
                "Idempotency-Key": idempotency_key or "",
                "X-Schema-Version": "1.1.0",
                "X-Request-ID": str(request_id),
                "X-Correlation-ID": observability.correlation_id,
            },
        )

    @app.get("/api/treatment-plan/v1/recommendation-runs/{run_id}")
    def read_recommendation_run(run_id: UUID, request: Request):
        current_session = authorized_session(request, Capability.PLAN_READ)
        if recommendation_workflow is None:
            raise blocked("recommendation")
        try:
            result = recommendation_workflow.read(str(run_id), current_session.user_id)
        except RecommendationRunNotFound as exc:
            raise HTTPException(404, str(exc)) from exc
        except RecommendationRunUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        return JSONResponse(result.to_dict(), headers={"X-Schema-Version": "1.1.0"})

    @app.get("/api/treatment-plan/v1/plans/{plan_id}")
    def read_plan(plan_id: UUID, request: Request):
        plan_id = str(plan_id)
        authorized_session(request, Capability.PLAN_READ)
        try:
            view = plan_ledger.get(plan_id)
        except PlanNotFound as exc:
            raise HTTPException(404, str(exc)) from exc
        return JSONResponse(view.to_dict(), headers={"ETag": view.etag, "X-Schema-Version": "1.1.0"})

    @app.get("/api/treatment-plan/v1/patients/{patient_id}/plans")
    def read_patient_plans(patient_id: UUID, request: Request):
        authorized_session(request, Capability.PLAN_READ)
        return JSONResponse(
            {"patientId": str(patient_id), "items": plan_ledger.list_for_patient(str(patient_id))},
            headers={"X-Schema-Version": "1.1.0"},
        )

    @app.post("/api/treatment-plan/v1/assistant/advisory")
    def assistant_advisory(body: dict[str, Any], request: Request):
        authorized_session(request, Capability.PLAN_READ)
        unknown = sorted(set(body) - {"planId", "prompt"})
        missing = sorted({"planId", "prompt"} - set(body))
        if unknown:
            raise HTTPException(422, "unsupported assistant fields: " + ", ".join(unknown))
        if missing:
            raise HTTPException(422, "missing assistant fields: " + ", ".join(missing))
        try:
            plan_id = str(UUID(str(body["planId"])))
        except (TypeError, ValueError) as exc:
            raise HTTPException(422, "planId must be a canonical UUID") from exc
        if assistant is None:
            raise HTTPException(503, "assistant provider is unavailable; clinical workflows remain available")
        try:
            view = plan_ledger.get(plan_id)
            result = assistant.advise(view.to_dict(), body["prompt"])
        except PlanNotFound as exc:
            raise HTTPException(404, str(exc)) from exc
        except InvalidAssistantRequest as exc:
            raise HTTPException(422, str(exc)) from exc
        except AssistantUnavailable as exc:
            raise HTTPException(503, "assistant provider is unavailable; clinical workflows remain available") from exc
        observability.metric("tp_assistant_requests", 1, labels={"module": "assistant", "outcome": "success"})
        return JSONResponse(result, headers={"X-Schema-Version": "1.0.0"})

    @app.post("/api/treatment-plan/v1/plans/{plan_id}/supersede", status_code=201)
    async def supersede_plan(
        plan_id: UUID,
        body: dict[str, Any],
        request: Request,
        csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
        idempotency_key: str = Header(alias="Idempotency-Key"),
        request_id: UUID = Header(alias="X-Request-ID"),
    ):
        plan_id = str(plan_id)
        authorized_session(request, Capability.PLAN_MUTATE, csrf_token)
        if not idempotency_key.strip() or len(idempotency_key) > 200:
            raise HTTPException(422, "Idempotency-Key must contain 1 to 200 characters")
        if plan_superseder is None:
            raise blocked("supersession")
        try:
            result = await plan_superseder.supersede(plan_id, body)
            successor = plan_ledger.get(result.primary_plan["planId"])
        except PlanNotFound as exc:
            raise HTTPException(404, str(exc)) from exc
        except PlanSuperseded as exc:
            raise HTTPException(409, str(exc)) from exc
        except (InvalidEdit, SupersessionError) as exc:
            raise HTTPException(422, str(exc)) from exc
        return JSONResponse(
            {"planView": successor.to_dict(), "supersession": result.supersession},
            status_code=201,
            headers={
                "ETag": successor.etag,
                "Idempotency-Key": idempotency_key,
                "X-Schema-Version": "1.1.0",
                "X-Request-ID": str(request_id),
                "X-Correlation-ID": observability.correlation_id,
            },
        )

    @app.patch("/api/treatment-plan/v1/plans/{plan_id}/draft")
    def edit_draft(
        plan_id: UUID,
        body: dict[str, Any],
        request: Request,
        if_match: str | None = Header(default=None, alias="If-Match"),
        csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    ):
        plan_id = str(plan_id)
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
        plan_id: UUID,
        body: dict[str, Any],
        request: Request,
        if_match: str | None = Header(default=None, alias="If-Match"),
        csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        request_id: UUID = Header(alias="X-Request-ID"),
        correlation_id: str | None = Header(default=None, alias="X-Correlation-ID"),
    ):
        plan_id = str(plan_id)
        current_session = authorized_session(request, Capability.PLAN_MUTATE, csrf_token)
        if plan_finalizer is None:
            raise blocked("finalization")
        unknown = sorted(set(body) - {"attestation"})
        if unknown:
            raise HTTPException(422, "unsupported finalization fields: " + ", ".join(unknown))
        if "attestation" not in body:
            raise HTTPException(422, "attestation is required")
        command = FinalizationCommand(
            actor_id=current_session.user_id,
            session_id=current_session.session_id,
            attestation=body["attestation"],
            request_id=str(request_id),
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
    def read_plan_provenance(plan_id: UUID, request: Request):
        plan_id = str(plan_id)
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
    def read_plan_audit(plan_id: UUID, request: Request):
        plan_id = str(plan_id)
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

        @app.get("/modules/treatment-plan/{plan_id}", include_in_schema=False)
        def module_plan_shell(plan_id: UUID):
            return FileResponse(frontend / "index.html")
    return app


app = create_app()




