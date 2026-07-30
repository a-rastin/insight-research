const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");
const { SuicideRiskRepository } = require("../repository");

test("repository migrates, versions, and enforces transactional concurrency", () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "suicide-risk-repository-"));
  const repository = new SuicideRiskRepository(path.join(directory, "risk.db"));
  try {
    const assessment = {
      assessmentId: "55555555-5555-4555-8555-555555555555",
      encounterId: "22222222-2222-4222-8222-222222222222",
      resourceVersion: 1,
      createdAt: "2026-07-30T00:00:00.000Z",
      updatedAt: "2026-07-30T00:00:00.000Z"
    };
    const create = repository.createIdempotent({ actorId: "33333333-3333-4333-8333-333333333333", key: "repository-case-01", fingerprint: "one", assessment, requestId: "44444444-4444-4444-8444-444444444444" });
    assert.equal(create.replay, false);
    assert.equal(repository.createIdempotent({ actorId: "33333333-3333-4333-8333-333333333333", key: "repository-case-01", fingerprint: "one", assessment, requestId: "44444444-4444-4444-8444-444444444444" }).replay, true);
    assert.equal(repository.createIdempotent({ actorId: "33333333-3333-4333-8333-333333333333", key: "repository-case-01", fingerprint: "two", assessment, requestId: "44444444-4444-4444-8444-444444444444" }).conflict, true);
    const updated = { ...assessment, resourceVersion: 2, updatedAt: "2026-07-30T01:00:00.000Z" };
    assert.equal(repository.update({ assessment: updated, expectedVersion: 1, actorId: "33333333-3333-4333-8333-333333333333", requestId: "44444444-4444-4444-8444-444444444444" }).assessment.resourceVersion, 2);
    assert.equal(repository.update({ assessment: { ...updated, resourceVersion: 3 }, expectedVersion: 1, actorId: "33333333-3333-4333-8333-333333333333", requestId: "44444444-4444-4444-8444-444444444444" }).stale, true);
    assert.equal(repository.latest(assessment.encounterId).resourceVersion, 2);
    assert.equal(repository.readiness(), true);
  } finally {
    repository.close();
    fs.rmSync(directory, { recursive: true, force: true });
  }
});
