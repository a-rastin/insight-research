import assert from "assert";
import { execFile } from "child_process";
import fs from "fs";
import http from "http";
import os from "os";
import path from "path";
import { ITEM_CODES, deriveScores, evaluatePanss } from "./panss.js";

const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), "severity-v2-"));
const port = 40000 + process.pid % 10000;
const authPort = port + 1;
const baseUrl = `http://127.0.0.1:${port}`;
const allowedOrigin = "http://clinical.test";
const patientId = "11111111-1111-4111-8111-111111111111";
const encounterId = "22222222-2222-4222-8222-222222222222";
const actorId = "33333333-3333-4333-8333-333333333333";
const sessionId = "44444444-4444-4444-8444-444444444444";
const allOnes = Object.fromEntries(ITEM_CODES.map(code => [code, 1]));
const allSevens = Object.fromEntries(ITEM_CODES.map(code => [code, 7]));
const authRequests = [];

const authServer = http.createServer((req, res) => {
  authRequests.push({ url: req.url, cookie: req.headers.cookie || "" });
  if (req.url !== "/api/auth/v2/session") {
    res.writeHead(404).end();
    return;
  }
  const cookie = req.headers.cookie || "";
  if (!cookie.includes("session=") || cookie.includes("session=revoked")) {
    res.writeHead(401, { "Content-Type": "application/json" }).end("{}");
    return;
  }
  const role = cookie.includes("session=admin") ? "admin" : "psychiatrist";
  res.writeHead(200, { "Content-Type": "application/json", "X-Schema-Version": "2.0.0" });
  res.end(JSON.stringify({
    authenticated: true,
    authorized: true,
    interfaceVersion: "2.0.0",
    session: { id: sessionId, active: true, expiresAt: "2999-01-01T00:00:00Z" },
    user: { id: actorId, username: "clinician", role },
    gates: { passwordChangeRequired: false, disclaimerRequired: false, disclaimerVersion: "test-v1" },
    compatibility: { legacyUserId: 1, legacyRole: role === "psychiatrist" ? "user" : null }
  }));
});
await new Promise(resolve => authServer.listen(authPort, "127.0.0.1", resolve));

const server = execFile("node", ["server.js"], {
  env: {
    ...process.env,
    PORT: String(port),
    SEVERITY_DB_PATH: path.join(dataDir, "severity.db"),
    SEVERITY_DATA_FILE: path.join(dataDir, "missing-v1.json"),
    SEVERITY_V2_DATA_FILE: path.join(dataDir, "missing-v2.json"),
    SEVERITY_AUTH_BASE_URL: `http://127.0.0.1:${authPort}`,
    SEVERITY_CSRF_SECRET: "test-only-severity-csrf-secret-32-characters",
    SEVERITY_ALLOWED_ORIGINS: allowedOrigin
  }
});
let serverError = "";
server.stderr.on("data", chunk => { serverError += chunk.toString(); });

async function waitForServer() {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      if ((await fetch(`${baseUrl}/healthz`)).ok) return;
    } catch {}
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error(`server did not start: ${serverError}`);
}

async function csrf(session = "psychiatrist") {
  const response = await fetch(`${baseUrl}/api/severity/v2/csrf`, { headers: { Cookie: `session=${session}` } });
  const body = await response.json();
  return { response, token: body.token, cookie: `session=${session}; severity_csrf=${body.token}` };
}

