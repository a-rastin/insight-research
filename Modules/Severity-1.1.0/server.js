import express from "express";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { createHash, randomUUID } from "crypto";
import { fetchSession, authenticationReachable } from "./auth.js";
import { mintCsrf, verifyCsrf } from "./csrf.js";
import { SeverityRepository } from "./repository.js";
import {
  INTERFACE_VERSION,
  RULE_VERSION,
  SCALE_VERSION,
  SCHEMA_VERSION,
  evaluatePanss,
  isUuid,
  validateAssessmentInput
} from "./panss.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const dataDir = path.join(__dirname, "data");
const environment = process.env.NODE_ENV || "development";
const production = environment === "production";
const port = Number(process.env.PORT || 3000);
const databasePath = process.env.SEVERITY_DB_PATH || path.join(dataDir, "severity.db");
const authBaseUrl = process.env.SEVERITY_AUTH_BASE_URL || "http://127.0.0.1:8101";
const authTimeoutMs = Number(process.env.SEVERITY_AUTH_TIMEOUT_MS || 2000);
const csrfSecret = process.env.SEVERITY_CSRF_SECRET || (production ? "" : "severity-development-only-csrf-secret");
const allowedOrigins = new Set((process.env.SEVERITY_ALLOWED_ORIGINS || "").split(",").map(value => value.trim()).filter(Boolean));
const contractDir = path.join(__dirname, "contracts");

function validateConfiguration() {
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error("PORT must be a valid TCP port");
  if (!Number.isFinite(authTimeoutMs) || authTimeoutMs < 100 || authTimeoutMs > 30000) throw new Error("SEVERITY_AUTH_TIMEOUT_MS is invalid");
  let authUrl;
  try {
    authUrl = new URL(authBaseUrl);
  } catch {
    throw new Error("SEVERITY_AUTH_BASE_URL must be an absolute HTTP URL");
  }
  if (!["http:", "https:"].includes(authUrl.protocol)) throw new Error("SEVERITY_AUTH_BASE_URL must use HTTP or HTTPS");
  if (csrfSecret.length < 32) throw new Error("SEVERITY_CSRF_SECRET must contain at least 32 characters");
  if (allowedOrigins.has("*")) throw new Error("SEVERITY_ALLOWED_ORIGINS cannot contain a wildcard");
  for (const origin of allowedOrigins) {
    const parsed = new URL(origin);
    if (parsed.origin !== origin || !["http:", "https:"].includes(parsed.protocol)) {
      throw new Error("SEVERITY_ALLOWED_ORIGINS must contain exact HTTP origins");
    }
  }
}

validateConfiguration();
fs.mkdirSync(path.dirname(databasePath), { recursive: true });
const repository = new SeverityRepository(databasePath, [
  { name: "severity-v1-json", kind: "v1", path: process.env.SEVERITY_DATA_FILE || path.join(dataDir, "assessments.json") },
  { name: "severity-v2-json", kind: "v2", path: process.env.SEVERITY_V2_DATA_FILE || path.join(dataDir, "assessments-v2.json") }
]);

const app = express();
app.disable("x-powered-by");
app.use(express.json({ limit: "1mb" }));

app.use((req, res, next) => {
  const origin = req.get("Origin");
  if (origin && allowedOrigins.has(origin)) {
    res.setHeader("Access-Control-Allow-Origin", origin);
    res.setHeader("Access-Control-Allow-Credentials", "true");
    res.setHeader("Vary", "Origin");
    res.setHeader("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type, X-Schema-Version, X-Request-ID, X-Correlation-ID, X-Causation-ID, Idempotency-Key, If-Match, X-CSRF-Token");
    res.setHeader("Access-Control-Expose-Headers", "ETag, X-Schema-Version, X-Request-ID");
  }
  if (req.method === "OPTIONS") {
    return origin && allowedOrigins.has(origin) ? res.sendStatus(204) : res.sendStatus(403);
  }
  next();
});

function requestId(req) {
  return isUuid(req.get("X-Request-ID")) ? req.get("X-Request-ID") : randomUUID();
}

function setV2Headers(res, id) {
  res.setHeader("X-Schema-Version", SCHEMA_VERSION);
  res.setHeader("X-Request-ID", id);
}

function problem(res, id, status, code, title, detail) {
  setV2Headers(res, id);
  return res.status(status).type("application/problem+json").json({
    type: `https://insight.local/problems/${code.toLowerCase().replaceAll("_", "-")}`,
    title,
    status,
    code,
    detail,
    requestId: id
  });
}

function cookies(req) {
  return Object.fromEntries((req.get("Cookie") || "").split(";").map(part => part.trim()).filter(Boolean).map(part => {
    const separator = part.indexOf("=");
    if (separator < 0) return [part, ""];
    try {
      return [part.slice(0, separator), decodeURIComponent(part.slice(separator + 1))];
    } catch {
      return [part.slice(0, separator), ""];
    }
  }));
}

