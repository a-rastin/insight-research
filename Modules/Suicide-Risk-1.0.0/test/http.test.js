const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const http = require("node:http");
const os = require("node:os");
const path = require("node:path");

const directory = fs.mkdtempSync(path.join(os.tmpdir(), "suicide-risk-http-"));
const port = 45500 + (process.pid % 400);
const authPort = port + 450;
const base = `http://127.0.0.1:${port}`;
const actorId = "33333333-3333-4333-8333-333333333333";
const sessionId = "44444444-4444-4444-8444-444444444444";
const patientId = "11111111-1111-4111-8111-111111111111";
const encounterId = "22222222-2222-4222-8222-222222222222";
const origin = "http://clinical.test";
let child;

const authServer = http.createServer((req, res) => {
  if (req.url !== "/api/auth/v2/session") return res.writeHead(404).end();
  const cookie = req.headers.cookie || "";
  if (!cookie.includes("session=active") && !cookie.includes("session=admin")) return res.writeHead(401).end("{}");
  const role = cookie.includes("session=admin") ? "admin" : "psychiatrist";
  res.writeHead(200, { "Content-Type": "application/json", "X-Schema-Version": "2.0.0" });
  res.end(JSON.stringify({
    authenticated: true,
    authorized: true,
    interfaceVersion: "2.0.0",
    session: { id: sessionId, active: true, expiresAt: "2999-01-01T00:00:00Z" },
    user: { id: actorId, username: "clinician", role },
    gates: { passwordChangeRequired: false, disclaimerRequired: false, disclaimerVersion: "test" },
    compatibility: { legacyUserId: 1, legacyRole: "user" }
  }));
});

async function wait() {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try { if ((await fetch(`${base}/healthz`)).ok) return; } catch {}
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error("Suicide Risk server did not start");
}

async function csrf() {
  const response = await fetch(`${base}/api/suicide-risk/v1/csrf`, { headers: { Cookie: "session=active" } });
  const value = await response.json();
  return { token: value.token, cookie: `session=active; suicide_risk_csrf=${value.token}` };
}

function headers(csrfContext, extra = {}) {
  return { "Content-Type": "application/json", "X-Schema-Version": "1.0.0", "X-CSRF-Token": csrfContext.token, Cookie: csrfContext.cookie, ...extra };
}

