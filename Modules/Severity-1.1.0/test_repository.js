import assert from "assert";
import fs from "fs";
import os from "os";
import path from "path";
import { SeverityRepository } from "./repository.js";

const root = fs.mkdtempSync(path.join(os.tmpdir(), "severity-repository-"));
const databasePath = path.join(root, "severity.db");
const actorId = "33333333-3333-4333-8333-333333333333";
const requestId = "55555555-5555-4555-8555-555555555555";

function assessment(id, version = 1) {
  const now = "2026-07-30T20:00:00.000Z";
  return {
    interfaceVersion: "2.0.0",
    schemaVersion: "2.0.0",
    assessmentId: id,
    patientId: "11111111-1111-4111-8111-111111111111",
    encounterId: "22222222-2222-4222-8222-222222222222",
    assessmentType: "PANSS",
    status: "skipped",
    itemScores: {},
    scores: null,
    evaluation: { state: "passed", missingItemCodes: [], scores: null, scaleVersion: "PANSS-30-1.0.0", ruleVersion: "PANSS-SUM-2.0.0" },
    resourceVersion: version,
    provenance: {
      sourceModule: "severity",
      createdAt: now,
      updatedAt: now,
      createdRequestId: requestId,
      updatedRequestId: requestId,
      scaleVersion: "PANSS-30-1.0.0",
      ruleVersion: "PANSS-SUM-2.0.0"
    }
  };
}

try {
  const fresh = new SeverityRepository(databasePath);
  assert.strictEqual(fresh.readiness(), true);
  assert.deepStrictEqual(fresh.stats(), { assessments: 0, versions: 0, quarantined: 0 });
  const id = "66666666-6666-4666-8666-666666666666";
  const created = fresh.createIdempotent({ actorId, key: "repository-create", fingerprint: "one", assessment: assessment(id), requestId });
  assert.strictEqual(created.replay, false);
  assert.strictEqual(fresh.createIdempotent({ actorId, key: "repository-create", fingerprint: "one", assessment: assessment(id), requestId }).replay, true);
  assert.strictEqual(fresh.createIdempotent({ actorId, key: "repository-create", fingerprint: "two", assessment: assessment(id), requestId }).conflict, true);
  const updated = assessment(id, 2);
  assert.strictEqual(fresh.update({ assessmentId: id, expectedVersion: 1, assessment: updated, actorId, requestId }).assessment.resourceVersion, 2);
  assert.strictEqual(fresh.update({ assessmentId: id, expectedVersion: 1, assessment: updated, actorId, requestId }).stale, true);
  assert.deepStrictEqual(fresh.stats(), { assessments: 1, versions: 2, quarantined: 0 });
  fresh.close();

  const importPath = path.join(root, "v2.json");
  const importedId = "77777777-7777-4777-8777-777777777777";
  fs.writeFileSync(importPath, JSON.stringify({ assessments: { [importedId]: assessment(importedId) }, idempotency: {} }));
  const importDatabasePath = path.join(root, "import.db");
  const canonicalImport = new SeverityRepository(importDatabasePath, [{ name: "v2", kind: "v2", path: importPath }]);
  assert.deepStrictEqual(canonicalImport.stats(), { assessments: 1, versions: 1, quarantined: 0 });
  assert.strictEqual(canonicalImport.get(importedId).patientId, assessment(importedId).patientId);
  canonicalImport.close();
  const repeatedImport = new SeverityRepository(importDatabasePath, [{ name: "v2", kind: "v2", path: importPath }]);
  assert.deepStrictEqual(repeatedImport.stats(), { assessments: 1, versions: 1, quarantined: 0 });
  repeatedImport.close();

  const legacyPath = path.join(root, "legacy.json");
  fs.writeFileSync(legacyPath, JSON.stringify({ "PAT-UNMAPPED": { patient_code: "PAT-UNMAPPED", status: "passed" } }));
  const imported = new SeverityRepository(databasePath, [{ name: "legacy", kind: "v1", path: legacyPath }]);
  assert.deepStrictEqual(imported.stats(), { assessments: 1, versions: 2, quarantined: 1 });
  imported.close();

  const corruptPath = path.join(root, "corrupt.json");
  fs.writeFileSync(corruptPath, "{not-json");
  assert.throws(() => new SeverityRepository(databasePath, [{ name: "corrupt", kind: "v1", path: corruptPath }]), /is corrupt/);
  const afterFailure = new SeverityRepository(databasePath);
  assert.deepStrictEqual(afterFailure.stats(), { assessments: 1, versions: 2, quarantined: 1 });
  afterFailure.close();
  console.log("SUCCESS: SQLite migration, repository, quarantine, corruption, provenance, and rollback checks passed");
} finally {
  fs.rmSync(root, { recursive: true, force: true });
}
