const http = require("http");
const fs = require("fs/promises");
const path = require("path");
const crypto = require("crypto");

const PORT = Number(process.env.PORT || 4173);
const ROOT_DIR = __dirname;
const PUBLIC_DIR = path.join(ROOT_DIR, "public");
const DATA_DIR = process.env.MEDICAL_HISTORY_DATA_DIR || path.join(ROOT_DIR, "data");
const SESSIONS_FILE = path.join(DATA_DIR, "activation_sessions.json");
const SUBMISSIONS_FILE = path.join(DATA_DIR, "medical_history_submissions.json");
const SCHEMA_FILE = path.join(DATA_DIR, "medical_history_schema.json");
const V2_FILE = process.env.MEDICAL_HISTORY_V2_DATA_FILE || path.join(DATA_DIR, "medical_history_assessments_v2.json");
const CONTRACTS_DIR = path.join(ROOT_DIR, "contracts");
const INTERFACE_VERSION = "2.0.0";
const SCHEMA_VERSION = "2.0.0";
const MODULE_VERSION = "1.0.0";
const CLINICAL_STATES = ["yes", "no", "unknown", "not-assessed"];
const ASSESSMENT_STATUSES = ["in-progress", "completed", "not-assessed"];
const NORMALIZATION_STATES = ["matched", "unresolved", "ambiguous", "not-assessed"];

const COMORBIDITY_OPTIONS = [
  "Diabetes mellitus",
  "Hypertension",
  "Coronary artery disease",
  "Heart failure",
  "Chronic obstructive pulmonary disease",
  "Asthma",
  "Chronic kidney disease",
  "Stroke or TIA",
  "Cancer",
  "Depression",
  "Anxiety disorder",
  "Other"
];

const ANTIPSYCHOTIC_OPTIONS = ["Aripiprazole", "Asenapine", "Brexpiprazole", "Cariprazine", "Chlorpromazine", "Clozapine", "Fluphenazine", "Haloperidol", "Iloperidone", "Lurasidone", "Olanzapine", "Paliperidone", "Perphenazine", "Quetiapine", "Risperidone", "Ziprasidone"];
const CLOZAPINE_CONTRAINDICATION_OPTIONS = ["Severe neutropenia", "Clozapine-induced myocarditis", "Unmanaged seizure disorder"];

const MIME_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon"
};

function isValidCode(code) {
  return typeof code === "string" && /^[A-Za-z0-9]{6}$/.test(code.trim());
}

function normalizeCode(code) {
  return String(code || "").trim().toUpperCase();
}

async function ensureDataFiles() {
  await fs.mkdir(DATA_DIR, { recursive: true });
  await ensureJsonFile(SESSIONS_FILE, []);
  await ensureJsonFile(SUBMISSIONS_FILE, []);
  await ensureJsonFile(V2_FILE, { assessments: {}, idempotency: {} });
}

async function ensureJsonFile(filePath, defaultValue) {
  try {
    await fs.access(filePath);
  } catch {
    await fs.writeFile(filePath, JSON.stringify(defaultValue, null, 2));
  }
}

async function readJson(filePath, fallback) {
  try {
    const raw = await fs.readFile(filePath, "utf8");
    return JSON.parse(raw || "null") ?? fallback;
  } catch (error) {
    if (error.code === "ENOENT") return fallback;
    throw error;
  }
}

async function writeJson(filePath, value) {
  await fs.writeFile(filePath, `${JSON.stringify(value, null, 2)}\n`);
}

async function parseBody(req) {
  return new Promise((resolve, reject) => {
    let raw = "";
    req.on("data", (chunk) => {
      raw += chunk;
      if (raw.length > 1_000_000) {
        reject(Object.assign(new Error("Request body too large"), { status: 413 }));
        req.destroy();
      }
    });
    req.on("end", () => {
      if (!raw) {
        resolve({});
        return;
      }
      try {
        resolve(JSON.parse(raw));
      } catch {
        reject(Object.assign(new Error("Invalid JSON body"), { status: 400 }));
      }
    });
    req.on("error", reject);
  });
}