(async () => {
  try {
    await new Promise((resolve) => authServer.listen(authPort, "127.0.0.1", resolve));
    child = spawn(process.execPath, ["server.js"], {
      cwd: path.join(__dirname, ".."),
      env: {
        ...process.env,
        PORT: String(port),
        SUICIDE_RISK_DATA_DIR: directory,
        SUICIDE_RISK_DB_PATH: path.join(directory, "risk.db"),
        SUICIDE_RISK_AUTH_BASE_URL: `http://127.0.0.1:${authPort}`,
        SUICIDE_RISK_CSRF_SECRET: "test-suicide-risk-csrf-secret-32-characters",
        SUICIDE_RISK_ALLOWED_ORIGINS: origin
      },
      stdio: "ignore"
    });
    await wait();

    assert.equal((await fetch(`${base}/readyz`)).status, 200);
    assert.equal((await fetch(`${base}/api/suicide-risk/v1/contract`)).status, 200);
    for (const name of ["document", "schema", "openapi"]) assert.equal((await fetch(`${base}/api/suicide-risk/v1/contract/${name}`)).status, 200);
    assert.equal((await fetch(`${base}/api/suicide-risk/v1/assessments/${patientId}`)).status, 401);
    assert.equal((await fetch(`${base}/api/suicide-risk/v1/csrf`, { headers: { Cookie: "session=admin" } })).status, 403);

    const token = await csrf();
    const request = { patientId, encounterId, riskState: "unknown", actor: { actorId, role: "psychiatrist" } };
    const noCsrf = await fetch(`${base}/api/suicide-risk/v1/assessments`, {
      method: "POST", headers: { "Content-Type": "application/json", "X-Schema-Version": "1.0.0", "Idempotency-Key": "missing-csrf-case", Cookie: "session=active" }, body: JSON.stringify(request)
    });
    assert.equal(noCsrf.status, 403);

    const createdResponse = await fetch(`${base}/api/suicide-risk/v1/assessments`, {
      method: "POST", headers: headers(token, { "Idempotency-Key": "suicide-risk-case-0001" }), body: JSON.stringify(request)
    });
    assert.equal(createdResponse.status, 201);
    const firstEtag = createdResponse.headers.get("etag");
    const created = await createdResponse.json();
    assert.equal(created.riskState, "unknown");
    assert.equal(created.riskScore, null);
    assert.equal(created.safetyDisposition.code, "TP_SUICIDE_RISK_UNAVAILABLE");
    assert.equal(created.instrument.completionClaimed, false);

    const replay = await fetch(`${base}/api/suicide-risk/v1/assessments`, {
      method: "POST", headers: headers(token, { "Idempotency-Key": "suicide-risk-case-0001" }), body: JSON.stringify(request)
    });
    assert.equal(replay.status, 201);
    assert.deepEqual(await replay.json(), created);
    const conflict = await fetch(`${base}/api/suicide-risk/v1/assessments`, {
      method: "POST", headers: headers(token, { "Idempotency-Key": "suicide-risk-case-0001" }), body: JSON.stringify({ ...request, riskState: "unavailable" })
    });
    assert.equal(conflict.status, 409);

    const forbiddenState = await fetch(`${base}/api/suicide-risk/v1/assessments`, {
      method: "POST", headers: headers(token, { "Idempotency-Key": "suicide-risk-case-0002" }), body: JSON.stringify({ ...request, riskState: "low-risk", score: 2 })
    });
    assert.equal(forbiddenState.status, 400);
    assert.doesNotMatch(await forbiddenState.text(), new RegExp(patientId));

    const update = { riskState: "imminent-suicide-risk", actor: { actorId, role: "psychiatrist" } };
    const updates = await Promise.all([0, 1].map(() => fetch(`${base}/api/suicide-risk/v1/assessments/${created.assessmentId}`, {
      method: "PUT", headers: headers(token, { "If-Match": firstEtag }), body: JSON.stringify(update)
    })));
    assert.deepEqual(updates.map((response) => response.status).sort(), [200, 412]);
    const successfulUpdate = updates.find((response) => response.status === 200);
    const urgent = await successfulUpdate.json();
    assert.equal(urgent.safetyDisposition.code, "TP_EMERGENCY_ACTION_REQUIRED");
    assert.equal(urgent.safetyDisposition.overrideAllowed, false);
    assert.equal(urgent.safetyDisposition.persistentUntilResolved, true);

    const latest = await fetch(`${base}/api/suicide-risk/v1/encounters/${encounterId}/assessments/latest`, { headers: { Cookie: "session=active" } });
    assert.equal(latest.status, 200);
    assert.equal((await latest.json()).riskState, "imminent-suicide-risk");
    const snapshotResponse = await fetch(`${base}/api/suicide-risk/v1/encounters/${encounterId}/snapshot`, { headers: { Cookie: "session=active" } });
    const snapshot = await snapshotResponse.json();
    assert.equal(snapshotResponse.status, 200);
    assert.equal(snapshot.source.owner, "suicide-risk");
    assert.equal(snapshot.source.resourceVersion, 2);
    assert.match(snapshot.source.contentSha256, /^[0-9a-f]{64}$/);
    assert.equal(snapshot.assessment.riskState, "imminent-suicide-risk");

    const cors = await fetch(`${base}/api/suicide-risk/v1/assessments`, { method: "OPTIONS", headers: { Origin: origin } });
    assert.equal(cors.status, 204);
    assert.equal(cors.headers.get("access-control-allow-credentials"), "true");
    assert.equal((await fetch(`${base}/api/suicide-risk/v1/assessments`, { method: "OPTIONS", headers: { Origin: "http://untrusted.test" } })).status, 403);

    await new Promise((resolve) => authServer.close(resolve));
    assert.equal((await fetch(`${base}/readyz`)).status, 503);
    console.log("SUCCESS: Suicide Risk HTTP auth, CSRF, state, urgent, ETag, idempotency, snapshot, CORS, and readiness checks passed");
  } finally {
    if (child) child.kill("SIGTERM");
    if (authServer.listening) await new Promise((resolve) => authServer.close(resolve));
    fs.rmSync(directory, { recursive: true, force: true });
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
