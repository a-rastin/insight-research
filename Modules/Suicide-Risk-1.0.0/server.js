const crypto = require("node:crypto");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { authenticationReachable, fetchSession } = require("./auth");
const { mintCsrf, verifyCsrf } = require("./csrf");
const { SuicideRiskRepository, canonicalJson } = require("./repository");

const INTERFACE_VERSION = "1.0.0";
const SCHEMA_VERSION = "1.0.0";
const MODULE_VERSION = "1.0.0";
const API_PREFIX = "/api/suicide-risk/v1";
const PORT = Number(process.env.PORT || 8109);
const DATA_DIR = process.env.SUICIDE_RISK_DATA_DIR || path.join(__dirname, "data");
const DATABASE_PATH = process.env.SUICIDE_RISK_DB_PATH || path.join(DATA_DIR, "suicide-risk.db");
const AUTH_BASE_URL = process.env.SUICIDE_RISK_AUTH_BASE_URL || "http://127.0.0.1:8101";
const AUTH_TIMEOUT_MS = Number(process.env.SUICIDE_RISK_AUTH_TIMEOUT_MS || 2000);
const PRODUCTION = (process.env.NODE_ENV || "development") === "production";
const CSRF_SECRET = process.env.SUICIDE_RISK_CSRF_SECRET || (PRODUCTION ? "" : "suicide-risk-development-csrf-secret");
const ALLOWED_ORIGINS = new Set((process.env.SUICIDE_RISK_ALLOWED_ORIGINS || "").split(",").map((value) => value.trim()).filter(Boolean));
const PUBLIC_DIR = path.join(__dirname, "public");
const CONTRACT_DIR = path.join(__dirname, "contracts");
const STATES = new Set([
  "unknown",
  "unavailable",
  "conflicting",
  "imminent-suicide-risk",
  "substantial-suicide-risk-requiring-urgent-evaluation"
]);
const URGENT_STATES = new Set([
  "imminent-suicide-risk",
  "substantial-suicide-risk-requiring-urgent-evaluation"
]);
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const MIME = { ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "application/javascript; charset=utf-8", ".json": "application/json; charset=utf-8" };

function validateConfiguration() {
  if (!Number.isInteger(PORT) || PORT < 1 || PORT > 65535) throw new Error("PORT must be a valid TCP port");
  if (!Number.isFinite(AUTH_TIMEOUT_MS) || AUTH_TIMEOUT_MS < 100 || AUTH_TIMEOUT_MS > 30000) throw new Error("SUICIDE_RISK_AUTH_TIMEOUT_MS is invalid");
  const auth = new URL(AUTH_BASE_URL);
  if (!["http:", "https:"].includes(auth.protocol)) throw new Error("SUICIDE_RISK_AUTH_BASE_URL must use HTTP or HTTPS");
  if (CSRF_SECRET.length < 32) throw new Error("SUICIDE_RISK_CSRF_SECRET must contain at least 32 characters");
  if (ALLOWED_ORIGINS.has("*")) throw new Error("SUICIDE_RISK_ALLOWED_ORIGINS cannot contain a wildcard");
  for (const origin of ALLOWED_ORIGINS) {
    const parsed = new URL(origin);
    if (parsed.origin !== origin || !["http:", "https:"].includes(parsed.protocol)) throw new Error("Allowed origins must be exact HTTP origins");
  }
}

function isUuid(value) {
  return typeof value === "string" && UUID.test(value);
}

function parseCookies(req) {
  return Object.fromEntries((req.headers.cookie || "").split(";").map((part) => part.trim()).filter(Boolean).map((part) => {
    const separator = part.indexOf("=");
    return separator < 0 ? [part, ""] : [part.slice(0, separator), decodeURIComponent(part.slice(separator + 1))];
  }));
}

function context(req) {
  const requestId = isUuid(req.headers["x-request-id"]) ? req.headers["x-request-id"] : crypto.randomUUID();
  return {
    requestId,
    correlationId: isUuid(req.headers["x-correlation-id"]) ? req.headers["x-correlation-id"] : requestId
  };
}

function send(res, status, payload, ctx, headers = {}, type = "application/json; charset=utf-8") {
  res.writeHead(status, {
    "Content-Type": type,
    "Cache-Control": "no-store",
    "X-Schema-Version": SCHEMA_VERSION,
    "X-Request-ID": ctx.requestId,
    "X-Correlation-ID": ctx.correlationId,
    ...headers
  });
  res.end(JSON.stringify(payload));
}