function sendJson(res, status, payload, headers = {}) {
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,PUT,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, X-Schema-Version, X-Request-ID, X-Correlation-ID, X-Causation-ID, Idempotency-Key, If-Match",
    "Access-Control-Expose-Headers": "ETag, X-Schema-Version, X-Request-ID, X-Correlation-ID",
    ...headers
  });
  res.end(JSON.stringify(payload, null, 2));
}

function isUuid(value) {
  return typeof value === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(value);
}

function requestContext(req) {
  return {
    requestId: isUuid(req.headers["x-request-id"]) ? req.headers["x-request-id"] : crypto.randomUUID(),
    correlationId: isUuid(req.headers["x-correlation-id"]) ? req.headers["x-correlation-id"] : null
  };
}

function sendV2(res, status, payload, context, headers = {}) {
  sendJson(res, status, payload, {
    "X-Schema-Version": SCHEMA_VERSION,
    "X-Request-ID": context.requestId,
    "X-Correlation-ID": context.correlationId || context.requestId,
    ...headers
  });
}

function sendProblem(res, context, status, code, title, detail, errors) {
  const payload = {
    type: `urn:insight:problem:${code.toLowerCase().replaceAll("_", "-")}`,
    title,
    status,
    code,
    detail,
    requestId: context.requestId
  };
  if (errors?.length) payload.errors = errors.map((message) => ({ code, message }));
  sendJson(res, status, payload, {
    "Content-Type": "application/problem+json",
    "X-Schema-Version": SCHEMA_VERSION,
    "X-Request-ID": context.requestId,
    "X-Correlation-ID": context.correlationId || context.requestId
  });
}

function requireV2Schema(req, res, context) {
  if (req.headers["x-schema-version"] !== SCHEMA_VERSION) {
    sendProblem(res, context, 400, "COMMON_UNSUPPORTED_SCHEMA_MAJOR", "Unsupported schema version", "X-Schema-Version must be 2.0.0.");
    return false;
  }
  return true;
}

function assessmentEtag(assessment) {
  return `"medical-history-assessment-${assessment.assessmentId}-v${assessment.resourceVersion}"`;
}

function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value !== null && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function hasExactKeys(value, required, allowed, label, errors) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    errors.push(`${label} must be an object`);
    return false;
  }
  required.filter((key) => !Object.hasOwn(value, key)).forEach((key) => errors.push(`${label}.${key} is required`));
  Object.keys(value).filter((key) => !allowed.includes(key)).forEach((key) => errors.push(`${label}.${key} is not allowed`));
  return true;
}

function validNullableString(value, maximum) {
  return value === null || (typeof value === "string" && value.length <= maximum);
}

function pruneIdempotency(store) {
  const cutoff = Date.now() - 86400000;
  for (const [key, record] of Object.entries(store.idempotency)) {
    const createdAt = Date.parse(record.createdAt);
    if (!Number.isFinite(createdAt) || createdAt <= cutoff) delete store.idempotency[key];
  }
}

