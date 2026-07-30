import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  assessmentToFormValue,
  createMedicalHistoryClient,
  deriveStatus,
  normalizeApiBasePath,
  normalizeContext,
  validateServerAssessment
} from "./public/app.js";

const root = path.dirname(fileURLToPath(import.meta.url));
const uiSource = fs.readFileSync(path.join(root, "public", "app.js"), "utf8");
const html = fs.readFileSync(path.join(root, "public", "index.html"), "utf8");
const css = fs.readFileSync(path.join(root, "public", "styles.css"), "utf8");
const patientId = "11111111-1111-4111-8111-111111111111";
const encounterId = "22222222-2222-4222-8222-222222222222";
const actorId = "33333333-3333-4333-8333-333333333333";
const assessmentId = "55555555-5555-4555-8555-555555555555";
const context = { patientId, encounterId, actorId };

assert.deepEqual(normalizeContext(context), { ...context, assessmentId: null });
assert.throws(() => normalizeContext({ patientId, encounterId }), /Actor UUID context/);
assert.equal(normalizeApiBasePath("/gateway/medical-history/"), "/gateway/medical-history");
assert.throws(() => normalizeApiBasePath("https://clinical.example/api"), /gateway-relative/);

const duplicateMedication = {
  originalText: "Same medication text",
  doseText: null,
  routeText: null,
  frequencyText: null,
  normalizedIdentity: { state: "unresolved", conceptId: null, display: null, terminologyVersion: null }
};
const assessment = {
  interfaceVersion: "2.0.0",
  schemaVersion: "2.0.0",
  assessmentId,
  patientId,
  encounterId,
  status: "in-progress",
  pastMedicalHistory: [],
  medications: [duplicateMedication, structuredClone(duplicateMedication)],
  substantialSuicideRisk: "not-assessed",
  priorAntipsychoticTherapy: "not-assessed",
  priorAntipsychoticTherapySuccessful: "not-assessed",
  antipsychotic: null,
  clozapineContraindication: "not-assessed",
  clozapineContraindications: [],
  recurrentNonAdherenceDeterioration: "not-assessed",
  actor: { actorId, role: "psychiatrist" },
  resourceVersion: 1
};
validateServerAssessment(assessment, context);
const formValue = assessmentToFormValue(assessment);
assert.equal(formValue.medications.length, 2, "duplicate medication instances must not collapse");
assert.equal(formValue.medications[0].normalizedIdentity.state, "unresolved");
assert.equal(formValue.medications[1].normalizedIdentity.state, "unresolved");
assert.equal(formValue.substantialSuicideRisk, null, "not-assessed must render as unanswered");
assert.notEqual(formValue.medications[0], formValue.medications[1]);

assert.equal(deriveStatus({
  substantialSuicideRisk: "not-assessed",
  priorAntipsychoticTherapy: "not-assessed",
  clozapineContraindication: "not-assessed",
  recurrentNonAdherenceDeterioration: "not-assessed",
  clozapineContraindications: []
}), "in-progress");
assert.equal(deriveStatus({
  substantialSuicideRisk: "unknown",
  priorAntipsychoticTherapy: "no",
  clozapineContraindication: "no",
  recurrentNonAdherenceDeterioration: "yes",
  clozapineContraindications: []
}), "completed");

const calls = [];
const fetchImpl = async (url, options = {}) => {
  calls.push({ url, options });
  if (url.endsWith("/csrf")) return new Response(JSON.stringify({ token: "csrf-token" }), { status: 200 });
  return new Response(JSON.stringify(assessment), { status: 201, headers: { ETag: '"assessment-v1"' } });
};
const client = createMedicalHistoryClient({ fetchImpl });
await client.save({
  context,
  assessment: null,
  etag: null,
  value: {
    status: "in-progress",
    pastMedicalHistory: [],
    medications: [duplicateMedication, structuredClone(duplicateMedication)],
    substantialSuicideRisk: "not-assessed",
    priorAntipsychoticTherapy: "not-assessed",
    priorAntipsychoticTherapySuccessful: "not-assessed",
    antipsychotic: null,
    clozapineContraindication: "not-assessed",
    clozapineContraindications: [],
    recurrentNonAdherenceDeterioration: "not-assessed",
    actor: { actorId, role: "psychiatrist" }
  }
});
assert.equal(calls[0].options.credentials, "include");
assert.equal(calls[1].options.credentials, "include");
assert.equal(calls[1].options.headers["X-CSRF-Token"], "csrf-token");
assert.equal(calls[1].options.headers["X-Schema-Version"], "2.0.0");
assert.ok(calls[1].options.headers["Idempotency-Key"]);
assert.equal(JSON.parse(calls[1].options.body).medications.length, 2);

assert.match(uiSource, /window\.InsightMedicalHistory = Object\.freeze\(\{ mount, unmount \}\)/);
assert.match(uiSource, /This error remains visible until a save succeeds/);
assert.match(uiSource, /alert\.focus\(\)/);
assert.match(css, /:focus-visible/);
assert.match(css, /prefers-reduced-motion/);
assert.match(html, /type="module"/);
const prohibitedBrowserState = /localStorage|sessionStorage|window\.location|window\.history|activation[_-]?code|patient[_-]?code/i;
assert.doesNotMatch(uiSource, prohibitedBrowserState);
assert.doesNotMatch(html, prohibitedBrowserState);
assert.doesNotMatch(uiSource, /console\.(?:log|info|warn|error)/);

console.log("SUCCESS: Medical History embedded UI context, duplicate/unresolved medication, privacy, CSRF, focus, and error checks passed");