function problem(res, status, code, title, detail, ctx, errors) {
  const payload = { type: `urn:insight:problem:${code.toLowerCase().replaceAll("_", "-")}`, title, status, code, detail, requestId: ctx.requestId };
  if (errors?.length) payload.errors = errors.map((message) => ({ code, message }));
  send(res, status, payload, ctx, {}, "application/problem+json");
}

async function body(req) {
  return new Promise((resolve, reject) => {
    let raw = "";
    req.on("data", (chunk) => {
      raw += chunk;
      if (raw.length > 65536) reject(Object.assign(new Error("Body too large"), { status: 413 }));
    });
    req.on("end", () => {
      try { resolve(raw ? JSON.parse(raw) : {}); } catch { reject(Object.assign(new Error("Invalid JSON"), { status: 400 })); }
    });
    req.on("error", reject);
  });
}

async function authorize(req, res, ctx, write = false) {
  const result = await fetchSession(AUTH_BASE_URL, req.headers.cookie, AUTH_TIMEOUT_MS);
  if (result.unavailable) {
    problem(res, 503, "COMMON_DEPENDENCY_UNAVAILABLE", "Authentication unavailable", "Authentication could not verify the session.", ctx);
    return null;
  }
  if (!result.session) {
    problem(res, 401, "COMMON_AUTHENTICATION_REQUIRED", "Authentication required", "A current authorized psychiatrist session is required.", ctx);
    return null;
  }
  if (result.session.role !== "psychiatrist") {
    problem(res, 403, "COMMON_FORBIDDEN", "Forbidden", "Psychiatrist authority is required.", ctx);
    return null;
  }
  if (write && !verifyCsrf(CSRF_SECRET, result.session.sessionId, parseCookies(req).suicide_risk_csrf, req.headers["x-csrf-token"])) {
    problem(res, 403, "COMMON_CSRF_REJECTED", "CSRF validation failed", "A valid Suicide Risk CSRF token is required.", ctx);
    return null;
  }
  return result.session;
}

function requireSchema(req, res, ctx) {
  if (req.headers["x-schema-version"] !== SCHEMA_VERSION) {
    problem(res, 400, "COMMON_UNSUPPORTED_SCHEMA_MAJOR", "Unsupported schema version", "X-Schema-Version must be 1.0.0.", ctx);
    return false;
  }
  return true;
}

function validateWrite(value, creating) {
  const required = creating ? ["patientId", "encounterId", "riskState", "actor"] : ["riskState", "actor"];
  const allowed = new Set(required);
  const errors = [];
  if (!value || typeof value !== "object" || Array.isArray(value)) return ["assessment must be an object"];
  for (const key of required) if (!Object.hasOwn(value, key)) errors.push(`${key} is required`);
  for (const key of Object.keys(value)) if (!allowed.has(key)) errors.push(`${key} is not allowed`);
  if (creating && !isUuid(value.patientId)) errors.push("patientId must be a UUID");
  if (creating && !isUuid(value.encounterId)) errors.push("encounterId must be a UUID");
  if (!STATES.has(value.riskState)) errors.push("riskState is not an approved state");
  if (!value.actor || Object.keys(value.actor).sort().join(",") !== "actorId,role" || !isUuid(value.actor.actorId) || value.actor.role !== "psychiatrist") {
    errors.push("actor must contain only a psychiatrist actorId UUID and role");
  }
  return errors;
}

function disposition(riskState) {
  if (URGENT_STATES.has(riskState)) return {
    outcome: "emergency-blocked",
    code: "TP_EMERGENCY_ACTION_REQUIRED",
    routinePlanningAllowed: false,
    overrideAllowed: false,
    persistentUntilResolved: true,
    guidance: "Stop routine planning and follow the applicable local emergency protocol for immediate clinical evaluation."
  };
  if (riskState === "conflicting") return {
    outcome: "blocked",
    code: "TP_REQUIRED_DATA_CONFLICTING",
    routinePlanningAllowed: false,
    overrideAllowed: false,
    persistentUntilResolved: true,
    guidance: "Resolve the conflicting source data and create a new validated snapshot."
  };
  return {
    outcome: "blocked",
    code: "TP_SUICIDE_RISK_UNAVAILABLE",
    routinePlanningAllowed: false,
    overrideAllowed: false,
    persistentUntilResolved: true,
    guidance: "Complete or obtain the approved suicide-risk assessment."
  };
}

