const test = require("node:test");
const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const fs = require("node:fs/promises");
const path = require("node:path");
const os = require("node:os");

const port = 4300 + Math.floor(Math.random() * 500);
const base = `http://127.0.0.1:${port}`;
let child;
let dataDir;

async function request(url, options) {
  const response = await fetch(base + url, { headers: { "Content-Type": "application/json" }, ...options });
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
  child = spawn(process.execPath, ["server.js"], { cwd: path.resolve(__dirname, ".."), env: { ...process.env, PORT: String(port), MEDICAL_HISTORY_DATA_DIR: dataDir }, stdio: "ignore" });
  await waitForServer();
});

test.after(async () => { child.kill(); await fs.rm(dataDir, { recursive: true, force: true }); });

test("options expose diseases, antipsychotics, and exact clozapine contraindications", async () => {
  const result = await request("/api/internal/medical-history/options");
  assert.equal(result.status, 200);
  assert.ok(result.body.pastMedicalHistory.includes("Hypertension"));
  assert.ok(result.body.antipsychotics.includes("Clozapine"));
  assert.deepEqual(result.body.clozapineContraindications, ["Severe neutropenia", "Clozapine-induced myocarditis", "Unmanaged seizure disorder"]);
});

test("saves complete conditional history correlated with normalized code", async () => {
  await request("/api/internal/medical-history/activate", { method: "POST", body: JSON.stringify({ code: "ab12cd" }) });
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
  await request("/api/internal/medical-history/activate", { method: "POST", body: JSON.stringify({ code: "NO1234" }) });
  const payload = { code: "NO1234", pastMedicalHistory: [], drugs: [], substantialSuicideRisk: false, priorAntipsychoticTherapy: false, priorAntipsychoticTherapySuccessful: null, antipsychotic: null, clozapineContraindication: false, clozapineContraindications: [], recurrentNonAdherenceDeterioration: false };
  const saved = await request("/api/internal/medical-history/submissions", { method: "POST", body: JSON.stringify(payload) });
  assert.equal(saved.status, 201);
  assert.equal(saved.body.priorAntipsychoticTherapySuccessful, null);
  assert.equal(saved.body.antipsychotic, null);
});

test("rejects over 20 drugs and invalid conditional answers", async () => {
  await request("/api/internal/medical-history/activate", { method: "POST", body: JSON.stringify({ code: "BAD123" }) });
  const basePayload = { code: "BAD123", pastMedicalHistory: [], drugs: Array.from({ length: 21 }, (_, i) => ({ name: `Drug ${i}` })), substantialSuicideRisk: false, priorAntipsychoticTherapy: true, clozapineContraindication: true, clozapineContraindications: [], recurrentNonAdherenceDeterioration: false };
  const result = await request("/api/internal/medical-history/submissions", { method: "POST", body: JSON.stringify(basePayload) });
  assert.equal(result.status, 422);
  assert.ok(result.body.error.details.some((error) => error.includes("more than 20")));
  assert.ok(result.body.error.details.some((error) => error.includes("antipsychotic")));
  assert.ok(result.body.error.details.some((error) => error.includes("at least one clozapine")));
});
