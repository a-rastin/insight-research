import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const engine = require("../src/ddi-engine.js");

const fixtureKb = {
  version: "ikb-test",
  drugs: [
    { id: "rxnorm:4493", name: "fluoxetine", aliases: ["Prozac"] },
    { id: "rxnorm:8332", name: "pimozide", aliases: [] },
    { id: "rxnorm:51272", name: "quetiapine", aliases: ["Seroquel"] }
  ],
  interactions: [
    {
      id: "ddi-1",
      drugAId: "rxnorm:4493",
      drugAName: "fluoxetine",
      drugBId: "rxnorm:8332",
      drugBName: "pimozide",
      severity: "contraindicated",
      mechanism: "QTc prolongation",
      clinicalEffect: "fluoxetine and pimozide both increase QTc interval.",
      recommendation: "Do not coadminister.",
      monitoring: "ECG/QTc monitoring",
      evidenceSource: "fixture",
      evidenceExcerpt: "fluoxetine and pimozide both increase QTc interval. Contraindicated.",
      sourceReportPath: "fixture",
      reviewStatus: "approved",
      knowledgeBaseVersion: "ikb-test"
    },
    {
      id: "ddi-2",
      drugAId: "rxnorm:4493",
      drugAName: "fluoxetine",
      drugBId: "rxnorm:51272",
      drugBName: "quetiapine",
      severity: "moderate",
      mechanism: "serotonergic toxicity risk",
      clinicalEffect: "monitor for additive CNS and serotonergic effects.",
      recommendation: "Monitor closely.",
      monitoring: "Mental status",
      evidenceSource: "fixture",
      evidenceExcerpt: "monitor closely",
      sourceReportPath: "fixture",
      reviewStatus: "approved",
      knowledgeBaseVersion: "ikb-test"
    }
  ]
};

test("suggestDrugs resolves canonical names and aliases", () => {
  const suggestions = engine.suggestDrugs("pro", fixtureKb);
  assert.equal(suggestions[0].name, "fluoxetine");
});

test("checkInteractions generates all pairs and sorts by severity", () => {
  const result = engine.checkInteractions([
    { name: "Prozac", dose: "20 mg daily" },
    { name: "pimozide", dose: "1 mg daily" },
    { name: "Seroquel", dose: "50 mg nightly" }
  ], fixtureKb);

  assert.equal(result.alerts.length, 2);
  assert.equal(result.alerts[0].severity, "contraindicated");
  assert.deepEqual(result.alerts[0].interactingDrugs, ["fluoxetine", "pimozide"]);
});

test("checkInteractions retains dose-specific medication pairs", () => {
  const result = engine.checkInteractions([
    { name: "fluoxetine", dose: "10 mg" },
    { name: "fluoxetine", dose: "20 mg" },
    { name: "pimozide", dose: "1 mg" }
  ], fixtureKb);

  assert.equal(result.alerts.length, 2);
  assert.deepEqual(result.alerts.map((alert) => alert.patientMedications.map((med) => med.dose)), [
    ["10 mg", "1 mg"],
    ["20 mg", "1 mg"]
  ]);
  assert.equal(new Set(result.alerts.map((alert) => alert.id)).size, 2);
});

test("medication instances distinguish route, frequency, and formulation", () => {
  const result = engine.checkInteractions([
    { name: "fluoxetine", dose: "10 mg", route: "oral", frequency: "daily" },
    { name: "fluoxetine", dose: "10 mg", route: "IV", frequency: "daily" },
    { name: "fluoxetine", dose: "10 mg", route: "oral", frequency: "weekly" },
    { name: "pimozide", dose: "1 mg" }
  ], fixtureKb);

  assert.equal(result.alerts.length, 3);
  assert.equal(new Set(result.alerts.flatMap((alert) => alert.patientMedications).map((med) => med.instanceId)).size, 4);
});

test("exact duplicate rows remain distinct medication instances", () => {
  const result = engine.checkInteractions([
    { name: "fluoxetine", dose: "10 mg", route: "oral", frequency: "daily" },
    { name: "fluoxetine", dose: "10 mg", route: "oral", frequency: "daily" },
    { name: "pimozide", dose: "1 mg" }
  ], fixtureKb);

  assert.equal(result.alerts.length, 2);
  const fluoxetineIds = result.alerts.map((alert) => alert.patientMedications[0].instanceId);
  assert.equal(new Set(fluoxetineIds).size, 2);
});

test("reversing medication order preserves the interaction-instance alert identity", () => {
  const medications = [
    { name: "fluoxetine", dose: "20 mg", route: "oral", frequency: "daily" },
    { name: "pimozide", dose: "1 mg", route: "oral", frequency: "nightly" }
  ];
  const forward = engine.checkInteractions(medications, fixtureKb);
  const reversed = engine.checkInteractions([...medications].reverse(), fixtureKb);

  assert.equal(forward.alerts.length, 1);
  assert.equal(reversed.alerts.length, 1);
  assert.equal(forward.alerts[0].id, reversed.alerts[0].id);
  assert.deepEqual(
    forward.alerts[0].patientMedications.map((med) => med.instanceId).sort(),
    reversed.alerts[0].patientMedications.map((med) => med.instanceId).sort()
  );
});

test("checkInteractions reports unresolved medications", () => {
  const result = engine.checkInteractions(["fluoxetine", "not-a-drug"], fixtureKb);
  assert.equal(result.unresolved.length, 1);
  assert.equal(result.unresolved[0].name, "not-a-drug");
});