function validateV2Write(body, creating) {
  const errors = [];
  const required = creating
    ? ["patientId", "encounterId", "status", "pastMedicalHistory", "medications", "substantialSuicideRisk", "priorAntipsychoticTherapy", "priorAntipsychoticTherapySuccessful", "antipsychotic", "clozapineContraindication", "clozapineContraindications", "recurrentNonAdherenceDeterioration", "actor"]
    : ["status", "pastMedicalHistory", "medications", "substantialSuicideRisk", "priorAntipsychoticTherapy", "priorAntipsychoticTherapySuccessful", "antipsychotic", "clozapineContraindication", "clozapineContraindications", "recurrentNonAdherenceDeterioration", "actor"];
  const allowed = creating
    ? ["patientId", "encounterId", "status", "pastMedicalHistory", "medications", "substantialSuicideRisk", "priorAntipsychoticTherapy", "priorAntipsychoticTherapySuccessful", "antipsychotic", "clozapineContraindication", "clozapineContraindications", "recurrentNonAdherenceDeterioration", "actor"]
    : ["status", "pastMedicalHistory", "medications", "substantialSuicideRisk", "priorAntipsychoticTherapy", "priorAntipsychoticTherapySuccessful", "antipsychotic", "clozapineContraindication", "clozapineContraindications", "recurrentNonAdherenceDeterioration", "actor"];
  if (!hasExactKeys(body, required, allowed, "assessment", errors)) return errors;
  if (creating && !isUuid(body.patientId)) errors.push("patientId must be a UUID");
  if (creating && !isUuid(body.encounterId)) errors.push("encounterId must be a UUID");
  if (!ASSESSMENT_STATUSES.includes(body.status)) errors.push("status must be in-progress, completed, or not-assessed");
  if (!Array.isArray(body.pastMedicalHistory) || body.pastMedicalHistory.some((value) => !COMORBIDITY_OPTIONS.includes(value))) {
    errors.push("pastMedicalHistory must contain only supported options");
  } else if (new Set(body.pastMedicalHistory).size !== body.pastMedicalHistory.length) {
    errors.push("pastMedicalHistory must contain unique options");
  }
  if (!Array.isArray(body.medications) || body.medications.length > 20) {
    errors.push("medications must be an array with no more than 20 entries");
  } else {
    body.medications.forEach((medication, index) => {
      const label = `medications[${index}]`;
      const medicationKeys = ["originalText", "doseText", "routeText", "frequencyText", "normalizedIdentity"];
      if (!hasExactKeys(medication, medicationKeys, medicationKeys, label, errors)) return;
      if (typeof medication.originalText !== "string" || !medication.originalText.trim() || medication.originalText.length > 500) errors.push(`${label}.originalText must be a non-empty string of at most 500 characters`);
      if (!validNullableString(medication.doseText, 160)) errors.push(`${label}.doseText must be null or a string of at most 160 characters`);
      if (!validNullableString(medication.routeText, 160)) errors.push(`${label}.routeText must be null or a string of at most 160 characters`);
      if (!validNullableString(medication.frequencyText, 160)) errors.push(`${label}.frequencyText must be null or a string of at most 160 characters`);
      const normalized = medication?.normalizedIdentity;
      const identityKeys = ["state", "conceptId", "display", "terminologyVersion"];
      if (!hasExactKeys(normalized, identityKeys, identityKeys, `${label}.normalizedIdentity`, errors)) return;
      if (!NORMALIZATION_STATES.includes(normalized.state)) errors.push(`${label}.normalizedIdentity.state is invalid`);
      if (!validNullableString(normalized.conceptId, 120) || !validNullableString(normalized.display, 300) || !validNullableString(normalized.terminologyVersion, 120)) errors.push(`${label}.normalizedIdentity contains an invalid identifier`);
      if (normalized.state === "matched" && (typeof normalized.conceptId !== "string" || normalized.conceptId.length === 0 || typeof normalized.display !== "string" || normalized.display.length === 0)) errors.push(`${label}.normalizedIdentity requires conceptId and display when matched`);
      if (normalized.state !== "matched" && (normalized.conceptId !== null || normalized.display !== null || normalized.terminologyVersion !== null)) errors.push(`${label}.normalizedIdentity identifiers must be null unless matched`);
    });
  }
  ["substantialSuicideRisk", "priorAntipsychoticTherapy", "priorAntipsychoticTherapySuccessful", "clozapineContraindication", "recurrentNonAdherenceDeterioration"].forEach((field) => {
    if (!CLINICAL_STATES.includes(body[field])) errors.push(`${field} must be yes, no, unknown, or not-assessed`);
  });
  if (body.priorAntipsychoticTherapy === "yes") {
    if (!ANTIPSYCHOTIC_OPTIONS.includes(body.antipsychotic)) errors.push("antipsychotic must be a supported option when priorAntipsychoticTherapy is yes");
  } else if (body.antipsychotic !== null) {
    errors.push("antipsychotic must be null unless priorAntipsychoticTherapy is yes");
  }
  if (body.priorAntipsychoticTherapy !== "yes" && body.priorAntipsychoticTherapySuccessful !== "not-assessed") errors.push("priorAntipsychoticTherapySuccessful must be not-assessed unless priorAntipsychoticTherapy is yes");
  if (!Array.isArray(body.clozapineContraindications) || body.clozapineContraindications.some((value) => !CLOZAPINE_CONTRAINDICATION_OPTIONS.includes(value))) {
    errors.push("clozapineContraindications must contain only supported options");
  } else if (new Set(body.clozapineContraindications).size !== body.clozapineContraindications.length) {
    errors.push("clozapineContraindications must contain unique options");
  } else if (body.clozapineContraindication === "yes" && body.clozapineContraindications.length === 0) {
    errors.push("at least one clozapine contraindication is required when clozapineContraindication is yes");
  } else if (body.clozapineContraindication !== "yes" && body.clozapineContraindications.length > 0) {
    errors.push("clozapineContraindications must be empty unless clozapineContraindication is yes");
  }
  if (hasExactKeys(body.actor, ["actorId", "role"], ["actorId", "role"], "actor", errors) && (!isUuid(body.actor.actorId) || body.actor.role !== "psychiatrist")) errors.push("actor must contain a UUID actorId and psychiatrist role");
  if (body.status === "not-assessed") {
    if (body.pastMedicalHistory?.length || body.medications?.length) errors.push("not-assessed records cannot contain history or medications");
    ["substantialSuicideRisk", "priorAntipsychoticTherapy", "priorAntipsychoticTherapySuccessful", "clozapineContraindication", "recurrentNonAdherenceDeterioration"].forEach((field) => {
      if (body[field] !== "not-assessed") errors.push(`${field} must be not-assessed when status is not-assessed`);
    });
  }
  return errors;
}