function canonicalAssessment(value, ctx, existing) {
  const now = new Date().toISOString();
  return {
    interfaceVersion: INTERFACE_VERSION,
    schemaVersion: SCHEMA_VERSION,
    assessmentId: existing?.assessmentId || crypto.randomUUID(),
    patientId: existing?.patientId || value.patientId,
    encounterId: existing?.encounterId || value.encounterId,
    assessmentType: "psychiatrist-suicide-risk-assertion",
    instrument: { name: "C-SSRS", completionClaimed: false, sourceLicensingStatus: "unavailable", questionsDefined: false, scoringDefined: false },
    riskState: value.riskState,
    riskScore: null,
    safetyDisposition: disposition(value.riskState),
    actor: { actorId: value.actor.actorId, role: "psychiatrist" },
    createdAt: existing?.createdAt || now,
    updatedAt: now,
    resourceVersion: existing ? existing.resourceVersion + 1 : 1,
    provenance: {
      sourceModule: "suicide-risk",
      policyVersion: "insight.treatment-plan-safety-policy/1.0.0",
      governanceVersion: "insight.clinical-ownership/1.0.0",
      createdRequestId: existing?.provenance.createdRequestId || ctx.requestId,
      updatedRequestId: ctx.requestId
    }
  };
}

function etag(assessment) {
  return `"suicide-risk-assessment-${assessment.assessmentId}-v${assessment.resourceVersion}"`;
}

function snapshot(assessment) {
  const sourceHash = crypto.createHash("sha256").update(canonicalJson(assessment)).digest("hex");
  return {
    interfaceVersion: INTERFACE_VERSION,
    schemaVersion: SCHEMA_VERSION,
    snapshotType: "suicide-risk-encounter-snapshot",
    patientId: assessment.patientId,
    encounterId: assessment.encounterId,
    source: {
      owner: "suicide-risk",
      assessmentId: assessment.assessmentId,
      resourceVersion: assessment.resourceVersion,
      etag: etag(assessment),
      contentSha256: sourceHash
    },
    assessment
  };
}

function idempotencyKey(req, res, ctx) {
  const key = req.headers["idempotency-key"];
  if (typeof key !== "string" || !/^[A-Za-z0-9._~-]{16,128}$/.test(key)) {
    problem(res, 400, "COMMON_IDEMPOTENCY_KEY_REQUIRED", "Idempotency key required", "Idempotency-Key must contain 16 to 128 supported characters.", ctx);
    return null;
  }
  return key;
}

async function createAssessment(req, res, ctx, session) {
  if (!requireSchema(req, res, ctx)) return;
  const key = idempotencyKey(req, res, ctx);
  if (!key) return;
  const value = await body(req);
  const errors = validateWrite(value, true);
  if (errors.length) return problem(res, 400, "SUICIDE_RISK_INVALID_ASSESSMENT", "Invalid suicide-risk assessment", "The assertion does not satisfy schema 1.0.0.", ctx, errors);
  if (value.actor.actorId !== session.actorId) return problem(res, 403, "COMMON_ACTOR_MISMATCH", "Actor mismatch", "Assessment actor must match the authenticated psychiatrist.", ctx);
  const assessment = canonicalAssessment(value, ctx);
  const fingerprint = crypto.createHash("sha256").update(canonicalJson(value)).digest("hex");
  const result = repository.createIdempotent({ actorId: session.actorId, key, fingerprint, assessment, requestId: ctx.requestId });
  if (result.conflict) return problem(res, 409, "COMMON_IDEMPOTENCY_KEY_REUSED", "Idempotency key reused", "The key was already used with different input.", ctx);
  send(res, 201, result.assessment, ctx, { ETag: etag(result.assessment) });
}