test("shared aliases are reported as ambiguous instead of resolving to the last indexed drug", () => {
  const kb = {
    ...fixtureKb,
    drugs: [
      ...fixtureKb.drugs,
      { id: "local:first", name: "first drug", aliases: ["shared"] },
      { id: "local:second", name: "second drug", aliases: ["shared"] }
    ],
    interactions: [{
      ...fixtureKb.interactions[0],
      id: "ddi-shared",
      drugAId: "local:second",
      drugAName: "second drug"
    }]
  };

  const result = engine.checkInteractions(["shared", "pimozide"], kb);

  assert.equal(result.alerts.length, 0);
  assert.equal(result.unresolved.length, 0);
  assert.equal(result.ambiguous.length, 1);
  assert.deepEqual(result.ambiguous[0].candidates.map((drug) => drug.id), ["local:first", "local:second"]);
});

test("resolution distinguishes resolved, ambiguous, and unknown identities", () => {
  const kb = {
    ...fixtureKb,
    drugs: [
      { id: "local:one", name: "Same Name", aliases: ["Repeat", "repeat", "Solo"] },
      { id: "local:two", name: "same name", aliases: ["SOLO"] }
    ]
  };
  const index = engine.buildIndex(kb);

  assert.equal(engine.resolveDrug("repeat", index).status, "resolved");
  assert.equal(engine.resolveDrug("SAME NAME", index).status, "ambiguous");
  assert.equal(engine.resolveDrug("solo", index).status, "ambiguous");
  assert.equal(engine.resolveDrug("missing", index).status, "unknown");
  assert.equal(index.byName.get("repeat").length, 1);
  assert.equal(index.identityCollisions.length, 2);
});

test("createAuditEntry captures KB version and override reason", () => {
  const result = engine.checkInteractions(["fluoxetine", "pimozide"], fixtureKb);
  const audit = engine.createAuditEntry(result.alerts[0], "overridden", {
    reason: "benefit outweighs risk",
    sessionCode: "DDI-260705-ABC123"
  });
  assert.equal(audit.knowledgeBaseVersion, "ikb-test");
  assert.equal(audit.reason, "benefit outweighs risk");
  assert.equal(audit.sessionCode, "DDI-260705-ABC123");
});

test("createAuditEntry rejects blank and whitespace-only override rationales", () => {
  const alert = engine.checkInteractions(["fluoxetine", "pimozide"], fixtureKb).alerts[0];
  assert.throws(() => engine.createAuditEntry(alert, "overridden", { reason: "" }), /nonblank rationale/);
  assert.throws(() => engine.createAuditEntry(alert, "overridden", { reason: "  \n\t " }), /nonblank rationale/);
});

test("createAuditEntry trims valid rationales and enforces the maximum length", () => {
  const alert = engine.checkInteractions(["fluoxetine", "pimozide"], fixtureKb).alerts[0];
  const audit = engine.createAuditEntry(alert, "overridden", { reason: "  Benefits outweigh risks.  " });
  assert.equal(audit.reason, "Benefits outweigh risks.");
  assert.throws(
    () => engine.createAuditEntry(alert, "overridden", { reason: "x".repeat(501) }),
    /must not exceed 500 characters/
  );
});

test("parseReportText imports uploaded report drugs and interactions", () => {
  const parsed = engine.parseReportText(`
newdrug (Rx)
Brand and Other Names: NewBrand
Dosage Forms & Strengths
tablet
5mg
Interactions
Contraindicated (1)

pimozide
newdrug and pimozide both increase QTc interval. Contraindicated.
Adverse Effects
`, "NewDrug.txt", { version: "ikb-test" });

  assert.equal(parsed.drug.name, "newdrug");
  assert.equal(parsed.drug.isSourceReportDrug, true);
  assert.ok(parsed.drug.aliases.includes("NewBrand"));
  assert.ok(parsed.drug.doseSuggestions.includes("tablet: 5mg"));
  assert.equal(parsed.interactions.length, 1);
  assert.equal(parsed.interactions[0].drugBName, "pimozide");
  assert.equal(parsed.interactions[0].reviewStatus, "uploaded_pending_review");
});


test("clinical eligibility excludes every unapproved status", () => {
  for (const status of ["rejected", "parsed_pending_review", "uploaded_pending_review", undefined]) {
    const record = { ...fixtureKb.interactions[0] };
    if (status === undefined) delete record.reviewStatus; else record.reviewStatus = status;
    const kb = { ...fixtureKb, interactions: [record] };
    assert.equal(engine.isInteractionEligible(record, kb), false);
    assert.equal(engine.checkInteractions(["fluoxetine", "pimozide"], kb).alerts.length, 0);
  }
  assert.equal(engine.checkInteractions(["fluoxetine", "pimozide"], fixtureKb).alerts.length, 1);
});

test("admin preview explicitly includes rejected interactions", () => {
  const kb = { ...fixtureKb, interactions: [{ ...fixtureKb.interactions[0], reviewStatus: "rejected" }] };
  assert.equal(engine.checkInteractions(["fluoxetine", "pimozide"], kb, { adminPreview: true }).alerts.length, 1);
});

test("reject persist rebuild and recheck produces no alert", () => {
  const kb = JSON.parse(JSON.stringify(fixtureKb));
  assert.equal(engine.checkInteractions(["fluoxetine", "pimozide"], kb).alerts.length, 1);
  kb.interactions[0].reviewStatus = "rejected";
  const persisted = JSON.parse(JSON.stringify(kb));
  const index = engine.buildIndex(persisted);
  assert.equal(engine.checkInteractions(["fluoxetine", "pimozide"], persisted, { index }).alerts.length, 0);
});