function canonicalV2Assessment(body, context, existing) {
  const now = new Date().toISOString();
  return {
    interfaceVersion: INTERFACE_VERSION,
    schemaVersion: SCHEMA_VERSION,
    assessmentId: existing?.assessmentId || crypto.randomUUID(),
    patientId: existing?.patientId || body.patientId,
    encounterId: existing?.encounterId || body.encounterId,
    status: body.status,
    pastMedicalHistory: [...body.pastMedicalHistory],
    medications: body.medications.map((medication) => ({
      originalText: medication.originalText.trim(),
      doseText: medication.doseText == null ? null : String(medication.doseText).trim(),
      routeText: medication.routeText == null ? null : String(medication.routeText).trim(),
      frequencyText: medication.frequencyText == null ? null : String(medication.frequencyText).trim(),
      normalizedIdentity: {
        state: medication.normalizedIdentity.state,
        conceptId: medication.normalizedIdentity.conceptId ?? null,
        display: medication.normalizedIdentity.display ?? null,
        terminologyVersion: medication.normalizedIdentity.terminologyVersion ?? null
      }
    })),
    substantialSuicideRisk: body.substantialSuicideRisk,
    priorAntipsychoticTherapy: body.priorAntipsychoticTherapy,
    priorAntipsychoticTherapySuccessful: body.priorAntipsychoticTherapySuccessful,
    antipsychotic: body.antipsychotic,
    clozapineContraindication: body.clozapineContraindication,
    clozapineContraindications: [...body.clozapineContraindications],
    recurrentNonAdherenceDeterioration: body.recurrentNonAdherenceDeterioration,
    actor: { actorId: body.actor.actorId, role: body.actor.role },
    createdAt: existing?.createdAt || now,
    updatedAt: now,
    resourceVersion: existing ? existing.resourceVersion + 1 : 1,
    provenance: {
      sourceModule: "medical-history",
      createdRequestId: existing?.provenance.createdRequestId || context.requestId,
      updatedRequestId: context.requestId
    }
  };
}

