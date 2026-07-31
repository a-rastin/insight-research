import { createHash, createHmac, randomUUID, timingSafeEqual } from "node:crypto";
import { createReadStream, existsSync, readFileSync } from "node:fs";
import { createServer } from "node:http";
import { createRequire } from "node:module";
import { extname, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { validateKnowledgeBase } from "../Modules/DDI-Checker-1.2.0/scripts/validate-kb.mjs";

const require = createRequire(import.meta.url);
const API_PREFIX = "/api/ddi/v1";
const SCHEMA_VERSION = "1.0.0";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const SHA256 = /^sha256:[a-f0-9]{64}$/;
const SEMVER = /^\d+\.\d+\.\d+$/;
const BODY_LIMIT = 1024 * 1024;
const TYPES = { ".css": "text/css", ".html": "text/html", ".js": "text/javascript", ".json": "application/json" };

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function stableJson(value) {
  if (Array.isArray(value)) return `[${value.map(stableJson).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stableJson(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function medicationSetHash(medications) {
  const canonical = medications
    .map(({ inputIndex: _inputIndex, ...medication }) => medication)
    .sort((left, right) => stableJson(left).localeCompare(stableJson(right)));
  return `sha256:${sha256(stableJson({ schemaVersion: SCHEMA_VERSION, medications: canonical }))}`;
}

function problem(response, status, code, detail, requestId) {
  return sendJson(response, status, {
    type: `https://insight.invalid/problems/${code.toLowerCase().replaceAll("_", "-")}`,
    title: detail,
    status,
    code,
    requestId,
  }, requestId);
}

function sendJson(response, status, body, requestId, headers = {}) {
  const bytes = Buffer.from(JSON.stringify(body));
  response.writeHead(status, {
    "Content-Type": "application/json",
    "Cache-Control": "no-store",
    "Content-Length": bytes.length,
    ...(requestId ? { "X-Request-ID": requestId } : {}),
    ...headers,
  });
  response.end(bytes);
}

function validateRequest(body, idempotencyKey) {
  const errors = [];
  const object = body && typeof body === "object" && !Array.isArray(body);
  if (!object) return ["body must be an object"];
  const allowed = new Set(["schemaVersion", "idempotencyKey", "planSemanticHash", "medicationSetHash", "medications"]);
  for (const key of Object.keys(body)) if (!allowed.has(key)) errors.push(`unsupported field: ${key}`);
  for (const key of ["idempotencyKey", "planSemanticHash", "medicationSetHash"]) {
    if (!SHA256.test(body[key] || "")) errors.push(`${key} must be a sha256 digest`);
  }
  if (body.idempotencyKey !== idempotencyKey) errors.push("Idempotency-Key must match idempotencyKey");
  if (!Array.isArray(body.medications) || body.medications.length < 1 || body.medications.length > 100) {
    errors.push("medications must contain 1 to 100 items");
    return errors;
  }
  const indexes = new Set();
  const medicationFields = new Set(["inputIndex", "source", "originalText", "medicationCode", "codeSystem", "dose", "route", "frequency"]);
  body.medications.forEach((medication, position) => {
    if (!medication || typeof medication !== "object" || Array.isArray(medication)) {
      errors.push(`medications[${position}] must be an object`);
      return;
    }
    for (const key of Object.keys(medication)) if (!medicationFields.has(key)) errors.push(`medications[${position}] has unsupported field: ${key}`);
    if (!Number.isInteger(medication.inputIndex) || medication.inputIndex < 0 || indexes.has(medication.inputIndex)) {
      errors.push(`medications[${position}].inputIndex must be a unique non-negative integer`);
    }
    indexes.add(medication.inputIndex);
    if (!new Set(["current", "proposed"]).has(medication.source)) errors.push(`medications[${position}].source is invalid`);
    if (typeof medication.originalText !== "string" || !medication.originalText.trim() || medication.originalText.length > 500) {
      errors.push(`medications[${position}].originalText is invalid`);
    }
    for (const key of ["medicationCode", "codeSystem", "dose", "route", "frequency"]) {
      if (key in medication && (typeof medication[key] !== "string" || !medication[key].trim())) errors.push(`medications[${position}].${key} is invalid`);
    }
  });
  if (body.medicationSetHash !== medicationSetHash(body.medications)) errors.push("medicationSetHash does not match medications");
  return errors;
}

