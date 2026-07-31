import assert from "assert";
import { execFile } from "child_process";
import fs from "fs";
import os from "os";
import path from "path";
import { ITEM_CODES, deriveScores, evaluatePanss } from "./panss.js";

const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), "severity-v2-"));
const port = 40000 + process.pid % 10000;
const baseUrl = `http://127.0.0.1:${port}`;
const server = execFile("node", ["server.js"], {
  env: {
    ...process.env,
    PORT: String(port),
    SEVERITY_DATA_FILE: path.join(dataDir, "legacy.json"),
    SEVERITY_V2_DATA_FILE: path.join(dataDir, "v2.json")
  }
});

const patientId = "11111111-1111-4111-8111-111111111111";
const encounterId = "22222222-2222-4222-8222-222222222222";
const allOnes = Object.fromEntries(ITEM_CODES.map(code => [code, 1]));
const allSevens = Object.fromEntries(ITEM_CODES.map(code => [code, 7]));
const headers = {
  "Content-Type": "application/json",
  "X-Schema-Version": "2.0.0"
};

async function waitForServer() {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      if ((await fetch(`${baseUrl}/api/severity/v2/contract`)).ok) return;
    } catch {}
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error("server did not start");
}

try {
  await waitForServer();

  const publishedContract = JSON.parse(fs.readFileSync("contracts/panss-assessment-v2.contract.json", "utf8"));
  assert.strictEqual(Object.values(publishedContract.items).flat().length, 30);
  assert.deepStrictEqual(publishedContract.allowedItemScore, { type: "integer", minimum: 1, maximum: 7 });
  assert.match(publishedContract.legacyPassSemantics, /skipped only/);

  assert.deepStrictEqual(deriveScores(allOnes), { positive: 7, negative: 7, general: 16, total: 30 });
  assert.deepStrictEqual(deriveScores(allSevens), { positive: 49, negative: 49, general: 112, total: 210 });
  assert.deepStrictEqual(evaluatePanss("completed", allOnes), {
    valid: true,
    state: "completed",
    missingItemCodes: [],
    scores: { positive: 7, negative: 7, general: 16, total: 30 },
    scaleVersion: "PANSS-30-1.0.0",
    ruleVersion: "PANSS-SUM-2.0.0"
  });
  const incomplete = evaluatePanss("incomplete", { P1: 4 });
  assert.strictEqual(incomplete.state, "incomplete");
  assert.strictEqual(incomplete.scores, null);
  assert.strictEqual(incomplete.missingItemCodes.length, 29);
  assert.strictEqual(evaluatePanss("passed", {}).state, "passed");
  assert.strictEqual(evaluatePanss("completed", { ...allOnes, X1: 2 }).code, "PANSS_UNKNOWN_ITEMS");
  assert.strictEqual(evaluatePanss("completed", { ...allOnes, P1: 0 }).code, "PANSS_INVALID_ITEM_SCORE");
  assert.strictEqual(evaluatePanss("completed", allOnes, { positive: 7, negative: 7, general: 16, total: 31 }).code, "PANSS_PROJECTED_SCORES_MISMATCH");

  const contract = await fetch(`${baseUrl}/api/severity/v2/contract`);
  assert.strictEqual(contract.status, 200);
  assert.strictEqual((await contract.json()).ruleVersion, "PANSS-SUM-2.0.0");

  const openapi = JSON.parse(fs.readFileSync("contracts/openapi-v2.json", "utf8"));
  assert.deepStrictEqual(Object.keys(openapi.paths).sort(), [
    "/api/severity/v2/assessments",
    "/api/severity/v2/assessments/{assessmentId}",
    "/api/severity/v2/contract",
    "/api/severity/v2/contract/document",
    "/api/severity/v2/contract/openapi",
    "/api/severity/v2/contract/schema"
  ]);
  for (const artifact of ["document", "schema", "openapi"]) {
    assert.strictEqual((await fetch(`${baseUrl}/api/severity/v2/contract/${artifact}`)).status, 200);
  }

  const completedBody = JSON.stringify({ patientId, encounterId, status: "completed", itemScores: allOnes });
  const created = await fetch(`${baseUrl}/api/severity/v2/assessments`, {
    method: "POST",
    headers: { ...headers, "Idempotency-Key": "completed-case-1" },
    body: completedBody
  });
  assert.strictEqual(created.status, 201);
  const createdEtag = created.headers.get("etag");
  const assessment = await created.json();
  assert.match(assessment.assessmentId, /^[0-9a-f-]{36}$/);
  assert.deepStrictEqual(assessment.scores, { positive: 7, negative: 7, general: 16, total: 30 });
  assert.strictEqual(assessment.evaluation.state, "completed");
  assert.deepStrictEqual(assessment.evaluation.scores, assessment.scores);
  assert.strictEqual(assessment.provenance.scaleVersion, "PANSS-30-1.0.0");

  const replay = await fetch(`${baseUrl}/api/severity/v2/assessments`, {
    method: "POST",
    headers: { ...headers, "Idempotency-Key": "completed-case-1" },
    body: JSON.stringify({ itemScores: allOnes, status: "completed", encounterId, patientId })
  });
  assert.deepStrictEqual(await replay.json(), assessment);

  const conflict = await fetch(`${baseUrl}/api/severity/v2/assessments`, {
    method: "POST",
    headers: { ...headers, "Idempotency-Key": "completed-case-1" },
    body: JSON.stringify({ patientId, encounterId, status: "skipped", itemScores: {} })
  });
  assert.strictEqual(conflict.status, 409);

  const invalidPass = await fetch(`${baseUrl}/api/severity/v2/assessments`, {
    method: "POST",
    headers: { ...headers, "Idempotency-Key": "invalid-pass-1" },
    body: JSON.stringify({ patientId, encounterId, status: "passed", itemScores: {} })
  });
  assert.strictEqual(invalidPass.status, 400);

  const clientScores = await fetch(`${baseUrl}/api/severity/v2/assessments`, {
    method: "POST",
    headers: { ...headers, "Idempotency-Key": "client-score-1" },
    body: JSON.stringify({ patientId, encounterId, status: "completed", itemScores: allOnes, scores: { total: 30 } })
  });
  assert.strictEqual(clientScores.status, 400);

  const mismatchedScores = await fetch(`${baseUrl}/api/severity/v2/assessments`, {
    method: "POST",
    headers: { ...headers, "Idempotency-Key": "score-mismatch-1" },
    body: JSON.stringify({
      patientId,
      encounterId,
      status: "completed",
      itemScores: allOnes,
      scores: { positive: 7, negative: 7, general: 16, total: 31 }
    })
  });
  assert.strictEqual(mismatchedScores.status, 400);

  const matchingScores = await fetch(`${baseUrl}/api/severity/v2/assessments`, {
    method: "POST",
    headers: { ...headers, "Idempotency-Key": "score-match-case-1" },
    body: JSON.stringify({
      patientId,
      encounterId,
      status: "completed",
      itemScores: allOnes,
      scores: { positive: 7, negative: 7, general: 16, total: 30 }
    })
  });
  assert.strictEqual(matchingScores.status, 201);
  assert.deepStrictEqual((await matchingScores.json()).scores, deriveScores(allOnes));

  const inProgress = await fetch(`${baseUrl}/api/severity/v2/assessments`, {
    method: "POST",
    headers: { ...headers, "Idempotency-Key": "incomplete-case-1" },
    body: JSON.stringify({ patientId, encounterId, status: "in-progress", itemScores: { P1: 4 } })
  });
  assert.strictEqual(inProgress.status, 201);
  const inProgressBody = await inProgress.json();
  assert.strictEqual(inProgressBody.evaluation.state, "incomplete");
  assert.strictEqual(inProgressBody.evaluation.scores, null);
  assert.strictEqual(inProgressBody.evaluation.missingItemCodes.length, 29);

  const skipped = await fetch(`${baseUrl}/api/severity/v2/assessments/${assessment.assessmentId}`, {
    method: "PUT",
    headers: { ...headers, "If-Match": createdEtag },
    body: JSON.stringify({ status: "skipped", itemScores: {} })
  });
  assert.strictEqual(skipped.status, 200);
  const skippedBody = await skipped.json();
  assert.strictEqual(skippedBody.scores, null);
  assert.deepStrictEqual(skippedBody.itemScores, {});
  assert.strictEqual(skippedBody.evaluation.state, "passed");

  const replayAfterUpdate = await fetch(`${baseUrl}/api/severity/v2/assessments`, {
    method: "POST",
    headers: { ...headers, "Idempotency-Key": "completed-case-1" },
    body: JSON.stringify({ encounterId, patientId, itemScores: allOnes, status: "completed" })
  });
  assert.deepStrictEqual(await replayAfterUpdate.json(), assessment);

  const stale = await fetch(`${baseUrl}/api/severity/v2/assessments/${assessment.assessmentId}`, {
    method: "PUT",
    headers: { ...headers, "If-Match": createdEtag },
    body: JSON.stringify({ status: "in-progress", itemScores: { P1: 4 } })
  });
  assert.strictEqual(stale.status, 412);

  const partialCompleted = await fetch(`${baseUrl}/api/severity/v2/assessments`, {
    method: "POST",
    headers: { ...headers, "Idempotency-Key": "partial-case-1" },
    body: JSON.stringify({ patientId, encounterId, status: "completed", itemScores: { P1: 4 } })
  });
  assert.strictEqual(partialCompleted.status, 400);

  console.log("SUCCESS: PANSS v2 contract and API checks passed");
} finally {
  server.kill();
  fs.rmSync(dataDir, { recursive: true, force: true });
}
