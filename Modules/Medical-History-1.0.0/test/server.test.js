const test = require("node:test");
const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const fs = require("node:fs/promises");
const path = require("node:path");
const os = require("node:os");
const http = require("node:http");

const port = 4300 + Math.floor(Math.random() * 500);
const base = `http://127.0.0.1:${port}`;
let child;
let dataDir;
let authServer;
let csrfToken;
const authPort = port + 1000;
const patientId = "11111111-1111-4111-8111-111111111111";
const encounterId = "22222222-2222-4222-8222-222222222222";
const actorId = "33333333-3333-4333-8333-333333333333";
const sessionId = "44444444-4444-4444-8444-444444444444";

async function request(url, options) {
  const headers = { "Content-Type": "application/json", Cookie: `session=test; medical_history_csrf=${csrfToken || ""}` };
  if (options?.method && options.method !== "GET") headers["X-CSRF-Token"] = csrfToken;
  const response = await fetch(base + url, { ...options, headers: { ...headers, ...options?.headers } });
  return { status: response.status, body: await response.json() };
}

async function waitForServer() {
  for (let i = 0; i < 50; i++) {
    try { const response = await fetch(base + "/api/internal/medical-history/health"); if (response.ok) return; } catch {}
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error("server did not start");
}

test.before(async () => {
  dataDir = await fs.mkdtemp(path.join(os.tmpdir(), "medical-history-test-"));
  authServer = http.createServer((req, res) => {
    if (req.url !== "/api/auth/v2/session" || !req.headers.cookie?.includes("session=test")) return res.writeHead(401).end("{}");
    res.writeHead(200, { "Content-Type": "application/json", "X-Schema-Version": "2.0.0" });
    res.end(JSON.stringify({ authenticated: true, authorized: true, interfaceVersion: "2.0.0", session: { id: sessionId, active: true, expiresAt: "2999-01-01T00:00:00Z" }, user: { id: actorId, username: "clinician", role: "psychiatrist" }, gates: { passwordChangeRequired: false, disclaimerRequired: false, disclaimerVersion: "test-v1" }, compatibility: { legacyUserId: 1, legacyRole: "user" } }));
  });
  await new Promise((resolve) => authServer.listen(authPort, "127.0.0.1", resolve));
  child = spawn(process.execPath, ["server.js"], { cwd: path.resolve(__dirname, ".."), env: { ...process.env, PORT: String(port), MEDICAL_HISTORY_DATA_DIR: dataDir, MEDICAL_HISTORY_DB_PATH: path.join(dataDir, "medical-history.db"), MEDICAL_HISTORY_AUTH_BASE_URL: `http://127.0.0.1:${authPort}`, MEDICAL_HISTORY_CSRF_SECRET: "test-medical-history-csrf-secret-32-characters" }, stdio: "ignore" });
  await waitForServer();
  const csrf = await fetch(`${base}/api/medical-history/v2/csrf`, { headers: { Cookie: "session=test" } });
  csrfToken = (await csrf.json()).token;
});

test.after(async () => { child.kill(); await new Promise((resolve) => authServer.close(resolve)); await fs.rm(dataDir, { recursive: true, force: true }); });

test("options expose diseases, antipsychotics, and exact clozapine contraindications", async () => {
  const result = await request("/api/internal/medical-history/options");
  assert.equal(result.status, 200);
  assert.ok(result.body.pastMedicalHistory.includes("Hypertension"));
  assert.ok(result.body.antipsychotics.includes("Clozapine"));
  assert.deepEqual(result.body.clozapineContraindications, ["Severe neutropenia", "Clozapine-induced myocarditis", "Unmanaged seizure disorder"]);
});

test("saves complete conditional history correlated with normalized code", async () => {
  await request("/api/internal/medical-history/activate", { method: "POST", body: JSON.stringify({ code: "ab12cd", patientId, encounterId }) });
  const payload = { code: "ab12cd", pastMedicalHistory: ["Hypertension", "Asthma"], drugs: [{ name: "Lithium", dose: "300 mg", route: "Oral", frequency: "Daily" }], substantialSuicideRisk: true, priorAntipsychoticTherapy: true, priorAntipsychoticTherapySuccessful: false, antipsychotic: "Risperidone", clozapineContraindication: true, clozapineContraindications: ["Severe neutropenia"], recurrentNonAdherenceDeterioration: true };
  const saved = await request("/api/internal/medical-history/submissions", { method: "POST", body: JSON.stringify(payload) });
  assert.equal(saved.status, 201);
  assert.equal(saved.body.code, "AB12CD");
  assert.deepEqual(saved.body.pastMedicalHistory, payload.pastMedicalHistory);
  assert.deepEqual(saved.body.drugs, payload.drugs);
  assert.equal(saved.body.antipsychotic, "Risperidone");
  const lookup = await request("/api/internal/medical-history/submissions?code=ab12cd");
  assert.equal(lookup.body.length, 1);
  assert.equal(lookup.body[0].submissionId, saved.body.submissionId);
});

test("defaults-compatible no answers persist null conditional therapy data", async () => {
  await request("/api/internal/medical-history/activate", { method: "POST", body: JSON.stringify({ code: "NO1234", patientId, encounterId }) });
  const payload = { code: "NO1234", pastMedicalHistory: [], drugs: [], substantialSuicideRisk: false, priorAntipsychoticTherapy: false, priorAntipsychoticTherapySuccessful: null, antipsychotic: null, clozapineContraindication: false, clozapineContraindications: [], recurrentNonAdherenceDeterioration: false };
  const saved = await request("/api/internal/medical-history/submissions", { method: "POST", body: JSON.stringify(payload) });
  assert.equal(saved.status, 201);
  assert.equal(saved.body.priorAntipsychoticTherapySuccessful, null);
  assert.equal(saved.body.antipsychotic, null);
});

test("rejects over 20 drugs and invalid conditional answers", async () => {
  await request("/api/internal/medical-history/activate", { method: "POST", body: JSON.stringify({ code: "BAD123", patientId, encounterId }) });
  const basePayload = { code: "BAD123", pastMedicalHistory: [], drugs: Array.from({ length: 21 }, (_, i) => ({ name: `Drug ${i}` })), substantialSuicideRisk: false, priorAntipsychoticTherapy: true, clozapineContraindication: true, clozapineContraindications: [], recurrentNonAdherenceDeterioration: false };
  const result = await request("/api/internal/medical-history/submissions", { method: "POST", body: JSON.stringify(basePayload) });
  assert.equal(result.status, 422);
  assert.ok(result.body.error.details.some((error) => error.includes("more than 20")));
  assert.ok(result.body.error.details.some((error) => error.includes("antipsychotic")));
  assert.ok(result.body.error.details.some((error) => error.includes("at least one clozapine")));
});