function clinicalKnowledge(root, registryRoot) {
  const file = resolve(registryRoot, "active-kb.json");
  try {
    const bytes = readFileSync(file);
    const knowledgeBase = JSON.parse(bytes.toString("utf8"));
    const errors = validateKnowledgeBase(knowledgeBase, { clinicalActive: true });
    if (!UUID.test(knowledgeBase.knowledgeBaseId || "")) errors.push("root.knowledgeBaseId must be a UUID");
    if (!SEMVER.test(knowledgeBase.version || "")) errors.push("root.version must be semantic version metadata");
    if (errors.length) return { ready: false, reason: "active-knowledge-base-invalid" };
    const engine = require(resolve(root, "src", "ddi-engine.js"));
    return {
      ready: true,
      knowledgeBase,
      index: engine.buildIndex({
        ...knowledgeBase,
        drugs: knowledgeBase.drugs.filter((drug) => drug.identityStatus === "rxnorm_seeded"),
      }),
      contentHash: `sha256:${sha256(bytes)}`,
      engine,
    };
  } catch {
    return { ready: false, reason: "active-knowledge-base-unavailable" };
  }
}

function uuidFrom(value) {
  const hex = sha256(value).slice(0, 32).split("");
  hex[12] = "4";
  hex[16] = ((parseInt(hex[16], 16) & 3) | 8).toString(16);
  return `${hex.slice(0, 8).join("")}-${hex.slice(8, 12).join("")}-${hex.slice(12, 16).join("")}-${hex.slice(16, 20).join("")}-${hex.slice(20).join("")}`;
}

function codeSystem(drug, requested) {
  if (requested) return requested;
  return String(drug.id).toLowerCase().startsWith("rxnorm:") ? "RxNorm" : "INSIGHT-DDI";
}

function resolveMedication(medication, clinical) {
  let resolution;
  if (medication.medicationCode) {
    const code = medication.medicationCode.trim().toLowerCase();
    const ids = [code];
    if (String(medication.codeSystem || "").toLowerCase().includes("rxnorm")) ids.push(`rxnorm:${code}`);
    const matches = new Map();
    for (const id of ids) {
      const drug = clinical.index.byId.get(id);
      if (drug) matches.set(String(drug.id).toLowerCase(), drug);
    }
    for (const drug of clinical.index.byId.values()) {
      if (String(drug.rxcui || "").toLowerCase() === code) matches.set(String(drug.id).toLowerCase(), drug);
    }
    const candidates = [...matches.values()];
    resolution = candidates.length === 1 ? { status: "resolved", drug: candidates[0] }
      : candidates.length > 1 ? { status: "ambiguous", candidates } : { status: "unknown" };
  } else {
    resolution = clinical.engine.resolveDrug({ name: medication.originalText }, clinical.index);
  }
  if (resolution.status === "resolved") {
    return {
      inputIndex: medication.inputIndex,
      status: "resolved",
      originalText: medication.originalText,
      conceptId: resolution.drug.id,
      codeSystem: codeSystem(resolution.drug, medication.codeSystem),
      display: resolution.drug.name,
      drug: resolution.drug,
    };
  }
  const candidates = (resolution.candidates || []).map((drug) => ({
    conceptId: drug.id,
    codeSystem: codeSystem(drug),
    display: drug.name,
  }));
  return {
    inputIndex: medication.inputIndex,
    status: candidates.length ? "ambiguous" : "unknown",
    originalText: medication.originalText,
    reason: candidates.length ? "multiple-active-concept-matches" : "no-active-concept-match",
    candidates,
  };
}

