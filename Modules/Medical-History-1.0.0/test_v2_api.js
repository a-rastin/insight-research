const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const http = require("node:http");
const os = require("node:os");
const path = require("node:path");

const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), "medical-history-v2-"));
const port = 44000 + (process.pid % 500);
const authPort = port + 500;
const base = `http://127.0.0.1:${port}`;
const allowedOrigin = "http://clinical.test";
const patientId = "11111111-1111-4111-8111-111111111111";
const encounterId = "22222222-2222-4222-8222-222222222222";
const actorId = "33333333-3333-4333-8333-333333333333";
const sessionId = "44444444-4444-4444-8444-444444444444";
let child;

const body = {
  patientId,
  encounterId,
  status: "completed",
  pastMedicalHistory: ["Hypertension"],
  medications: [{
    originalText: "Lithium 300 mg oral daily",
    doseText: "300 mg",
    routeText: "oral",
    frequencyText: "daily",
    normalizedIdentity: { state: "unresolved", conceptId: null, display: null, terminologyVersion: null }
  }],
  substantialSuicideRisk: "unknown",
  priorAntipsychoticTherapy: "yes",
  priorAntipsychoticTherapySuccessful: "no",
  antipsychotic: "Risperidone",
  clozapineContraindication: "not-assessed",
  clozapineContraindications: [],
  recurrentNonAdherenceDeterioration: "no",
  actor: { actorId, role: "psychiatrist" }
};

const authServer = http.createServer((req, res) => {
  if (req.url !== "/api/auth/v2/session") return res.writeHead(404).end();
  const cookie = req.headers.cookie || "";
  if (!cookie.includes("session=") || cookie.includes("session=revoked")) return res.writeHead(401).end("{}");
  const role = cookie.includes("session=admin") ? "admin" : "psychiatrist";
  res.writeHead(200, { "Content-Type": "application/json", "X-Schema-Version": "2.0.0" });
  res.end(JSON.stringify({
    authenticated: true,
    authorized: true,
    interfaceVersion: "2.0.0",
    session: { id: sessionId, active: true, expiresAt: "2999-01-01T00:00:00Z" },
    user: { id: actorId, username: "clinician", role },
    gates: { passwordChangeRequired: false, disclaimerRequired: false, disclaimerVersion: "test-v1" },
    compatibility: { legacyUserId: 1, legacyRole: role === "psychiatrist" ? "user" : null }
  }));
});

async function waitForServer() {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      if ((await fetch(`${base}/healthz`)).ok) return;
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error("server did not start");
}

async function csrf(session = "psychiatrist") {
  const response = await fetch(`${base}/api/medical-history/v2/csrf`, { headers: { Cookie: `session=${session}` } });
  const payload = await response.json();
  return { response, token: payload.token, cookie: `session=${session}; medical_history_csrf=${payload.token}` };
}

function writeHeaders(context, extra = {}) {
  return {
    "Content-Type": "application/json",
    "X-Schema-Version": "2.0.0",
    "X-CSRF-Token": context.token,
    Cookie: context.cookie,
    ...extra
  };
}

