const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { MedicalHistoryRepository } = require("./repository");

const root = fs.mkdtempSync(path.join(os.tmpdir(), "medical-history-repository-"));
const actorId = "33333333-3333-4333-8333-333333333333";
const requestId = "55555555-5555-4555-8555-555555555555";

function assessment(id, version = 1) {
  const now = "2026-07-30T20:00:00.000Z";
  return {
    interfaceVersion: "2.0.0", schemaVersion: "2.0.0", assessmentId: id,
    patientId: "11111111-1111-4111-8111-111111111111", encounterId: "22222222-2222-4222-8222-222222222222",
    status: "not-assessed", pastMedicalHistory: [], medications: [], substantialSuicideRisk: "not-assessed",
    priorAntipsychoticTherapy: "not-assessed", priorAntipsychoticTherapySuccessful: "not-assessed", antipsychotic: null,
    clozapineContraindication: "not-assessed", clozapineContraindications: [], recurrentNonAdherenceDeterioration: "not-assessed",
    actor: { actorId, role: "psychiatrist" }, createdAt: now, updatedAt: now, resourceVersion: version,
    provenance: { sourceModule: "medical-history", optionSetVersion: "2.0.0", createdRequestId: requestId, updatedRequestId: requestId }
  };
}

try {
  const databasePath = path.join(root, "medical-history.db");
  const repository = new MedicalHistoryRepository(databasePath);
  assert.equal(repository.readiness(), true);
  assert.deepEqual(repository.stats(), { assessments: 0, versions: 0, quarantined: 0 });
  const id = "66666666-6666-4666-8666-666666666666";
  assert.equal(repository.createIdempotent({ actorId, key: "repository-create", fingerprint: "one", assessment: assessment(id), requestId }).replay, false);
  assert.equal(repository.createIdempotent({ actorId, key: "repository-create", fingerprint: "one", assessment: assessment(id), requestId }).replay, true);
  assert.equal(repository.createIdempotent({ actorId, key: "repository-create", fingerprint: "two", assessment: assessment(id), requestId }).conflict, true);
  assert.equal(repository.latest(assessment(id).encounterId).assessmentId, id);
  assert.equal(repository.update({ assessmentId: id, expectedVersion: 1, assessment: assessment(id, 2), actorId, requestId }).assessment.resourceVersion, 2);
  assert.equal(repository.update({ assessmentId: id, expectedVersion: 1, assessment: assessment(id, 2), actorId, requestId }).stale, true);
  repository.close();

  const importedId = "77777777-7777-4777-8777-777777777777";
  const importPath = path.join(root, "v2.json");
  fs.writeFileSync(importPath, JSON.stringify({ assessments: { [importedId]: assessment(importedId) }, idempotency: {} }));
  const importDatabase = path.join(root, "import.db");
  new MedicalHistoryRepository(importDatabase, [{ name: "v2", kind: "v2", path: importPath }]).close();
  const repeated = new MedicalHistoryRepository(importDatabase, [{ name: "v2", kind: "v2", path: importPath }]);
  assert.deepEqual(repeated.stats(), { assessments: 1, versions: 1, quarantined: 0 });
  repeated.close();

  const legacyCanonicalId = "88888888-8888-4888-8888-888888888888";
  const aliasesPath = path.join(root, "aliases.json");
  const canonicalLegacyPath = path.join(root, "canonical-legacy.json");
  fs.writeFileSync(aliasesPath, JSON.stringify([{ code: "ABC123", status: "active", expiresAt: "2999-01-01T00:00:00Z", context: { patientId: assessment(importedId).patientId, encounterId: assessment(importedId).encounterId } }]));
  fs.writeFileSync(canonicalLegacyPath, JSON.stringify([{ submissionId: legacyCanonicalId, code: "ABC123", patientId: assessment(importedId).patientId, encounterId: assessment(importedId).encounterId, submittedAt: "2026-07-30T20:00:00.000Z", pastMedicalHistory: [], drugs: [], substantialSuicideRisk: false, priorAntipsychoticTherapy: false, priorAntipsychoticTherapySuccessful: null, antipsychotic: null, clozapineContraindication: false, clozapineContraindications: [], recurrentNonAdherenceDeterioration: false }]));
  const legacyImportDatabase = path.join(root, "legacy-import.db");
  const legacyImport = new MedicalHistoryRepository(legacyImportDatabase, [
    { name: "aliases", kind: "aliases", path: aliasesPath },
    { name: "legacy", kind: "legacy", path: canonicalLegacyPath }
  ]);
  assert.equal(legacyImport.get(legacyCanonicalId).status, "completed");
  assert.equal(legacyImport.getAlias("ABC123").assessmentId, legacyCanonicalId);
  legacyImport.close();
  fs.writeFileSync(canonicalLegacyPath, JSON.stringify([]));
  assert.throws(() => new MedicalHistoryRepository(legacyImportDatabase, [{ name: "legacy", kind: "legacy", path: canonicalLegacyPath }]), /changed after import/);

  const legacyPath = path.join(root, "legacy.json");
  fs.writeFileSync(legacyPath, JSON.stringify([{ code: "ABC123", patientId: null }]));
  const quarantine = new MedicalHistoryRepository(databasePath, [{ name: "legacy", kind: "legacy", path: legacyPath }]);
  assert.equal(quarantine.stats().quarantined, 1);
  quarantine.close();

  const corruptPath = path.join(root, "corrupt.json");
  fs.writeFileSync(corruptPath, "{not-json");
  assert.throws(() => new MedicalHistoryRepository(databasePath, [{ name: "corrupt", kind: "legacy", path: corruptPath }]), /is corrupt/);
  const afterCorruption = new MedicalHistoryRepository(databasePath);
  assert.deepEqual(afterCorruption.stats(), { assessments: 1, versions: 2, quarantined: 1 });
  afterCorruption.close();
  console.log("SUCCESS: Medical History fresh/import/quarantine/corruption repository checks passed");
} finally {
  fs.rmSync(root, { recursive: true, force: true });
}