async function createV2Assessment(req, res, context) {
  if (!requireV2Schema(req, res, context)) return;
  const key = req.headers["idempotency-key"];
  if (typeof key !== "string" || !/^[A-Za-z0-9._~-]{16,128}$/.test(key)) {
    sendProblem(res, context, 400, "COMMON_IDEMPOTENCY_KEY_REQUIRED", "Idempotency key required", "Idempotency-Key must contain 16 to 128 supported characters.");
    return;
  }
  const body = await parseBody(req);
  const errors = validateV2Write(body, true);
  if (errors.length) {
    sendProblem(res, context, 400, "MEDICAL_HISTORY_INVALID_ASSESSMENT", "Invalid medical history assessment", "The assessment does not satisfy schema 2.0.0.", errors);
    return;
  }
  const fingerprint = crypto.createHash("sha256").update(canonicalJson(body)).digest("hex");
  const store = await readJson(V2_FILE, { assessments: {}, idempotency: {} });
  pruneIdempotency(store);
  const prior = store.idempotency[key];
  if (prior) {
    if (prior.fingerprint !== fingerprint) {
      sendProblem(res, context, 409, "COMMON_IDEMPOTENCY_KEY_REUSED", "Idempotency key reused", "Idempotency-Key was already used with different input.");
      return;
    }
    const assessment = prior.response;
    sendV2(res, 201, assessment, context, { ETag: assessmentEtag(assessment) });
    return;
  }
  const assessment = canonicalV2Assessment(body, context);
  store.assessments[assessment.assessmentId] = assessment;
  store.idempotency[key] = { fingerprint, response: assessment, createdAt: assessment.createdAt };
  await writeJson(V2_FILE, store);
  sendV2(res, 201, assessment, context, { ETag: assessmentEtag(assessment) });
}

async function getV2Assessment(res, assessmentId, context) {
  if (!isUuid(assessmentId)) {
    sendProblem(res, context, 400, "MEDICAL_HISTORY_INVALID_ASSESSMENT_ID", "Invalid assessment identifier", "assessmentId must be a UUID.");
    return;
  }
  const store = await readJson(V2_FILE, { assessments: {}, idempotency: {} });
  const assessment = store.assessments[assessmentId];
  if (!assessment) {
    sendProblem(res, context, 404, "MEDICAL_HISTORY_ASSESSMENT_NOT_FOUND", "Assessment not found", "No medical history assessment exists for that identifier.");
    return;
  }
  sendV2(res, 200, assessment, context, { ETag: assessmentEtag(assessment) });
}

async function updateV2Assessment(req, res, assessmentId, context) {
  if (!requireV2Schema(req, res, context)) return;
  if (!isUuid(assessmentId)) {
    sendProblem(res, context, 400, "MEDICAL_HISTORY_INVALID_ASSESSMENT_ID", "Invalid assessment identifier", "assessmentId must be a UUID.");
    return;
  }
  const store = await readJson(V2_FILE, { assessments: {}, idempotency: {} });
  const current = store.assessments[assessmentId];
  if (!current) {
    sendProblem(res, context, 404, "MEDICAL_HISTORY_ASSESSMENT_NOT_FOUND", "Assessment not found", "No medical history assessment exists for that identifier.");
    return;
  }
  const ifMatch = req.headers["if-match"];
  if (!ifMatch) {
    sendProblem(res, context, 428, "COMMON_PRECONDITION_REQUIRED", "Precondition required", "If-Match is required for assessment updates.");
    return;
  }
  if (ifMatch !== assessmentEtag(current)) {
    sendProblem(res, context, 412, "COMMON_PRECONDITION_FAILED", "Precondition failed", "If-Match does not match the current resource version.");
    return;
  }
  const body = await parseBody(req);
  const errors = validateV2Write(body, false);
  if (errors.length) {
    sendProblem(res, context, 400, "MEDICAL_HISTORY_INVALID_ASSESSMENT", "Invalid medical history assessment", "The assessment does not satisfy schema 2.0.0.", errors);
    return;
  }
  const assessment = canonicalV2Assessment(body, context, current);
  store.assessments[assessmentId] = assessment;
  await writeJson(V2_FILE, store);
  sendV2(res, 200, assessment, context, { ETag: assessmentEtag(assessment) });
}

