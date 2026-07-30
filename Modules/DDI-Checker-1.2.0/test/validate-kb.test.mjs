import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { validateKnowledgeBase } from "../scripts/validate-kb.mjs";

const dir = path.join(path.dirname(fileURLToPath(import.meta.url)), "fixtures", "kb");
const fixture = name => JSON.parse(fs.readFileSync(path.join(dir, name + ".json"), "utf8"));
const clone = value => JSON.parse(JSON.stringify(value));

test("valid pending KB passes structural validation but not clinical activation", () => {
  const kb = fixture("valid-pending");
  assert.deepEqual(validateKnowledgeBase(kb), []);
  assert.match(validateKnowledgeBase(kb, { clinicalActive: true }).join("\n"), /at least one approved interaction/);
});

test("malformed root produces readable diagnostics without throwing", () => {
  assert.deepEqual(validateKnowledgeBase(fixture("malformed-root")), [
    "root.schemaVersion must be a non-empty string",
    "root.status must be a non-empty string",
    "root.drugs must be an array",
    "root.interactions must be an array",
    "root.clinicalUse must be an object"
  ]);
});

test("malformed records diagnose identity, review, version, confidence, IDs, and pair conflicts", () => {
  const errors = validateKnowledgeBase(fixture("malformed-records")).join("\n");
  for (const expected of ["duplicate drug id","is ambiguous with","duplicate interaction id","invalid reviewStatus","invalid parserConfidence","knowledgeBaseVersion must match","conflicting record for pair"]) assert.match(errors, new RegExp(expected));
});

test("approved records require reviewer provenance", () => {
  const kb = fixture("valid-pending");
  Object.assign(kb.interactions[0], { reviewStatus: "approved", reviewedBy: "", reviewedAt: "yesterday" });
  const errors = validateKnowledgeBase(kb).join("\n");
  assert.match(errors, /approved record requires reviewedBy/);
  assert.match(errors, /approved record requires a valid reviewedAt timestamp/);
});

test("clinical-active mode accepts only eligible approved records", () => {
  const kb = fixture("valid-pending");
  Object.assign(kb, { status: "active_clinical", activatedAt: "2026-07-13T12:00:00Z", clinicalUse: { allowedForProduction: true } });
  Object.assign(kb.interactions[0], { reviewStatus: "approved", reviewedBy: "pharmacist", reviewedAt: "2026-07-13T11:00:00Z" });
  assert.deepEqual(validateKnowledgeBase(kb, { clinicalActive: true }), []);
  const bad = clone(kb);
  bad.drugs[0].identityStatus = "pending_rxnorm_review";
  bad.interactions[0].parserConfidence = "low";
  const errors = validateKnowledgeBase(bad, { clinicalActive: true }).join("\n");
  assert.match(errors, /not RxNorm-resolved/);
  assert.match(errors, /parserConfidence is low/);
});

test("exact duplicate unordered pairs are distinguished from conflicts", () => {
  const kb = fixture("valid-pending");
  kb.interactions.push({ ...clone(kb.interactions[0]), id: "ddi-2", drugAId: "rxnorm:2", drugBId: "rxnorm:1" });
  assert.match(validateKnowledgeBase(kb).join("\n"), /exact duplicate for pair/);
});