async function authorize(req, res, id, requireWrite = false) {
  const result = await fetchSession(authBaseUrl, req.get("Cookie"), authTimeoutMs);
  if (result.unavailable) {
    problem(res, id, 503, "COMMON_DEPENDENCY_UNAVAILABLE", "Authentication unavailable", "Authentication could not verify the session.");
    return null;
  }
  if (!result.session) {
    problem(res, id, 401, "COMMON_AUTHENTICATION_REQUIRED", "Authentication required", "A current authorized session is required.");
    return null;
  }
  if (result.session.role !== "psychiatrist") {
    problem(res, id, 403, "COMMON_FORBIDDEN", "Forbidden", "Psychiatrist authority is required.");
    return null;
  }
  if (requireWrite && !verifyCsrf(csrfSecret, result.session.sessionId, cookies(req).severity_csrf, req.get("X-CSRF-Token"))) {
    problem(res, id, 403, "COMMON_CSRF_REJECTED", "CSRF validation failed", "A valid Severity CSRF token is required.");
    return null;
  }
  return result.session;
}

function validateV2Request(req, res, id, includeIdentity) {
  if (req.get("X-Schema-Version") !== SCHEMA_VERSION) {
    problem(res, id, 400, "COMMON_UNSUPPORTED_SCHEMA_MAJOR", "Unsupported schema version", "X-Schema-Version must be 2.0.0.");
    return false;
  }
  const validationError = validateAssessmentInput(req.body, includeIdentity);
  if (validationError) {
    problem(res, id, 400, "SEVERITY_INVALID_ASSESSMENT", "Invalid PANSS assessment", validationError);
    return false;
  }
  return true;
}

function assessmentFromInput(input, id, existing) {
  const now = new Date().toISOString();
  const state = { "in-progress": "incomplete", completed: "completed", skipped: "passed" }[input.status];
  const { valid: _valid, ...evaluation } = evaluatePanss(state, input.itemScores, input.scores);
  return {
    interfaceVersion: INTERFACE_VERSION,
    schemaVersion: SCHEMA_VERSION,
    assessmentId: existing?.assessmentId || randomUUID(),
    patientId: existing?.patientId || input.patientId,
    encounterId: existing?.encounterId || input.encounterId,
    assessmentType: "PANSS",
    status: input.status,
    itemScores: input.itemScores,
    scores: evaluation.scores,
    evaluation,
    resourceVersion: existing ? existing.resourceVersion + 1 : 1,
    provenance: {
      sourceModule: "severity",
      createdAt: existing?.provenance.createdAt || now,
      updatedAt: now,
      createdRequestId: existing?.provenance.createdRequestId || id,
      updatedRequestId: id,
      scaleVersion: SCALE_VERSION,
      ruleVersion: RULE_VERSION
    }
  };
}

function etag(assessment) {
  return `"severity-assessment-${assessment.assessmentId}-v${assessment.resourceVersion}"`;
}