function check(body, clinical) {
  const checkId = randomUUID();
  const identities = body.medications.map((medication) => resolveMedication(medication, clinical));
  const resolved = identities.filter((item) => item.status === "resolved");
  const unresolved = identities.filter((item) => item.status !== "resolved");
  const pairsChecked = [];
  const alerts = [];
  for (let left = 0; left < resolved.length; left += 1) {
    for (let right = left + 1; right < resolved.length; right += 1) {
      const a = resolved[left];
      const b = resolved[right];
      const indexes = [a.inputIndex, b.inputIndex].sort((x, y) => x - y);
      pairsChecked.push({ medicationInputIndexes: indexes });
      const records = clinical.index.interactionsByPair.get(clinical.engine.pairKey(a.drug.id, b.drug.id)) || [];
      records.forEach((record) => alerts.push({
        alertId: uuidFrom(`${checkId}\n${record.id}\n${indexes.join(":")}`),
        medicationInputIndexes: indexes,
        severity: ({ major: "high", minor: "low" })[record.severity] || record.severity || "unknown",
        ...(record.mechanism ? { mechanism: record.mechanism } : {}),
        recommendedAction: record.recommendation || "Review interaction and document clinical plan.",
        evidence: [{
          sourceId: record.evidenceSource || record.sourceReportPath || "DDI knowledge base",
          sourceVersion: record.knowledgeBaseVersion || clinical.knowledgeBase.version,
          summary: record.evidenceExcerpt || record.clinicalEffect || record.mechanism || "Approved interaction record.",
        }],
      }));
    }
  }
  return {
    schemaVersion: SCHEMA_VERSION,
    checkId,
    medicationSetHash: body.medicationSetHash,
    knowledgeBaseId: clinical.knowledgeBase.knowledgeBaseId,
    knowledgeBaseVersion: clinical.knowledgeBase.version,
    knowledgeBaseContentHash: clinical.contentHash,
    coverageStatus: unresolved.length ? "incomplete" : "complete",
    resolvedMedications: resolved.map(({ drug: _drug, ...identity }) => identity),
    unresolvedMedications: unresolved,
    pairsChecked,
    alerts,
    checkedAt: new Date().toISOString(),
  };
}

function readBody(request) {
  return new Promise((resolveBody, reject) => {
    const chunks = [];
    let length = 0;
    request.on("data", (chunk) => {
      length += chunk.length;
      if (length > BODY_LIMIT) {
        reject(Object.assign(new Error("body-too-large"), { status: 413 }));
        request.destroy();
      } else chunks.push(chunk);
    });
    request.on("end", () => resolveBody(Buffer.concat(chunks)));
    request.on("error", reject);
  });
}

function serviceAuthorized(request, bodyBytes, config, nonces) {
  const fields = {
    serviceId: request.headers["x-insight-service-id"],
    keyId: request.headers["x-insight-key-id"],
    timestamp: request.headers["x-insight-timestamp"],
    nonce: request.headers["x-insight-nonce"],
    contentHash: request.headers["x-insight-content-sha256"],
    signature: request.headers["x-insight-signature"],
    requestId: request.headers["x-request-id"],
    correlationId: request.headers["x-correlation-id"],
    causationId: request.headers["x-causation-id"] || "",
  };
  const now = Date.now();
  for (const [nonce, recordedAt] of nonces) if (now - recordedAt > 300_000) nonces.delete(nonce);
  if (fields.serviceId !== config.serviceId || fields.keyId !== config.keyId || !UUID.test(fields.requestId || "") || !UUID.test(fields.correlationId || "")) return false;
  if (fields.causationId && !UUID.test(fields.causationId)) return false;
  if (!/^\d{10}$/.test(fields.timestamp || "") || !/^[a-f0-9]{32,}$/i.test(fields.nonce || "") || Math.abs(now / 1000 - Number(fields.timestamp)) > 60) return false;
  if (fields.contentHash !== sha256(bodyBytes) || nonces.has(fields.nonce)) return false;
  if (Object.values(fields).some((value) => /[\r\n]/.test(String(value)))) return false;
  const canonical = ["INSIGHT-HMAC-V1", fields.serviceId, fields.keyId, fields.timestamp, fields.nonce,
    "ddi-checker", request.method, request.url, fields.contentHash, fields.requestId, fields.correlationId, fields.causationId].join("\n");
  const expected = `v1=${createHmac("sha256", config.secret).update(canonical).digest("base64url")}`;
  const valid = fields.signature?.length === expected.length && timingSafeEqual(Buffer.from(fields.signature), Buffer.from(expected));
  if (valid) nonces.set(fields.nonce, now);
  return valid;
}