function sendError(res, status, message, details) {
  sendJson(res, status, { error: { message, details } });
}

async function activateMedicalHistory(req, res) {
  const body = await parseBody(req);
  if (!isValidCode(body.code)) {
    sendError(res, 422, "Activation code must be exactly 6 alphanumeric characters.");
    return;
  }

  const code = normalizeCode(body.code);
  const now = new Date();
  const expiresAt = new Date(now.getTime() + 2 * 60 * 60 * 1000);
  const sessions = await readJson(SESSIONS_FILE, []);
  const existingIndex = sessions.findIndex((session) => session.code === code && session.status !== "expired");
  const activation = {
    activationId: crypto.randomUUID(),
    code,
    status: "active",
    receivedAt: now.toISOString(),
    expiresAt: expiresAt.toISOString(),
    context: {
      patientId: body.patientId || null,
      encounterId: body.encounterId || null,
      requestedByModule: body.requestedByModule || null,
      returnUrl: body.returnUrl || null
    }
  };

  if (existingIndex >= 0) {
    sessions[existingIndex] = activation;
  } else {
    sessions.push(activation);
  }

  await writeJson(SESSIONS_FILE, sessions);
  sendJson(res, 201, {
    ...activation,
    launchUrl: `/?code=${encodeURIComponent(code)}`
  });
}

async function getActivation(req, res, code) {
  if (!isValidCode(code)) {
    sendError(res, 422, "Activation code must be exactly 6 alphanumeric characters.");
    return;
  }

  const normalizedCode = normalizeCode(code);
  const sessions = await readJson(SESSIONS_FILE, []);
  const activation = sessions.find((session) => session.code === normalizedCode);

  if (!activation) {
    sendError(res, 404, "No active Medical History session found for this code.");
    return;
  }

  if (new Date(activation.expiresAt).getTime() < Date.now()) {
    activation.status = "expired";
    await writeJson(SESSIONS_FILE, sessions);
    sendError(res, 410, "This Medical History activation code has expired.");
    return;
  }

  sendJson(res, 200, activation);
}

