const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const { canonicalAssessment, disposition, validateWrite } = require("../server");

const actorId = "33333333-3333-4333-8333-333333333333";
const patientId = "11111111-1111-4111-8111-111111111111";
const encounterId = "22222222-2222-4222-8222-222222222222";
const ctx = { requestId: "44444444-4444-4444-8444-444444444444" };

test("contract fields trace only to accepted source paths", () => {
  const contract = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "contracts", "suicide-risk-assessment-v1.contract.json")));
  const ownership = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "..", "..", "contracts", "clinical-ownership-v1.json")));
  const policy = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "..", "..", "contracts", "treatment-plan-safety-policy-v1.json")));
  assert.deepEqual(ownership.instrumentGovernance.allowedMissingStates, ["unknown", "unavailable"]);
  assert.ok(policy.uncertaintyPolicy.clinicallyRequiredInputStates.includes("conflicting"));
  assert.deepEqual(policy.emergencyPolicy.triggerStates.slice(0, 2), contract.riskStates.slice(3));
  assert.equal(contract.clinicalBoundary.questionsDefined, false);
  assert.equal(contract.clinicalBoundary.scoringDefined, false);
  assert.equal(contract.clinicalBoundary.riskScoreAlwaysNull, true);
  assert.equal(contract.sourceTraceability.length, 5);
});

test("missing, favorable, question, score, and emergency-instruction fields are rejected", () => {
  const base = { patientId, encounterId, riskState: "unknown", actor: { actorId, role: "psychiatrist" } };
  assert.deepEqual(validateWrite(base, true), []);
  assert.ok(validateWrite({ ...base, riskState: "low-risk" }, true).length);
  assert.ok(validateWrite({ ...base, score: 1 }, true).length);
  assert.ok(validateWrite({ ...base, questions: [] }, true).length);
  assert.ok(validateWrite({ ...base, emergencyInstruction: "call" }, true).length);
  assert.ok(validateWrite({ patientId, encounterId, actor: base.actor }, true).length);
});

test("unknown, unavailable, and conflicting states fail closed", () => {
  assert.equal(disposition("unknown").code, "TP_SUICIDE_RISK_UNAVAILABLE");
  assert.equal(disposition("unavailable").routinePlanningAllowed, false);
  assert.equal(disposition("conflicting").code, "TP_REQUIRED_DATA_CONFLICTING");
  for (const state of ["unknown", "unavailable", "conflicting"]) assert.equal(disposition(state).overrideAllowed, false);
});

test("approved urgent states use exact persistent INS-010 behavior", () => {
  for (const riskState of ["imminent-suicide-risk", "substantial-suicide-risk-requiring-urgent-evaluation"]) {
    const value = disposition(riskState);
    assert.equal(value.outcome, "emergency-blocked");
    assert.equal(value.code, "TP_EMERGENCY_ACTION_REQUIRED");
    assert.equal(value.guidance, "Stop routine planning and follow the applicable local emergency protocol for immediate clinical evaluation.");
    assert.equal(value.persistentUntilResolved, true);
    assert.equal(value.overrideAllowed, false);
  }
});

test("canonical assessment preserves explicit psychiatrist authority and no score", () => {
  const value = canonicalAssessment({ patientId, encounterId, riskState: "unknown", actor: { actorId, role: "psychiatrist" } }, ctx);
  assert.equal(value.actor.actorId, actorId);
  assert.equal(value.riskScore, null);
  assert.equal(value.instrument.completionClaimed, false);
  assert.equal(value.instrument.questionsDefined, false);
  assert.equal(value.instrument.scoringDefined, false);
});