function writeHeaders(csrfContext, extra = {}) {
  return {
    "Content-Type": "application/json",
    "X-Schema-Version": "2.0.0",
    "X-CSRF-Token": csrfContext.token,
    Cookie: csrfContext.cookie,
    ...extra
  };
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
  assert.strictEqual(evaluatePanss("incomplete", { P1: 4 }).missingItemCodes.length, 29);
  assert.strictEqual(evaluatePanss("passed", {}).state, "passed");
  assert.strictEqual(evaluatePanss("completed", { ...allOnes, X1: 2 }).code, "PANSS_UNKNOWN_ITEMS");
  assert.strictEqual(evaluatePanss("completed", { ...allOnes, P1: 0 }).code, "PANSS_INVALID_ITEM_SCORE");
  assert.strictEqual(evaluatePanss("completed", allOnes, { positive: 7, negative: 7, general: 16, total: 31 }).code, "PANSS_PROJECTED_SCORES_MISMATCH");

  assert.strictEqual((await fetch(`${baseUrl}/healthz`)).status, 200);
  assert.strictEqual((await fetch(`${baseUrl}/readyz`)).status, 200);
  assert.strictEqual((await fetch(`${baseUrl}/api/severity/v2/contract`)).status, 200);
  for (const artifact of ["document", "schema", "openapi"]) {
    assert.strictEqual((await fetch(`${baseUrl}/api/severity/v2/contract/${artifact}`)).status, 200);
  }

  const deniedRead = await fetch(`${baseUrl}/api/severity/v2/assessments/${patientId}`);
  assert.strictEqual(deniedRead.status, 401);
  assert.strictEqual((await deniedRead.json()).code, "COMMON_AUTHENTICATION_REQUIRED");
  const revoked = await fetch(`${baseUrl}/api/severity/v2/assessments/${patientId}`, { headers: { Cookie: "session=revoked" } });
  assert.strictEqual(revoked.status, 401);
  const adminCsrf = await csrf("admin");
  assert.strictEqual(adminCsrf.response.status, 403);

  const context = await csrf();
  assert.strictEqual(context.response.status, 200);
  const noCsrf = await fetch(`${baseUrl}/api/severity/v2/assessments`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Schema-Version": "2.0.0", "Idempotency-Key": "no-csrf-case", Cookie: "session=psychiatrist" },
    body: JSON.stringify({ patientId, encounterId, status: "completed", itemScores: allOnes })
  });
  assert.strictEqual(noCsrf.status, 403);
  assert.strictEqual((await noCsrf.json()).code, "COMMON_CSRF_REJECTED");
  const malformedCsrfCookie = await fetch(`${baseUrl}/api/severity/v2/assessments`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Schema-Version": "2.0.0",
      "Idempotency-Key": "malformed-csrf",
      "X-CSRF-Token": "invalid",
      Cookie: "session=psychiatrist; severity_csrf=%"
    },
    body: JSON.stringify({ patientId, encounterId, status: "completed", itemScores: allOnes })
  });
  assert.strictEqual(malformedCsrfCookie.status, 403);

  const invalidPass = await fetch(`${baseUrl}/api/severity/v2/assessments`, {
    method: "POST",
    headers: writeHeaders(context, { "Idempotency-Key": "invalid-pass-1" }),
    body: JSON.stringify({ patientId, encounterId, status: "passed", itemScores: {} })
  });
  assert.strictEqual(invalidPass.status, 400);
  const malformedProjection = await fetch(`${baseUrl}/api/severity/v2/assessments`, {
    method: "POST",
    headers: writeHeaders(context, { "Idempotency-Key": "client-score-1" }),
    body: JSON.stringify({ patientId, encounterId, status: "completed", itemScores: allOnes, scores: { total: 30 } })
  });
  assert.strictEqual(malformedProjection.status, 400);
  const mismatchedProjection = await fetch(`${baseUrl}/api/severity/v2/assessments`, {
    method: "POST",
    headers: writeHeaders(context, { "Idempotency-Key": "score-mismatch-1" }),
    body: JSON.stringify({
      patientId,
      encounterId,
      status: "completed",
      itemScores: allOnes,
      scores: { positive: 7, negative: 7, general: 16, total: 31 }
    })
  });
  assert.strictEqual(mismatchedProjection.status, 400);
  const matchingProjection = await fetch(`${baseUrl}/api/severity/v2/assessments`, {
    method: "POST",
    headers: writeHeaders(context, { "Idempotency-Key": "score-match-case-1" }),
    body: JSON.stringify({
      patientId,
      encounterId,
      status: "completed",
      itemScores: allOnes,
      scores: { positive: 7, negative: 7, general: 16, total: 30 }
    })
  });
  assert.strictEqual(matchingProjection.status, 201);
  assert.deepStrictEqual((await matchingProjection.json()).scores, deriveScores(allOnes));
  const partialCompleted = await fetch(`${baseUrl}/api/severity/v2/assessments`, {
    method: "POST",
    headers: writeHeaders(context, { "Idempotency-Key": "partial-case-1" }),
    body: JSON.stringify({ patientId, encounterId, status: "completed", itemScores: { P1: 4 } })
  });
  assert.strictEqual(partialCompleted.status, 400);
  const inProgress = await fetch(`${baseUrl}/api/severity/v2/assessments`, {
    method: "POST",
    headers: writeHeaders(context, { "Idempotency-Key": "incomplete-case-1" }),
    body: JSON.stringify({ patientId, encounterId, status: "in-progress", itemScores: { P1: 4 } })
  });
  assert.strictEqual(inProgress.status, 201);
  const inProgressBody = await inProgress.json();
  assert.strictEqual(inProgressBody.evaluation.state, "incomplete");
  assert.strictEqual(inProgressBody.evaluation.scores, null);
  assert.strictEqual(inProgressBody.evaluation.missingItemCodes.length, 29);

  const completedBody = JSON.stringify({ patientId, encounterId, status: "completed", itemScores: allOnes });
  const created = await fetch(`${baseUrl}/api/severity/v2/assessments`, {
    method: "POST",
    headers: writeHeaders(context, { "Idempotency-Key": "completed-case-1" }),
    body: completedBody
  });
  assert.strictEqual(created.status, 201);
  const createdEtag = created.headers.get("etag");
  const assessment = await created.json();
  assert.deepStrictEqual(assessment.scores, { positive: 7, negative: 7, general: 16, total: 30 });

  const replay = await fetch(`${baseUrl}/api/severity/v2/assessments`, {
    method: "POST",
    headers: writeHeaders(context, { "Idempotency-Key": "completed-case-1" }),
    body: JSON.stringify({ itemScores: allOnes, status: "completed", encounterId, patientId })
  });
  assert.strictEqual(replay.status, 201);
  assert.deepStrictEqual(await replay.json(), assessment);

  const conflict = await fetch(`${baseUrl}/api/severity/v2/assessments`, {
    method: "POST",
    headers: writeHeaders(context, { "Idempotency-Key": "completed-case-1" }),
    body: JSON.stringify({ patientId, encounterId, status: "skipped", itemScores: {} })
  });
  assert.strictEqual(conflict.status, 409);

  const read = await fetch(`${baseUrl}/api/severity/v2/assessments/${assessment.assessmentId}`, { headers: { Cookie: "session=psychiatrist" } });
  assert.strictEqual(read.status, 200);
  assert.strictEqual(read.headers.get("etag"), createdEtag);

  const updates = await Promise.all(["skipped", "in-progress"].map(status => fetch(`${baseUrl}/api/severity/v2/assessments/${assessment.assessmentId}`, {
    method: "PUT",
    headers: writeHeaders(context, { "If-Match": createdEtag }),
    body: JSON.stringify({ status, itemScores: status === "skipped" ? {} : { P1: 4 } })
  })));
  assert.deepStrictEqual(updates.map(response => response.status).sort(), [200, 412]);

  const allowedPreflight = await fetch(`${baseUrl}/api/severity/v2/assessments`, {
    method: "OPTIONS",
    headers: { Origin: allowedOrigin }
  });
  assert.strictEqual(allowedPreflight.status, 204);
  assert.strictEqual(allowedPreflight.headers.get("access-control-allow-origin"), allowedOrigin);
  assert.strictEqual(allowedPreflight.headers.get("access-control-allow-credentials"), "true");
  const rejectedPreflight = await fetch(`${baseUrl}/api/severity/v2/assessments`, {
    method: "OPTIONS",
    headers: { Origin: "http://untrusted.test" }
  });
  assert.strictEqual(rejectedPreflight.status, 403);

  assert.ok(authRequests.some(request => request.url === "/api/auth/v2/session" && request.cookie.includes("session=psychiatrist")));
  await new Promise(resolve => authServer.close(resolve));
  const unavailableReadiness = await fetch(`${baseUrl}/readyz`);
  assert.strictEqual(unavailableReadiness.status, 503);
  assert.strictEqual((await unavailableReadiness.json()).code, "SEVERITY_NOT_READY");
  console.log("SUCCESS: Severity v2 auth, CSRF, CORS, ETag, idempotency, and health checks passed");
} finally {
  server.kill("SIGTERM");
  if (authServer.listening) await new Promise(resolve => authServer.close(resolve));
  fs.rmSync(dataDir, { recursive: true, force: true });
}