function getAssessment(res, assessmentId, ctx) {
  if (!isUuid(assessmentId)) return problem(res, 400, "SUICIDE_RISK_INVALID_ASSESSMENT_ID", "Invalid assessment identifier", "assessmentId must be a UUID.", ctx);
  const assessment = repository.get(assessmentId);
  if (!assessment) return problem(res, 404, "SUICIDE_RISK_ASSESSMENT_NOT_FOUND", "Assessment not found", "No suicide-risk assessment exists for that identifier.", ctx);
  send(res, 200, assessment, ctx, { ETag: etag(assessment) });
}

async function updateAssessment(req, res, assessmentId, ctx, session) {
  if (!requireSchema(req, res, ctx)) return;
  if (!isUuid(assessmentId)) return problem(res, 400, "SUICIDE_RISK_INVALID_ASSESSMENT_ID", "Invalid assessment identifier", "assessmentId must be a UUID.", ctx);
  const value = await body(req);
  const errors = validateWrite(value, false);
  if (errors.length) return problem(res, 400, "SUICIDE_RISK_INVALID_ASSESSMENT", "Invalid suicide-risk assessment", "The assertion does not satisfy schema 1.0.0.", ctx, errors);
  if (value.actor.actorId !== session.actorId) return problem(res, 403, "COMMON_ACTOR_MISMATCH", "Actor mismatch", "Assessment actor must match the authenticated psychiatrist.", ctx);
  const current = repository.get(assessmentId);
  if (!current) return problem(res, 404, "SUICIDE_RISK_ASSESSMENT_NOT_FOUND", "Assessment not found", "No suicide-risk assessment exists for that identifier.", ctx);
  if (!req.headers["if-match"]) return problem(res, 428, "COMMON_PRECONDITION_REQUIRED", "Precondition required", "If-Match is required for assessment updates.", ctx);
  if (req.headers["if-match"] !== etag(current)) return problem(res, 412, "COMMON_PRECONDITION_FAILED", "Precondition failed", "If-Match does not match the current resource version.", ctx);
  const result = repository.update({ assessment: canonicalAssessment(value, ctx, current), expectedVersion: current.resourceVersion, actorId: session.actorId, requestId: ctx.requestId });
  if (result.stale) return problem(res, 412, "COMMON_PRECONDITION_FAILED", "Precondition failed", "Assessment changed after it was read.", ctx);
  send(res, 200, result.assessment, ctx, { ETag: etag(result.assessment) });
}

function latest(res, encounterId, ctx, asSnapshot) {
  if (!isUuid(encounterId)) return problem(res, 400, "SUICIDE_RISK_INVALID_ENCOUNTER_ID", "Invalid encounter identifier", "encounterId must be a UUID.", ctx);
  const assessment = repository.latest(encounterId);
  if (!assessment) return problem(res, 404, "SUICIDE_RISK_ASSESSMENT_NOT_FOUND", "Assessment not found", "No suicide-risk assessment exists for that encounter.", ctx);
  send(res, 200, asSnapshot ? snapshot(assessment) : assessment, ctx, { ETag: etag(assessment) });
}

function cors(req, res, ctx) {
  const origin = req.headers.origin;
  if (!ALLOWED_ORIGINS.has(origin)) return problem(res, 403, "COMMON_ORIGIN_FORBIDDEN", "Origin forbidden", "The request origin is not allowed.", ctx);
  res.writeHead(204, {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Credentials": "true",
    "Access-Control-Allow-Methods": "GET, POST, PUT, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, X-Schema-Version, X-CSRF-Token, Idempotency-Key, If-Match, X-Request-ID, X-Correlation-ID",
    Vary: "Origin"
  });
  res.end();
}

function contractArtifact(name, res, ctx) {
  const files = { document: "suicide-risk-assessment-v1.contract.json", schema: "suicide-risk-assessment-v1.schema.json", openapi: "openapi-v1.json" };
  if (!files[name]) return false;
  send(res, 200, JSON.parse(fs.readFileSync(path.join(CONTRACT_DIR, files[name]), "utf8")), ctx);
  return true;
}

function staticFile(pathname, res) {
  const file = pathname === "/" ? "index.html" : pathname.slice(1);
  if (!new Set(["index.html", "app.js", "styles.css"]).has(file)) return false;
  const bytes = fs.readFileSync(path.join(PUBLIC_DIR, file));
  res.writeHead(200, { "Content-Type": MIME[path.extname(file)], "Cache-Control": "no-store" });
  res.end(bytes);
  return true;
}

