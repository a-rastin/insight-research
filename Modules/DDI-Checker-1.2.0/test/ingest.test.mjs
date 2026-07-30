import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { buildKnowledgeBase, extractDoseSuggestions, parseReport, validateDrugIdentities } from "../scripts/ingest.mjs";
const REPORT = `
fluoxetine (Rx)
Interactions
Contraindicated (1)
pimozide
fluoxetine and pimozide both increase QTc interval. Contraindicated.
Adverse Effects
`;

test("ingestion identity validation detects canonical and alias collisions but deduplicates one drug's aliases", () => {
  const collisions = validateDrugIdentities([
    { id: "one", name: "Drug A", aliases: ["Shared", "shared"] },
    { id: "two", name: "drug a", aliases: ["SHARED"] }
  ]);

  assert.deepEqual(collisions.map((collision) => collision.label), ["drug a", "shared"]);
  assert.deepEqual(collisions[1].candidates.map((candidate) => candidate.id), ["one", "two"]);
});

test("parseReport extracts long-form severity sections", () => {
  const drugs = new Map();
  const raw = `
fluoxetine (Rx)
Brand and Other Names: Prozac

Interactions
Contraindicated (1)

pimozide
fluoxetine and pimozide both increase QTc interval. Contraindicated.

Serious (1)

amitriptyline
fluoxetine will increase the level or effect of amitriptyline by affecting hepatic enzyme CYP2C19 metabolism. Avoid or Use Alternate Drug.

Adverse Effects
`;

  const parsed = parseReport(raw, "Fluoxetine.txt", { drugs, version: "ikb-test" });
  assert.equal(parsed.interactions.length, 2);
  assert.equal(parsed.interactions[0].severity, "contraindicated");
  assert.equal(parsed.interactions[1].severity, "major");
});

test("parseReport extracts compact bullet sections", () => {
  const drugs = new Map();
  const raw = `
quetiapine (Rx)
Interactions
Contraindicated (1)
• lefamulin: increases level/effect of quetiapine by affecting CYP3A4 metabolism. Contraindicated.
Monitor Closely (1)
• Increased Sedation/CNS Depression: alprazolam, lorazepam, zolpidem.
Adverse Effects
`;

  const parsed = parseReport(raw, "Quetiapine.txt", { drugs, version: "ikb-test" });
  assert.equal(parsed.interactions.length, 4);
  assert.equal(parsed.interactions[0].severity, "contraindicated");
  assert.equal(parsed.interactions[1].severity, "moderate");
});

test("buildKnowledgeBase versions a folder of text reports", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ddi-ingest-"));
  fs.writeFileSync(path.join(dir, "Fluoxetine.txt"), `
fluoxetine (Rx)
Interactions
Contraindicated (1)

pimozide
fluoxetine and pimozide both increase QTc interval. Contraindicated.
Adverse Effects
`);

  const kb = buildKnowledgeBase(dir);
  assert.equal(kb.source.textReportCount, 1);
  assert.equal(kb.interactions.length, 1);
  assert.match(kb.version, /^ikb-/);
});

test("knowledge-base versions are stable content identities independent of source location", () => {
  const first = fs.mkdtempSync(path.join(os.tmpdir(), "ddi-ingest-a-"));
  const second = fs.mkdtempSync(path.join(os.tmpdir(), "ddi-ingest-b-"));
  fs.mkdirSync(path.join(first, "nested"));
  fs.mkdirSync(path.join(second, "nested"));
  fs.writeFileSync(path.join(first, "nested", "Fluoxetine.txt"), REPORT);
  fs.writeFileSync(path.join(second, "nested", "Fluoxetine.txt"), REPORT);

  assert.equal(buildKnowledgeBase(first).version, buildKnowledgeBase(second).version);
});

test("knowledge-base versions change with content, parser, schema, or normalization changes", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ddi-ingest-version-"));
  const reportPath = path.join(dir, "Fluoxetine.txt");
  fs.writeFileSync(reportPath, REPORT);
  const baseline = buildKnowledgeBase(dir).version;

  fs.appendFileSync(reportPath, "\nAdditional exact source bytes.\n");
  assert.notEqual(buildKnowledgeBase(dir).version, baseline);
  fs.writeFileSync(reportPath, REPORT);
  assert.notEqual(buildKnowledgeBase(dir, { parserVersion: "test-parser-2" }).version, baseline);
  assert.notEqual(buildKnowledgeBase(dir, { schemaVersion: "test-schema-2" }).version, baseline);
  assert.notEqual(buildKnowledgeBase(dir, { normalization: { identitySystem: "test-normalizer" } }).version, baseline);
});
test("extractDoseSuggestions captures form strengths and dosing lines", () => {
  const raw = `
fluoxetine (Rx)
Dosage Forms & Strengths
capsule
10mg
20mg
Major Depressive Disorder
Initial: 20 mg PO qDay
Interactions
Contraindicated (1)
`;

  const suggestions = extractDoseSuggestions(raw);
  assert.ok(suggestions.includes("capsule: 10mg"));
  assert.ok(suggestions.includes("Initial: 20 mg PO qDay"));
});
