import assert from "node:assert/strict";
import { createHash, createHmac, randomUUID } from "node:crypto";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { createDdiServer } from "../../../deploy/ddi-static-server.mjs";

const moduleRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const secret = "test-only-ddi-service-secret-000000000000";
const keyId = "tp-ddi-test-v1";

function hash(value) {
  return createHash("sha256").update(value).digest("hex");
}

function stableJson(value) {
  if (Array.isArray(value)) return `[${value.map(stableJson).join(",")}]`;
  if (value && typeof value === "object") return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stableJson(value[key])}`).join(",")}}`;
  return JSON.stringify(value);
}

function medicationHash(medications) {
  const values = medications.map(({ inputIndex: _, ...item }) => item)
    .sort((a, b) => stableJson(a).localeCompare(stableJson(b)));
  return `sha256:${hash(stableJson({ schemaVersion: "1.0.0", medications: values }))}`;
}

function signedHeaders(body, cookie = "insight_session=valid") {
  const timestamp = String(Math.floor(Date.now() / 1000));
  const nonce = createHash("sha256").update(randomUUID()).digest("hex").slice(0, 32);
  const requestId = randomUUID();
  const correlationId = randomUUID();
  const contentHash = hash(body);
  const canonical = ["INSIGHT-HMAC-V1", "treatment-plan", keyId, timestamp, nonce, "ddi-checker", "POST",
    "/api/ddi/v1/checks", contentHash, requestId, correlationId, ""].join("\n");
  return {
    "Content-Type": "application/json",
    "X-Schema-Version": "1.0.0",
    "Idempotency-Key": JSON.parse(body).idempotencyKey,
    "X-Request-ID": requestId,
    "X-Correlation-ID": correlationId,
    "X-Insight-Service-ID": "treatment-plan",
    "X-Insight-Key-ID": keyId,
    "X-Insight-Timestamp": timestamp,
    "X-Insight-Nonce": nonce,
    "X-Insight-Content-SHA256": contentHash,
    "X-Insight-Signature": `v1=${createHmac("sha256", secret).update(canonical).digest("base64url")}`,
    Cookie: cookie,
  };
}

function session(role) {
  return {
    authenticated: true,
    authorized: true,
    interfaceVersion: "2.0.0",
    session: { id: "00000000-0000-4000-8000-000000000201", active: true },
    user: { id: "00000000-0000-4000-8000-000000000202", role },
    gates: { passwordChangeRequired: false, disclaimerRequired: false },
  };
}

async function listen(server) {
  await new Promise((resolve, reject) => server.listen(0, "127.0.0.1", resolve).once("error", reject));
  return `http://127.0.0.1:${server.address().port}`;
}

async function activeRegistry() {
  const registry = await mkdtemp(join(tmpdir(), "ddi-rest-"));
  const fixture = JSON.parse(await readFile(join(moduleRoot, "test", "fixtures", "kb", "valid-pending.json"), "utf8"));
  Object.assign(fixture, {
    knowledgeBaseId: "00000000-0000-4000-8000-000000000101",
    version: "1.2.3",
    status: "active_clinical",
    activatedAt: "2026-07-31T08:00:00Z",
    clinicalUse: { allowedForProduction: true },
  });
  Object.assign(fixture.interactions[0], {
    knowledgeBaseVersion: "1.2.3",
    reviewStatus: "approved",
    reviewedBy: "pharmacist-reviewer",
    reviewedAt: "2026-07-31T07:00:00Z",
  });
  await writeFile(join(registry, "active-kb.json"), JSON.stringify(fixture));
  return registry;
}

