import express from "express";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { createHash, randomUUID } from "crypto";
import {
  INTERFACE_VERSION,
  RULE_VERSION,
  SCALE_VERSION,
  SCHEMA_VERSION,
  evaluatePanss,
  isUuid,
  validateAssessmentInput
} from "./panss.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 3000;
const DATA_DIR = path.join(__dirname, "data");
const DATA_FILE = process.env.SEVERITY_DATA_FILE || path.join(DATA_DIR, "assessments.json");
const V2_DATA_FILE = process.env.SEVERITY_V2_DATA_FILE || path.join(DATA_DIR, "assessments-v2.json");
const CONTRACT_DIR = path.join(__dirname, "contracts");

// Ensure data directory and file exist
for (const file of [DATA_FILE, V2_DATA_FILE]) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  if (!fs.existsSync(file)) {
    fs.writeFileSync(file, JSON.stringify(file === DATA_FILE ? {} : { assessments: {}, idempotency: {} }, null, 2));
  }
}

// Middleware
app.use(express.json({
  limit: "1mb"
}));
app.use(express.static(path.join(__dirname, "public")));

// CORS headers for API-first communication with other modules
app.use((req, res, next) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, X-Schema-Version, X-Request-ID, X-Correlation-ID, X-Causation-ID, Idempotency-Key, If-Match");
  res.setHeader("Access-Control-Expose-Headers", "ETag, X-Schema-Version, X-Request-ID");
  if (req.method === "OPTIONS") {
    return res.sendStatus(200);
  }
  next();
});

// Helper to read assessments
function readAssessments() {
  try {
    const data = fs.readFileSync(DATA_FILE, "utf8");
    return JSON.parse(data);
  } catch (error) {
    console.error("Error reading database:", error);
    return {};
  }
}

// Helper to write assessments
function writeAssessments(data) {
  try {
    fs.writeFileSync(DATA_FILE, JSON.stringify(data, null, 2));
    return true;
  } catch (error) {
    console.error("Error writing database:", error);
    return false;
  }
}

function readV2Store() {
  return JSON.parse(fs.readFileSync(V2_DATA_FILE, "utf8"));
}

function writeV2Store(store) {
  fs.writeFileSync(V2_DATA_FILE, JSON.stringify(store, null, 2));
}

function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value !== null && typeof value === "object") {
    return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function pruneIdempotency(store) {
  const cutoff = Date.now() - 86400000;
  for (const [key, record] of Object.entries(store.idempotency)) {
    const createdAt = Date.parse(record.createdAt);
    if (!Number.isFinite(createdAt) || createdAt <= cutoff) delete store.idempotency[key];
  }
}

function etag(assessment) {
  return `"severity-assessment-${assessment.assessmentId}-v${assessment.resourceVersion}"`;
}

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
    res.sendFile(path.join(CONTRACT_DIR, file));
  });
}

app.post("/api/severity/v2/assessments", (req, res) => {
  const id = requestId(req);
  if (!validateV2Request(req, res, id, true)) return;

  const key = req.get("Idempotency-Key");
  if (!key || key.length < 8 || key.length > 128) {
    return problem(res, id, 400, "COMMON_IDEMPOTENCY_KEY_REQUIRED", "Idempotency key required", "Idempotency-Key must contain 8 to 128 characters.");
  }

  const fingerprint = createHash("sha256").update(canonicalJson(req.body)).digest("hex");
  try {
    const store = readV2Store();
    pruneIdempotency(store);
    const activePrior = store.idempotency[key];
    if (activePrior && activePrior.fingerprint !== fingerprint) {
      return problem(res, id, 409, "COMMON_IDEMPOTENCY_KEY_REUSED", "Idempotency key reused", "Idempotency-Key was already used with different input.");
    }
    if (activePrior) {
      const assessment = activePrior.response;
      setV2Headers(res, id);
      res.setHeader("ETag", etag(assessment));
      return res.status(201).json(assessment);
    }

    const assessment = assessmentFromInput(req.body, id);
    store.assessments[assessment.assessmentId] = assessment;
    store.idempotency[key] = { fingerprint, response: assessment, createdAt: new Date().toISOString() };
    writeV2Store(store);
    setV2Headers(res, id);
    res.setHeader("ETag", etag(assessment));
    res.status(201).json(assessment);
  } catch {
    problem(res, id, 503, "SEVERITY_STORAGE_UNAVAILABLE", "Severity storage unavailable", "Assessment could not be persisted.");
  }
});

app.get("/api/severity/v2/assessments/:assessmentId", (req, res) => {
  const id = requestId(req);
  if (!isUuid(req.params.assessmentId)) {
    return problem(res, id, 400, "SEVERITY_INVALID_ASSESSMENT_ID", "Invalid assessment identifier", "assessmentId must be a UUID.");
  }
  try {
    const assessment = readV2Store().assessments[req.params.assessmentId];
    if (!assessment) {
      return problem(res, id, 404, "SEVERITY_ASSESSMENT_NOT_FOUND", "Assessment not found", "No PANSS assessment has that identifier.");
    }
    setV2Headers(res, id);
    res.setHeader("ETag", etag(assessment));
    res.json(assessment);
  } catch {
    problem(res, id, 503, "SEVERITY_STORAGE_UNAVAILABLE", "Severity storage unavailable", "Assessment could not be read.");
  }
});