function validateSubmission(body) {
  const errors = [];
  if (!isValidCode(body.code)) errors.push("code must be exactly 6 alphanumeric characters");
  if (!Array.isArray(body.pastMedicalHistory)) errors.push("pastMedicalHistory must be an array");
  if (!Array.isArray(body.drugs)) errors.push("drugs must be an array");
  const history = Array.isArray(body.pastMedicalHistory) ? body.pastMedicalHistory : [];
  if (history.some((condition) => !COMORBIDITY_OPTIONS.includes(condition))) errors.push("pastMedicalHistory contains an unsupported condition");
  const drugs = Array.isArray(body.drugs) ? body.drugs : [];
  if (drugs.length > 20) errors.push("drugs cannot contain more than 20 entries");
  drugs.forEach((drug, index) => {
    if (!drug || typeof drug.name !== "string" || drug.name.trim().length === 0) errors.push(`drugs[${index}].name is required`);
  });
  ["substantialSuicideRisk", "priorAntipsychoticTherapy", "clozapineContraindication", "recurrentNonAdherenceDeterioration"].forEach((field) => {
    if (typeof body[field] !== "boolean") errors.push(`${field} must be a boolean`);
  });
  if (body.priorAntipsychoticTherapy === true) {
    if (typeof body.priorAntipsychoticTherapySuccessful !== "boolean") errors.push("priorAntipsychoticTherapySuccessful must be a boolean when priorAntipsychoticTherapy is true");
    if (!ANTIPSYCHOTIC_OPTIONS.includes(body.antipsychotic)) errors.push("antipsychotic must be selected from the supported options when priorAntipsychoticTherapy is true");
  }
  const contraindications = body.clozapineContraindications;
  if (!Array.isArray(contraindications)) errors.push("clozapineContraindications must be an array");
  if (Array.isArray(contraindications)) {
    if (contraindications.some((item) => !CLOZAPINE_CONTRAINDICATION_OPTIONS.includes(item))) errors.push("clozapineContraindications contains an unsupported option");
    if (body.clozapineContraindication === true && contraindications.length === 0) errors.push("at least one clozapine contraindication is required when clozapineContraindication is true");
    if (body.clozapineContraindication === false && contraindications.length > 0) errors.push("clozapineContraindications must be empty when clozapineContraindication is false");
  }
  return errors;
}
async function submitMedicalHistory(req, res) {
  const body = await parseBody(req);
  const errors = validateSubmission(body);
  if (errors.length) {
    sendError(res, 422, "Medical History submission failed validation.", errors);
    return;
  }

  const code = normalizeCode(body.code);
  const sessions = await readJson(SESSIONS_FILE, []);
  const activation = sessions.find((session) => session.code === code);
  if (!activation || activation.status === "expired") {
    sendError(res, 404, "Submit requires an active Medical History activation code.");
    return;
  }

  const submissions = await readJson(SUBMISSIONS_FILE, []);
  const submission = {
    submissionId: crypto.randomUUID(),
    code,
    patientId: activation.context.patientId,
    encounterId: activation.context.encounterId,
    pastMedicalHistory: body.pastMedicalHistory.map(String),
    drugs: body.drugs.map((drug) => ({
      name: String(drug.name).trim(),
      dose: drug.dose ? String(drug.dose).trim() : "",
      route: drug.route ? String(drug.route).trim() : "",
      frequency: drug.frequency ? String(drug.frequency).trim() : ""
    })),
    substantialSuicideRisk: body.substantialSuicideRisk,
    priorAntipsychoticTherapy: body.priorAntipsychoticTherapy,
    priorAntipsychoticTherapySuccessful: body.priorAntipsychoticTherapy ? body.priorAntipsychoticTherapySuccessful : null,
    antipsychotic: body.priorAntipsychoticTherapy ? body.antipsychotic : null,
    clozapineContraindication: body.clozapineContraindication,
    clozapineContraindications: body.clozapineContraindication ? body.clozapineContraindications.map(String) : [],
    recurrentNonAdherenceDeterioration: body.recurrentNonAdherenceDeterioration,
    submittedAt: new Date().toISOString(),
    submittedBy: body.submittedBy || "standalone-ui",
    source: body.source || "medical-history-module"
  };

  submissions.push(submission);
  activation.status = "submitted";
  activation.submissionId = submission.submissionId;
  activation.submittedAt = submission.submittedAt;

  await writeJson(SUBMISSIONS_FILE, submissions);
  await writeJson(SESSIONS_FILE, sessions);
  sendJson(res, 201, submission);
}

async function listSubmissions(req, res, url) {
  const submissions = await readJson(SUBMISSIONS_FILE, []);
  const code = url.searchParams.get("code");
  if (code) {
    sendJson(res, 200, submissions.filter((submission) => submission.code === normalizeCode(code)));
    return;
  }
  sendJson(res, 200, submissions);
}

async function serveStatic(req, res, url) {
  const requestedPath = url.pathname === "/" ? "/index.html" : decodeURIComponent(url.pathname);
  const filePath = path.normalize(path.join(PUBLIC_DIR, requestedPath));

  if (!filePath.startsWith(PUBLIC_DIR)) {
    sendError(res, 403, "Forbidden path.");
    return;
  }

  try {
    const body = await fs.readFile(filePath);
    const contentType = MIME_TYPES[path.extname(filePath)] || "application/octet-stream";
    res.writeHead(200, { "Content-Type": contentType });
    res.end(body);
  } catch (error) {
    if (error.code === "ENOENT") {
      res.writeHead(302, { Location: "/" });
      res.end();
      return;
    }
    throw error;
  }
}