let repository;
const server = http.createServer(async (req, res) => {
  const ctx = context(req);
  try {
    const url = new URL(req.url, "http://module.local");
    if (req.method === "GET" && url.pathname === "/healthz") return send(res, 200, { status: "alive", module: "suicide-risk", moduleVersion: MODULE_VERSION }, ctx);
    if (req.method === "GET" && url.pathname === "/readyz") {
      const ready = repository.readiness() && await authenticationReachable(AUTH_BASE_URL, AUTH_TIMEOUT_MS);
      return ready ? send(res, 200, { status: "ready", module: "suicide-risk" }, ctx)
        : problem(res, 503, "SUICIDE_RISK_NOT_READY", "Suicide Risk not ready", "A required local or authentication dependency is unavailable.", ctx);
    }
    if (req.method === "OPTIONS" && url.pathname.startsWith(API_PREFIX)) return cors(req, res, ctx);
    if (req.method === "GET" && url.pathname === `${API_PREFIX}/contract`) return send(res, 200, {
      moduleId: "suicide-risk", moduleVersion: MODULE_VERSION, interfaceVersion: INTERFACE_VERSION, schemaVersion: SCHEMA_VERSION,
      artifacts: { document: `${API_PREFIX}/contract/document`, schema: `${API_PREFIX}/contract/schema`, openapi: `${API_PREFIX}/contract/openapi` }
    }, ctx);
    const contractMatch = url.pathname.match(new RegExp(`^${API_PREFIX}/contract/(document|schema|openapi)$`));
    if (req.method === "GET" && contractMatch) return contractArtifact(contractMatch[1], res, ctx);
    if (req.method === "GET" && url.pathname === `${API_PREFIX}/csrf`) {
      const session = await authorize(req, res, ctx);
      if (!session) return;
      const token = mintCsrf(CSRF_SECRET, session.sessionId);
      return send(res, 200, { token }, ctx, { "Set-Cookie": `suicide_risk_csrf=${encodeURIComponent(token)}; Path=${API_PREFIX}; SameSite=Lax${PRODUCTION ? "; Secure" : ""}` });
    }
    if (req.method === "POST" && url.pathname === `${API_PREFIX}/assessments`) {
      const session = await authorize(req, res, ctx, true);
      if (session) await createAssessment(req, res, ctx, session);
      return;
    }
    const assessmentMatch = url.pathname.match(new RegExp(`^${API_PREFIX}/assessments/([^/]+)$`));
    if (assessmentMatch && req.method === "GET") {
      if (await authorize(req, res, ctx)) getAssessment(res, assessmentMatch[1], ctx);
      return;
    }
    if (assessmentMatch && req.method === "PUT") {
      const session = await authorize(req, res, ctx, true);
      if (session) await updateAssessment(req, res, assessmentMatch[1], ctx, session);
      return;
    }
    const encounterMatch = url.pathname.match(new RegExp(`^${API_PREFIX}/encounters/([^/]+)/(assessments/latest|snapshot)$`));
    if (encounterMatch && req.method === "GET") {
      if (await authorize(req, res, ctx)) latest(res, encounterMatch[1], ctx, encounterMatch[2] === "snapshot");
      return;
    }
    if (req.method === "GET" && staticFile(url.pathname, res)) return;
    problem(res, 404, "COMMON_NOT_FOUND", "Not found", "The requested resource is not available.", ctx);
  } catch (error) {
    problem(res, error.status || 500, error.status === 400 ? "COMMON_INVALID_JSON" : "SUICIDE_RISK_INTERNAL_ERROR",
      error.status === 400 ? "Invalid JSON" : "Internal error", error.status === 400 ? "The request body is not valid JSON." : "The request could not be completed.", ctx);
  }
});

function start() {
  validateConfiguration();
  fs.mkdirSync(DATA_DIR, { recursive: true });
  repository = new SuicideRiskRepository(DATABASE_PATH);
  server.listen(PORT, "127.0.0.1");
}

function stop() {
  server.close(() => {
    repository?.close();
    process.exit(0);
  });
}

if (require.main === module) {
  start();
  process.on("SIGTERM", stop);
  process.on("SIGINT", stop);
}

module.exports = { API_PREFIX, INTERFACE_VERSION, SCHEMA_VERSION, canonicalAssessment, disposition, snapshot, start, validateWrite };