app.put("/api/severity/v2/assessments/:assessmentId", (req, res) => {
  const id = requestId(req);
  if (!isUuid(req.params.assessmentId)) {
    return problem(res, id, 400, "SEVERITY_INVALID_ASSESSMENT_ID", "Invalid assessment identifier", "assessmentId must be a UUID.");
  }
  if (!validateV2Request(req, res, id, false)) return;
  const ifMatch = req.get("If-Match");
  if (!ifMatch) {
    return problem(res, id, 428, "COMMON_PRECONDITION_REQUIRED", "Precondition required", "If-Match is required for assessment updates.");
  }

  try {
    const store = readV2Store();
    const current = store.assessments[req.params.assessmentId];
    if (!current) {
      return problem(res, id, 404, "SEVERITY_ASSESSMENT_NOT_FOUND", "Assessment not found", "No PANSS assessment has that identifier.");
    }
    if (ifMatch !== etag(current)) {
      return problem(res, id, 412, "COMMON_PRECONDITION_FAILED", "Precondition failed", "Assessment changed after it was read.");
    }

    const assessment = assessmentFromInput(req.body, id, current);
    store.assessments[assessment.assessmentId] = assessment;
    writeV2Store(store);
    setV2Headers(res, id);
    res.setHeader("ETag", etag(assessment));
    res.json(assessment);
  } catch {
    problem(res, id, 503, "SEVERITY_STORAGE_UNAVAILABLE", "Severity storage unavailable", "Assessment could not be persisted.");
  }
});

// GET api/severity/:patient_code
app.get("/api/severity/:patient_code", (req, res) => {
  const { patient_code } = req.params;
  if (!patient_code || patient_code.trim() === "") {
    return res.status(400).json({ error: "Patient code is required" });
  }

  const assessments = readAssessments();
  const assessment = assessments[patient_code];

  if (assessment) {
    return res.json(assessment);
  } else {
    // Return empty initial state for new patient evaluation
    const evaluation = evaluatePanss("incomplete", {});
    return res.json({
      patient_code,
      status: "pending",
      items: {},
      scores: {
        total: 0,
        positive: 0,
        negative: 0,
        general: 0
      },
      evaluation: {
        state: evaluation.state,
        missingItemCodes: evaluation.missingItemCodes,
        scores: evaluation.scores,
        scaleVersion: evaluation.scaleVersion,
        ruleVersion: evaluation.ruleVersion
      }
    });
  }
});

// PUT api/severity/:patient_code
app.put("/api/severity/:patient_code", (req, res) => {
  const { patient_code } = req.params;
  const { status, scores, items } = req.body || {};

  if (!patient_code || patient_code.trim() === "") {
    return res.status(400).json({ error: "Patient code is required" });
  }

  if (!status || !["completed", "passed"].includes(status)) {
    return res.status(400).json({ error: "Status must be 'completed' or 'passed'" });
  }

  const assessments = readAssessments();
  const evaluation = evaluatePanss(
    status === "passed" ? "passed" : "completed",
    status === "passed" ? {} : items,
    status === "passed" ? undefined : scores
  );
  if (!evaluation.valid) {
    return res.status(400).json({ error: evaluation.detail, code: evaluation.code });
  }

  if (status === "passed") {
    assessments[patient_code] = {
      patient_code,
      status: "passed",
      evaluation: {
        state: evaluation.state,
        missingItemCodes: evaluation.missingItemCodes,
        scores: evaluation.scores,
        scaleVersion: evaluation.scaleVersion,
        ruleVersion: evaluation.ruleVersion
      },
      updated_at: new Date().toISOString()
    };
  } else {
    assessments[patient_code] = {
      patient_code,
      status: "completed",
      scores: evaluation.scores,
      items,
      evaluation: {
        state: evaluation.state,
        missingItemCodes: evaluation.missingItemCodes,
        scores: evaluation.scores,
        scaleVersion: evaluation.scaleVersion,
        ruleVersion: evaluation.ruleVersion
      },
      updated_at: new Date().toISOString()
    };
  }

  if (writeAssessments(assessments)) {
    return res.json({ success: true, data: assessments[patient_code] });
  } else {
    return res.status(500).json({ error: "Failed to write to database" });
  }
});

// Fallback to SPA index.html for all other routes to allow standalone client-side routing if needed
app.get("*", (req, res, next) => {
  // If requesting api, let it 404
  if (req.path.startsWith("/api/")) {
    return next();
  }
  res.sendFile(path.join(__dirname, "public", "index.html"));
});

app.listen(PORT, () => {
  console.log(`====================================================`);
  console.log(` Severity Module is running as a Standalone Web App`);
  console.log(` URL: http://localhost:${PORT}`);
  console.log(` GET API: http://localhost:${PORT}/api/severity/:patient_code`);
  console.log(` PUT API: http://localhost:${PORT}/api/severity/:patient_code`);
  console.log(`====================================================`);
});