async function route(req, res) {
  const url = new URL(req.url, `http://${req.headers.host}`);
  const context = requestContext(req);

  if (req.method === "OPTIONS") {
    sendJson(res, 204, {});
    return;
  }

  if (req.method === "GET" && url.pathname === "/api/internal/medical-history/health") {
    sendJson(res, 200, { status: "ok", module: "Medical History" });
    return;
  }

  if (req.method === "GET" && url.pathname === "/healthz") {
    sendV2(res, 200, { status: "live", service: "medical-history", moduleVersion: MODULE_VERSION, time: new Date().toISOString() }, context);
    return;
  }

  if (req.method === "GET" && url.pathname === "/readyz") {
    sendV2(res, 200, { status: "ready", service: "medical-history", moduleVersion: MODULE_VERSION, time: new Date().toISOString(), checks: [{ name: "assessment-store", status: "ready" }] }, context);
    return;
  }

  if (req.method === "GET" && url.pathname === "/api/medical-history/v1/contract") {
    sendV2(res, 200, {
      moduleId: "medical-history",
      moduleVersion: MODULE_VERSION,
      interfaceVersion: INTERFACE_VERSION,
      schemaVersions: [SCHEMA_VERSION],
      profileVersion: "1.0.0",
      openapiPath: "/api/medical-history/v2/contract/openapi",
      idempotencyKeyRetentionSeconds: 86400,
      time: new Date().toISOString()
    }, context);
    return;
  }

  const contractMatch = url.pathname.match(/^\/api\/medical-history\/v2\/contract\/(document|schema|openapi)$/);
  if (req.method === "GET" && contractMatch) {
    const names = {
      document: "medical-history-assessment-v2.contract.json",
      schema: "medical-history-assessment-v2.schema.json",
      openapi: "openapi-v2.json"
    };
    sendV2(res, 200, await readJson(path.join(CONTRACTS_DIR, names[contractMatch[1]]), {}), context);
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/medical-history/v2/assessments") {
    await createV2Assessment(req, res, context);
    return;
  }

  const v2AssessmentMatch = url.pathname.match(/^\/api\/medical-history\/v2\/assessments\/([0-9a-f-]{36})$/);
  if (req.method === "GET" && v2AssessmentMatch) {
    await getV2Assessment(res, v2AssessmentMatch[1], context);
    return;
  }
  if (req.method === "PUT" && v2AssessmentMatch) {
    await updateV2Assessment(req, res, v2AssessmentMatch[1], context);
    return;
  }

  if (req.method === "GET" && url.pathname === "/api/internal/medical-history/options") {
    sendJson(res, 200, { pastMedicalHistory: COMORBIDITY_OPTIONS, antipsychotics: ANTIPSYCHOTIC_OPTIONS, clozapineContraindications: CLOZAPINE_CONTRAINDICATION_OPTIONS });
    return;
  }

  if (req.method === "GET" && url.pathname === "/api/internal/medical-history/schema") {
    sendJson(res, 200, await readJson(SCHEMA_FILE, {}));
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/internal/medical-history/activate") {
    await activateMedicalHistory(req, res);
    return;
  }

  const activationMatch = url.pathname.match(/^\/api\/internal\/medical-history\/activation\/([A-Za-z0-9]{1,20})$/);
  if (req.method === "GET" && activationMatch) {
    await getActivation(req, res, activationMatch[1]);
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/internal/medical-history/submissions") {
    await submitMedicalHistory(req, res);
    return;
  }

  if (req.method === "GET" && url.pathname === "/api/internal/medical-history/submissions") {
    await listSubmissions(req, res, url);
    return;
  }

  if (req.method === "GET") {
    await serveStatic(req, res, url);
    return;
  }

  sendError(res, 405, "Method not allowed.");
}

ensureDataFiles()
  .then(() => {
    http
      .createServer((req, res) => {
        route(req, res).catch((error) => {
          const status = error.status || 500;
          sendError(res, status, error.message || "Internal server error");
        });
      })
      .listen(PORT, () => {
        console.log(`Medical History module running at http://localhost:${PORT}`);
      });
  })
  .catch((error) => {
    console.error("Failed to start Medical History module:", error);
    process.exit(1);
  });
