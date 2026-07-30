import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createClient, normalizeBase, normalizeContext, validateAssessment } from "../public/app.js";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const source = fs.readFileSync(path.join(root, "public", "app.js"), "utf8");
const html = fs.readFileSync(path.join(root, "public", "index.html"), "utf8");
const css = fs.readFileSync(path.join(root, "public", "styles.css"), "utf8");
const patientId = "11111111-1111-4111-8111-111111111111";
const encounterId = "22222222-2222-4222-8222-222222222222";
const actorId = "33333333-3333-4333-8333-333333333333";
const assessmentId = "55555555-5555-4555-8555-555555555555";
const context = { patientId, encounterId, actorId };

assert.deepEqual(normalizeContext(context), { ...context, assessmentId: null });
assert.throws(() => normalizeContext({ patientId, encounterId }), /Actor UUID context/);
assert.equal(normalizeBase("/gateway/suicide-risk/"), "/gateway/suicide-risk");
assert.throws(() => normalizeBase("https://clinical.example/api"), /gateway-relative/);

const assessment = {
  interfaceVersion: "1.0.0",
  schemaVersion: "1.0.0",
  assessmentId,
  patientId,
  encounterId,
  assessmentType: "psychiatrist-suicide-risk-assertion",
  instrument: { name: "C-SSRS", completionClaimed: false, sourceLicensingStatus: "unavailable", questionsDefined: false, scoringDefined: false },
  riskState: "unknown",
  riskScore: null,
  safetyDisposition: { outcome: "blocked", code: "TP_SUICIDE_RISK_UNAVAILABLE", routinePlanningAllowed: false, overrideAllowed: false, persistentUntilResolved: true, guidance: "Complete or obtain the approved suicide-risk assessment." },
  actor: { actorId, role: "psychiatrist" },
  resourceVersion: 1
};
assert.equal(validateAssessment(assessment, context), assessment);

const calls = [];
const fetchImpl = async (url, options = {}) => {
  calls.push({ url, options });
  if (url.endsWith("/csrf")) return new Response(JSON.stringify({ token: "csrf-token" }), { status: 200 });
  return new Response(JSON.stringify(assessment), { status: 201, headers: { ETag: '"risk-v1"' } });
};
const client = createClient({ fetchImpl });
await client.save({ context, assessment: null, etag: null, riskState: "unknown" });
assert.equal(calls[0].options.credentials, "include");
assert.equal(calls[1].options.credentials, "include");
assert.equal(calls[1].options.headers["X-CSRF-Token"], "csrf-token");
assert.equal(calls[1].options.headers["X-Schema-Version"], "1.0.0");
assert.ok(calls[1].options.headers["Idempotency-Key"]);

assert.match(source, /window\.InsightSuicideRisk = Object\.freeze\(\{ mount, unmount \}\)/);
assert.match(source, /No option is preselected/);
assert.match(source, /This error remains visible until a save succeeds/);
assert.match(source, /alert\.focus\(\)/);
assert.match(source, /role="alert"/);
assert.match(source, /aria-live="polite"/);
assert.match(css, /:focus-visible/);
assert.match(css, /prefers-reduced-motion/);
assert.match(css, /min-height: 44px/);
assert.match(html, /type="module"/);
assert.doesNotMatch(source, /localStorage|sessionStorage|window\.location|window\.history|patient[_-]?code/i);
assert.doesNotMatch(html, /localStorage|sessionStorage|patient[_-]?code/i);
assert.doesNotMatch(source, /console\.(?:log|info|warn|error)/);

console.log("SUCCESS: Suicide Risk UI context, privacy, CSRF, accessibility, urgent text, and lifecycle checks passed");