async function currentPsychiatrist(request, config) {
  const cookie = String(request.headers.cookie || "").split(";")
    .map((item) => item.trim()).find((item) => item.startsWith(`${config.sessionCookieName}=`));
  if (!cookie) return { status: 401 };
  try {
    const response = await fetch(config.authSessionUrl, { headers: { Accept: "application/json", Cookie: cookie }, redirect: "error" });
    if (response.status === 401) return { status: 401 };
    if (!response.ok) return { status: 503 };
    const session = await response.json();
    if (response.headers.get("x-schema-version") !== "2.0.0" || session?.interfaceVersion !== "2.0.0" ||
      session?.authenticated !== true || session?.session?.active !== true || !UUID.test(session?.session?.id || "") ||
      !UUID.test(session?.user?.id || "") || typeof session?.gates?.passwordChangeRequired !== "boolean" ||
      typeof session?.gates?.disclaimerRequired !== "boolean") return { status: 503 };
    if (session.authorized !== true || session.gates.passwordChangeRequired || session.gates.disclaimerRequired) return { status: 401 };
    if (session?.user?.role !== "psychiatrist") return { status: 403 };
    return { status: 200 };
  } catch {
    return { status: 503 };
  }
}

async function authenticationOperational(config) {
  try {
    const response = await fetch(config.authSessionUrl, {
      headers: { Accept: "application/json" },
      redirect: "error",
      signal: AbortSignal.timeout(1000),
    });
    return response.status === 401;
  } catch {
    return false;
  }
}