function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value !== null && typeof value === "object") {
    return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

app.get("/healthz", (_req, res) => res.json({ status: "live", module: "severity" }));

app.get("/readyz", async (req, res) => {
  const id = requestId(req);
  try {
    const storageReady = repository.readiness();
    const authReady = await authenticationReachable(authBaseUrl, authTimeoutMs);
    if (!storageReady || !authReady) {
      return problem(res, id, 503, "SEVERITY_NOT_READY", "Severity is not ready", "A required local or Authentication dependency is unavailable.");
    }
    setV2Headers(res, id);
    res.json({ status: "ready", module: "severity", schemaVersion: SCHEMA_VERSION });
  } catch {
    problem(res, id, 503, "SEVERITY_NOT_READY", "Severity is not ready", "A required local or Authentication dependency is unavailable.");
  }
});

app.get("/api/severity/v2/contract", (req, res) => {
  const id = requestId(req);
  setV2Headers(res, id);
  res.json({
    interfaceVersion: INTERFACE_VERSION,
    schemaVersion: SCHEMA_VERSION,
    scaleVersion: SCALE_VERSION,
    ruleVersion: RULE_VERSION,
    contract: "/api/severity/v2/contract/document",
    schema: "/api/severity/v2/contract/schema",
    openapi: "/api/severity/v2/contract/openapi",
    idempotencyRetentionSeconds: 86400
  });
});

for (const [route, file] of [
  ["document", "panss-assessment-v2.contract.json"],
  ["schema", "panss-assessment-v2.schema.json"],
  ["openapi", "openapi-v2.json"]
]) {
  app.get(`/api/severity/v2/contract/${route}`, (req, res) => {
    setV2Headers(res, requestId(req));
    res.sendFile(path.join(contractDir, file));
  });
}

app.get("/api/severity/v2/csrf", async (req, res) => {
  const id = requestId(req);
  const session = await authorize(req, res, id);
  if (!session) return;
  const token = mintCsrf(csrfSecret, session.sessionId);
  res.cookie("severity_csrf", token, { httpOnly: false, sameSite: "strict", secure: production, path: "/api/severity" });
  setV2Headers(res, id);
  res.json({ token });
});

app.post("/api/severity/v2/assessments", async (req, res) => {
  const id = requestId(req);
  const session = await authorize(req, res, id, true);
  if (!session || !validateV2Request(req, res, id, true)) return;
  const key = req.get("Idempotency-Key");
  if (!key || key.length < 8 || key.length > 128) {
    return problem(res, id, 400, "COMMON_IDEMPOTENCY_KEY_REQUIRED", "Idempotency key required", "Idempotency-Key must contain 8 to 128 characters.");
  }
  const fingerprint = createHash("sha256").update(canonicalJson(req.body)).digest("hex");
  try {
    const assessment = assessmentFromInput(req.body, id);
    const result = repository.createIdempotent({ actorId: session.actorId, key, fingerprint, assessment, requestId: id });
    if (result.conflict) {
      return problem(res, id, 409, "COMMON_IDEMPOTENCY_KEY_REUSED", "Idempotency key reused", "Idempotency-Key was already used with different input by this actor.");
    }
    setV2Headers(res, id);
    res.setHeader("ETag", etag(result.assessment));
    res.status(201).json(result.assessment);
  } catch {
    problem(res, id, 503, "SEVERITY_STORAGE_UNAVAILABLE", "Severity storage unavailable", "Assessment could not be persisted.");
  }
});

app.get("/api/severity/v2/assessments/:assessmentId", async (req, res) => {
  const id = requestId(req);
  const session = await authorize(req, res, id);
  if (!session) return;
  if (!isUuid(req.params.assessmentId)) {
    return problem(res, id, 400, "SEVERITY_INVALID_ASSESSMENT_ID", "Invalid assessment identifier", "assessmentId must be a UUID.");
  }
  try {
    const assessment = repository.get(req.params.assessmentId);
    if (!assessment) return problem(res, id, 404, "SEVERITY_ASSESSMENT_NOT_FOUND", "Assessment not found", "No PANSS assessment has that identifier.");
    setV2Headers(res, id);
    res.setHeader("ETag", etag(assessment));
    res.json(assessment);
  } catch {
    problem(res, id, 503, "SEVERITY_STORAGE_UNAVAILABLE", "Severity storage unavailable", "Assessment could not be read.");
  }
});

app.put("/api/severity/v2/assessments/:assessmentId", async (req, res) => {
  const id = requestId(req);
  const session = await authorize(req, res, id, true);
  if (!session) return;
  if (!isUuid(req.params.assessmentId)) {
    return problem(res, id, 400, "SEVERITY_INVALID_ASSESSMENT_ID", "Invalid assessment identifier", "assessmentId must be a UUID.");
  }
  if (!validateV2Request(req, res, id, false)) return;
  const ifMatch = req.get("If-Match");
  if (!ifMatch) return problem(res, id, 428, "COMMON_PRECONDITION_REQUIRED", "Precondition required", "If-Match is required for assessment updates.");
  try {
    const current = repository.get(req.params.assessmentId);
    if (!current) return problem(res, id, 404, "SEVERITY_ASSESSMENT_NOT_FOUND", "Assessment not found", "No PANSS assessment has that identifier.");
    if (ifMatch !== etag(current)) return problem(res, id, 412, "COMMON_PRECONDITION_FAILED", "Precondition failed", "Assessment changed after it was read.");
    const assessment = assessmentFromInput(req.body, id, current);
    const result = repository.update({
      assessmentId: current.assessmentId,
      expectedVersion: current.resourceVersion,
      assessment,
      actorId: session.actorId,
      requestId: id
    });
    if (result.missing) return problem(res, id, 404, "SEVERITY_ASSESSMENT_NOT_FOUND", "Assessment not found", "No PANSS assessment has that identifier.");
    if (result.stale) return problem(res, id, 412, "COMMON_PRECONDITION_FAILED", "Precondition failed", "Assessment changed after it was read.");
    setV2Headers(res, id);
    res.setHeader("ETag", etag(result.assessment));
    res.json(result.assessment);
  } catch {
    problem(res, id, 503, "SEVERITY_STORAGE_UNAVAILABLE", "Severity storage unavailable", "Assessment could not be persisted.");
  }
});

app.all("/api/severity/:patientCode", (req, res) => {
  const id = requestId(req);
  problem(res, id, 410, "SEVERITY_LEGACY_IDENTITY_UNMAPPED", "Legacy Severity route unavailable", "Patient-code records cannot be persisted without verified Patient and Encounter UUIDs; use the v2 assessment API.");
});

app.use(express.static(path.join(__dirname, "public")));
app.get("*", (req, res, next) => {
  if (req.path.startsWith("/api/")) return next();
  res.sendFile(path.join(__dirname, "public", "index.html"));
});

const server = app.listen(port, "127.0.0.1", () => {
  console.log(`Severity Module listening on 127.0.0.1:${port}`);
});

function shutdown() {
  server.close(() => {
    repository.close();
    process.exit(0);
  });
}

process.on("SIGTERM", shutdown);
process.on("SIGINT", shutdown);
