const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), "medical-history-v2-"));
const port = 44000 + (process.pid % 1000);
const base = `http://127.0.0.1:${port}`;
const child = spawn(process.execPath, ["server.js"], {
  cwd: __dirname,
  env: {...process.env, PORT: String(port), MEDICAL_HISTORY_DATA_DIR: dataDir},
  stdio: "ignore"
});

const patientId = "11111111-1111-4111-8111-111111111111";
const encounterId = "22222222-2222-4222-8222-222222222222";
const actorId = "33333333-3333-4333-8333-333333333333";
const headers = {"Content-Type": "application/json", "X-Schema-Version": "2.0.0"};
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
    normalizedIdentity: {state: "unresolved"}
  }],
  substantialSuicideRisk: "unknown",
  priorAntipsychoticTherapy: "yes",
  priorAntipsychoticTherapySuccessful: "no",
  antipsychotic: "Risperidone",
  clozapineContraindication: "not-assessed",
  clozapineContraindications: [],
  recurrentNonAdherenceDeterioration: "no",
  actor: {actorId, role: "psychiatrist"}
};

async function waitForServer() {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      if ((await fetch(`${base}/healthz`)).ok) return;
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error("server did not start");
}

(async () => {
  try {
    await waitForServer();
    const published = JSON.parse(fs.readFileSync(path.join(__dirname, "contracts", "medical-history-assessment-v2.contract.json"), "utf8"));
    assert.equal(published.schemaVersion, "2.0.0");
    assert.deepEqual(published.controlledClinicalStates, ["yes", "no", "unknown", "not-assessed"]);

    const discovery = await fetch(`${base}/api/medical-history/v1/contract`);
    assert.equal(discovery.status, 200);
    assert.equal((await discovery.json()).interfaceVersion, "2.0.0");

    const created = await fetch(`${base}/api/medical-history/v2/assessments`, {
      method: "POST",
      headers: {...headers, "Idempotency-Key": "medical-history-case-0001"},
      body: JSON.stringify(body)
    });
    assert.equal(created.status, 201);
    const etag = created.headers.get("etag");
    const assessment = await created.json();
    assert.equal(assessment.patientId, patientId);
    assert.equal(assessment.medications[0].originalText, body.medications[0].originalText);
    assert.equal(assessment.medications[0].normalizedIdentity.state, "unresolved");
    assert.equal(assessment.medications[0].normalizedIdentity.conceptId, null);
    assert.equal(assessment.substantialSuicideRisk, "unknown");
    assert.equal(assessment.resourceVersion, 1);
    assert.equal(assessment.actor.actorId, actorId);

    const replay = await fetch(`${base}/api/medical-history/v2/assessments`, {
      method: "POST",
      headers: {...headers, "Idempotency-Key": "medical-history-case-0001"},
      body: JSON.stringify(body)
    });
    assert.equal(replay.status, 201);
    assert.equal((await replay.json()).assessmentId, assessment.assessmentId);

    const conflict = await fetch(`${base}/api/medical-history/v2/assessments`, {
      method: "POST",
      headers: {...headers, "Idempotency-Key": "medical-history-case-0001"},
      body: JSON.stringify({...body, substantialSuicideRisk: "no"})
    });
    assert.equal(conflict.status, 409);

    const missingUnknown = await fetch(`${base}/api/medical-history/v2/assessments`, {
      method: "POST",
      headers: {...headers, "Idempotency-Key": "medical-history-case-0002"},
      body: JSON.stringify({...body, substantialSuicideRisk: false})
    });
    assert.equal(missingUnknown.status, 400);

    const updateBody = {...body, status: "in-progress", substantialSuicideRisk: "not-assessed"};
    delete updateBody.patientId;
    delete updateBody.encounterId;
    const updated = await fetch(`${base}/api/medical-history/v2/assessments/${assessment.assessmentId}`, {
      method: "PUT",
      headers: {...headers, "If-Match": etag},
      body: JSON.stringify(updateBody)
    });
    assert.equal(updated.status, 200);
    assert.equal((await updated.json()).resourceVersion, 2);

    const stale = await fetch(`${base}/api/medical-history/v2/assessments/${assessment.assessmentId}`, {
      method: "PUT",
      headers: {...headers, "If-Match": etag},
      body: JSON.stringify(updateBody)
    });
    assert.equal(stale.status, 412);

    console.log("SUCCESS: Medical History v2 contract and API checks passed");
  } finally {
    child.kill();
    fs.rmSync(dataDir, {recursive: true, force: true});
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