export function createDdiServer(options = {}) {
  const root = resolve(options.root || process.env.DDI_ROOT || "/opt/insight/Modules/DDI-Checker-1.2.0");
  const registryRoot = resolve(options.registryRoot || process.env.DDI_REGISTRY_ROOT || resolve(root, "data"));
  const config = {
    authSessionUrl: options.authSessionUrl || process.env.DDI_AUTH_SESSION_URL || "",
    sessionCookieName: options.sessionCookieName || process.env.DDI_AUTH_SESSION_COOKIE || "insight_session",
    serviceId: options.serviceId || process.env.DDI_CALLER_SERVICE_ID || "treatment-plan",
    keyId: options.keyId || process.env.DDI_SERVICE_AUTH_KEY_ID || "",
    secret: options.secret || process.env.DDI_SERVICE_AUTH_SECRET || "",
  };
  const clinical = clinicalKnowledge(root, registryRoot);
  const configured = Boolean(config.authSessionUrl && config.keyId && config.secret.length >= 32);
  const idempotency = new Map();
  const nonces = new Map();

  return createServer(async (request, response) => {
    const requestId = UUID.test(request.headers["x-request-id"] || "") ? request.headers["x-request-id"] : randomUUID();
    const pathname = new URL(request.url, "http://module.local").pathname;
    if (request.method === "GET" && pathname === "/healthz") return sendJson(response, 200, { status: "live", module: "ddi-checker" }, requestId);
    if (request.method === "GET" && pathname === "/readyz") {
      if (!configured) return sendJson(response, 503, { status: "not-ready", module: "ddi-checker", reason: "production-security-unavailable" }, requestId);
      if (!clinical.ready) return sendJson(response, 503, { status: "not-ready", module: "ddi-checker", reason: clinical.reason }, requestId);
      if (!await authenticationOperational(config)) return sendJson(response, 503, { status: "not-ready", module: "ddi-checker", reason: "authentication-unavailable" }, requestId);
      return sendJson(response, 200, {
        status: "ready", module: "ddi-checker", schemaVersion: SCHEMA_VERSION,
        knowledgeBaseVersion: clinical.knowledgeBase.version, knowledgeBaseContentHash: clinical.contentHash,
      }, requestId, { "X-Schema-Version": SCHEMA_VERSION });
    }
    if (request.method === "GET" && pathname === `${API_PREFIX}/contract`) {
      return sendJson(response, 200, {
        contractId: "insight.ddi", interfaceVersion: SCHEMA_VERSION, schemaVersion: SCHEMA_VERSION,
        artifacts: { document: `${API_PREFIX}/contract/document`, schema: `${API_PREFIX}/contract/schema`, openapi: `${API_PREFIX}/contract/openapi` },
      }, requestId, { "X-Schema-Version": SCHEMA_VERSION });
    }
    const artifacts = { document: "ddi-v1.contract.json", schema: "ddi-v1.schema.json", openapi: "openapi-v1.json" };
    const artifact = Object.entries(artifacts).find(([name]) => request.method === "GET" && pathname === `${API_PREFIX}/contract/${name}`);
    if (artifact) {
      const file = resolve(root, "contracts", artifact[1]);
      if (!existsSync(file)) return problem(response, 404, "DDI_NOT_FOUND", "Contract artifact not found", requestId);
      response.writeHead(200, { "Content-Type": "application/json", "Cache-Control": "no-store", "X-Request-ID": requestId, "X-Schema-Version": SCHEMA_VERSION });
      return createReadStream(file).pipe(response);
    }
    if (pathname === `${API_PREFIX}/checks`) {
      if (request.method !== "POST") return problem(response, 405, "DDI_METHOD_NOT_ALLOWED", "Method not allowed", requestId);
      if (!String(request.headers["content-type"] || "").toLowerCase().startsWith("application/json")) return problem(response, 415, "DDI_SCHEMA_INVALID", "Content-Type must be application/json", requestId);
      let bodyBytes;
      try { bodyBytes = await readBody(request); }
      catch (error) { return problem(response, error.status || 400, "DDI_SCHEMA_INVALID", "Request body is invalid", requestId); }
      if (!configured || !serviceAuthorized(request, bodyBytes, config, nonces)) return problem(response, 401, "DDI_UNAUTHENTICATED", "Valid service authentication is required", requestId);
      const session = await currentPsychiatrist(request, config);
      if (session.status !== 200) return problem(response, session.status, session.status === 403 ? "DDI_FORBIDDEN" : "DDI_UNAUTHENTICATED", session.status === 503 ? "Authentication service unavailable" : "Current psychiatrist authorization is required", requestId);
      if (request.headers["x-schema-version"] !== SCHEMA_VERSION) return problem(response, 400, "DDI_SCHEMA_INVALID", "Unsupported schema version", requestId);
      const idempotencyKey = request.headers["idempotency-key"];
      if (!SHA256.test(idempotencyKey || "")) return problem(response, 422, "DDI_SCHEMA_INVALID", "Idempotency-Key is invalid", requestId);
      let body;
      try { body = JSON.parse(bodyBytes.toString("utf8")); }
      catch { return problem(response, 422, "DDI_SCHEMA_INVALID", "Request body is not valid JSON", requestId); }
      if (body?.schemaVersion !== SCHEMA_VERSION) return problem(response, 400, "DDI_SCHEMA_INVALID", "Unsupported schema version", requestId);
      const errors = validateRequest(body, idempotencyKey);
      if (errors.length) {
        const code = errors.includes("medicationSetHash does not match medications") ? "DDI_MEDICATION_SET_HASH_MISMATCH" : "DDI_SCHEMA_INVALID";
        return problem(response, 422, code, errors.join("; "), requestId);
      }
      if (!clinical.ready) return problem(response, 503, "DDI_NO_ACTIVE_KNOWLEDGE_REVISION", "No valid active reviewed knowledge revision", requestId);
      const fingerprint = sha256(stableJson(body));
      const prior = idempotency.get(idempotencyKey);
      if (prior && prior.fingerprint !== fingerprint) return problem(response, 409, "DDI_IDEMPOTENCY_KEY_REUSED", "Idempotency key was used for different input", requestId);
      const result = prior?.result || check(body, clinical);
      if (!prior) idempotency.set(idempotencyKey, { fingerprint, result });
      return sendJson(response, 201, result, requestId, { "X-Schema-Version": SCHEMA_VERSION });
    }
    if (request.method !== "GET") return problem(response, 405, "DDI_METHOD_NOT_ALLOWED", "Method not allowed", requestId);

    const relative = pathname === "/" ? "index.html" : decodeURIComponent(pathname.slice(1));
    const registryFile = /^data\/active-kb\.(js|json)$/.test(relative);
    const file = registryFile ? resolve(registryRoot, relative.slice(5)) : resolve(root, relative);
    const base = registryFile ? registryRoot : root;
    const allowed = file.startsWith(`${base}${sep}`) && /^(index\.html|src\/[\w.-]+\.(css|js)|data\/active-kb\.(js|json))$/.test(relative);
    if (!allowed || !existsSync(file)) return problem(response, 404, "DDI_NOT_FOUND", "Resource not found", requestId);
    response.writeHead(200, { "Content-Type": TYPES[extname(file)] || "application/octet-stream", "Cache-Control": "no-store", "X-Request-ID": requestId });
    createReadStream(file).pipe(response);
  });
}

if (process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1])) {
  const server = createDdiServer();
  server.listen(Number(process.env.PORT || 8107), "127.0.0.1");
  const stop = () => server.close(() => process.exit(0));
  process.on("SIGTERM", stop);
  process.on("SIGINT", stop);
}