(async () => {
  try {
    await new Promise((resolve) => authServer.listen(authPort, "127.0.0.1", resolve));
    child = spawn(process.execPath, ["server.js"], {
      cwd: __dirname,
      env: {
        ...process.env,
        PORT: String(port),
        MEDICAL_HISTORY_DATA_DIR: dataDir,
        MEDICAL_HISTORY_DB_PATH: path.join(dataDir, "medical-history.db"),
        MEDICAL_HISTORY_V2_DATA_FILE: path.join(dataDir, "missing-v2.json"),
        MEDICAL_HISTORY_AUTH_BASE_URL: `http://127.0.0.1:${authPort}`,
        MEDICAL_HISTORY_CSRF_SECRET: "test-medical-history-csrf-secret-32-characters",
        MEDICAL_HISTORY_ALLOWED_ORIGINS: allowedOrigin
      },
      stdio: "ignore"
    });
    await waitForServer();

    assert.equal((await fetch(`${base}/healthz`)).status, 200);
    assert.equal((await fetch(`${base}/readyz`)).status, 200);
    const published = JSON.parse(fs.readFileSync(path.join(__dirname, "contracts", "medical-history-assessment-v2.contract.json"), "utf8"));
    assert.equal(published.persistence.repository, "module-owned SQLite");
    assert.deepEqual(published.controlledClinicalStates, ["yes", "no", "unknown", "not-assessed"]);
    for (const artifact of ["document", "schema", "openapi"]) {
      assert.equal((await fetch(`${base}/api/medical-history/v2/contract/${artifact}`)).status, 200);
    }

    const denied = await fetch(`${base}/api/medical-history/v2/assessments/${patientId}`);
    assert.equal(denied.status, 401);
    const revoked = await fetch(`${base}/api/medical-history/v2/assessments/${patientId}`, { headers: { Cookie: "session=revoked" } });
    assert.equal(revoked.status, 401);
    assert.equal((await csrf("admin")).response.status, 403);

    const context = await csrf();
    assert.equal(context.response.status, 200);
    const noCsrf = await fetch(`${base}/api/medical-history/v2/assessments`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Schema-Version": "2.0.0", "Idempotency-Key": "medical-history-no-csrf", Cookie: "session=psychiatrist" },
      body: JSON.stringify(body)
    });
    assert.equal(noCsrf.status, 403);

    const created = await fetch(`${base}/api/medical-history/v2/assessments`, {
      method: "POST",
      headers: writeHeaders(context, { "Idempotency-Key": "medical-history-case-0001" }),
      body: JSON.stringify(body)
    });
    assert.equal(created.status, 201);
    const etag = created.headers.get("etag");
    const assessment = await created.json();
    assert.equal(assessment.patientId, patientId);
    assert.equal(assessment.substantialSuicideRisk, "unknown");
    assert.equal(assessment.provenance.optionSetVersion, "2.0.0");

    const replay = await fetch(`${base}/api/medical-history/v2/assessments`, {
      method: "POST",
      headers: writeHeaders(context, { "Idempotency-Key": "medical-history-case-0001" }),
      body: JSON.stringify({ ...body, actor: { role: "psychiatrist", actorId } })
    });
    assert.equal(replay.status, 201);
    assert.deepEqual(await replay.json(), assessment);
    const conflict = await fetch(`${base}/api/medical-history/v2/assessments`, {
      method: "POST",
      headers: writeHeaders(context, { "Idempotency-Key": "medical-history-case-0001" }),
      body: JSON.stringify({ ...body, substantialSuicideRisk: "no" })
    });
    assert.equal(conflict.status, 409);

    const latest = await fetch(`${base}/api/medical-history/v2/encounters/${encounterId}/assessments/latest`, { headers: { Cookie: "session=psychiatrist" } });
    assert.equal(latest.status, 200);
    assert.equal((await latest.json()).assessmentId, assessment.assessmentId);

    const updateBody = { ...body, status: "in-progress", substantialSuicideRisk: "not-assessed" };
    delete updateBody.patientId;
    delete updateBody.encounterId;
    const updates = await Promise.all(["unknown", "not-assessed"].map((value) => fetch(`${base}/api/medical-history/v2/assessments/${assessment.assessmentId}`, {
      method: "PUT",
      headers: writeHeaders(context, { "If-Match": etag }),
      body: JSON.stringify({ ...updateBody, substantialSuicideRisk: value })
    })));
    assert.deepEqual(updates.map((response) => response.status).sort(), [200, 412]);

    const allowed = await fetch(`${base}/api/medical-history/v2/assessments`, { method: "OPTIONS", headers: { Origin: allowedOrigin } });
    assert.equal(allowed.status, 204);
    assert.equal(allowed.headers.get("access-control-allow-origin"), allowedOrigin);
    assert.equal(allowed.headers.get("access-control-allow-credentials"), "true");
    assert.equal((await fetch(`${base}/api/medical-history/v2/assessments`, { method: "OPTIONS", headers: { Origin: "http://untrusted.test" } })).status, 403);

    await new Promise((resolve) => authServer.close(resolve));
    const unavailable = await fetch(`${base}/readyz`);
    assert.equal(unavailable.status, 503);
    assert.equal((await unavailable.json()).code, "MEDICAL_HISTORY_NOT_READY");
    console.log("SUCCESS: Medical History v2 auth, CSRF, CORS, repository, latest, ETag, idempotency, and readiness checks passed");
  } finally {
    if (child) child.kill("SIGTERM");
    if (authServer.listening) await new Promise((resolve) => authServer.close(resolve));
    fs.rmSync(dataDir, { recursive: true, force: true });
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