test("POST checks uses active reviewed KB, fails closed, and replays idempotently", async (t) => {
  const registryRoot = await activeRegistry();
  const auth = createServer((request, response) => {
    if (!request.headers.cookie) {
      response.writeHead(401);
      return response.end();
    }
    response.writeHead(200, { "Content-Type": "application/json", "X-Schema-Version": "2.0.0" });
    response.end(JSON.stringify(session("psychiatrist")));
  });
  const authUrl = `${await listen(auth)}/api/auth/v2/session`;
  const server = createDdiServer({ root: moduleRoot, registryRoot, authSessionUrl: authUrl, keyId, secret });
  const base = await listen(server);
  t.after(async () => {
    await Promise.all([new Promise((resolve) => server.close(resolve)), new Promise((resolve) => auth.close(resolve))]);
    await rm(registryRoot, { recursive: true, force: true });
  });

  const ready = await fetch(`${base}/readyz`);
  assert.equal(ready.status, 200);
  assert.equal(ready.headers.get("x-schema-version"), "1.0.0");

  const medications = [
    { inputIndex: 0, source: "current", originalText: "Alpha", medicationCode: "1", codeSystem: "RxNorm" },
    { inputIndex: 1, source: "proposed", originalText: "Unmapped medication" },
  ];
  const idempotencyKey = `sha256:${"a".repeat(64)}`;
  const body = JSON.stringify({
    schemaVersion: "1.0.0",
    idempotencyKey,
    planSemanticHash: `sha256:${"b".repeat(64)}`,
    medicationSetHash: medicationHash(medications),
    medications,
  });
  const first = await fetch(`${base}/api/ddi/v1/checks`, { method: "POST", headers: signedHeaders(body), body });
  const result = await first.json();
  assert.equal(first.status, 201);
  assert.equal(first.headers.get("x-schema-version"), "1.0.0");
  assert.equal(result.coverageStatus, "incomplete");
  assert.equal(result.resolvedMedications[0].conceptId, "rxnorm:1");
  assert.equal(result.unresolvedMedications[0].status, "unknown");
  assert.deepEqual(result.pairsChecked, []);
  assert.deepEqual(result.alerts, []);
  assert.equal(result.knowledgeBaseId, "00000000-0000-4000-8000-000000000101");
  assert.equal(result.knowledgeBaseVersion, "1.2.3");
  assert.match(result.knowledgeBaseContentHash, /^sha256:[a-f0-9]{64}$/);

  const replay = await fetch(`${base}/api/ddi/v1/checks`, { method: "POST", headers: signedHeaders(body), body });
  assert.equal(replay.status, 201);
  assert.deepEqual(await replay.json(), result);

  const completeMedications = [
    { inputIndex: 0, source: "current", originalText: "Alpha" },
    { inputIndex: 1, source: "proposed", originalText: "Beta" },
  ];
  const completeBody = JSON.stringify({
    schemaVersion: "1.0.0",
    idempotencyKey: `sha256:${"e".repeat(64)}`,
    planSemanticHash: `sha256:${"f".repeat(64)}`,
    medicationSetHash: medicationHash(completeMedications),
    medications: completeMedications,
  });
  const complete = await fetch(`${base}/api/ddi/v1/checks`, { method: "POST", headers: signedHeaders(completeBody), body: completeBody });
  const completeResult = await complete.json();
  assert.equal(complete.status, 201);
  assert.equal(completeResult.coverageStatus, "complete");
  assert.deepEqual(completeResult.pairsChecked, [{ medicationInputIndexes: [0, 1] }]);
  assert.equal(completeResult.alerts.length, 1);
  assert.equal(completeResult.alerts[0].severity, "high");
  assert.match(completeResult.alerts[0].alertId, /^[0-9a-f-]{36}$/);
});

test("checks reject missing service auth and non-psychiatrist sessions", async (t) => {
  const registryRoot = await activeRegistry();
  const auth = createServer((_request, response) => {
    response.writeHead(200, { "Content-Type": "application/json", "X-Schema-Version": "2.0.0" });
    response.end(JSON.stringify(session("admin")));
  });
  const server = createDdiServer({
    root: moduleRoot,
    registryRoot,
    authSessionUrl: `${await listen(auth)}/api/auth/v2/session`,
    keyId,
    secret,
  });
  const base = await listen(server);
  t.after(async () => {
    await Promise.all([new Promise((resolve) => server.close(resolve)), new Promise((resolve) => auth.close(resolve))]);
    await rm(registryRoot, { recursive: true, force: true });
  });
  const medications = [{ inputIndex: 0, source: "proposed", originalText: "Alpha" }];
  const body = JSON.stringify({
    schemaVersion: "1.0.0",
    idempotencyKey: `sha256:${"c".repeat(64)}`,
    planSemanticHash: `sha256:${"d".repeat(64)}`,
    medicationSetHash: medicationHash(medications),
    medications,
  });

  const unsigned = await fetch(`${base}/api/ddi/v1/checks`, { method: "POST", headers: { "Content-Type": "application/json" }, body });
  assert.equal(unsigned.status, 401);
  assert.equal((await unsigned.json()).code, "DDI_UNAUTHENTICATED");
  const forbidden = await fetch(`${base}/api/ddi/v1/checks`, { method: "POST", headers: signedHeaders(body), body });
  assert.equal(forbidden.status, 403);
  assert.equal((await forbidden.json()).code, "DDI_FORBIDDEN");
});

test("readiness rejects pending knowledge without promoting its records", async (t) => {
  const registryRoot = await mkdtemp(join(tmpdir(), "ddi-pending-"));
  await writeFile(join(registryRoot, "active-kb.json"), await readFile(join(moduleRoot, "test", "fixtures", "kb", "valid-pending.json")));
  const server = createDdiServer({ root: moduleRoot, registryRoot, authSessionUrl: "http://127.0.0.1:1/session", keyId, secret });
  const base = await listen(server);
  t.after(async () => {
    await new Promise((resolve) => server.close(resolve));
    await rm(registryRoot, { recursive: true, force: true });
  });
  const response = await fetch(`${base}/readyz`);
  assert.equal(response.status, 503);
  assert.equal((await response.json()).reason, "active-knowledge-base-invalid");
});
