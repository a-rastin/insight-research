import assert from "assert";
import { execFile } from "child_process";
import fs from "fs";
import http from "http";
import os from "os";
import path from "path";
import { ITEM_CODES } from "./panss.js";
import { PANSS_ITEMS, createSeverityClient, normalizeApiBasePath, normalizeContext } from "./public/severity-ui.js";

const html = fs.readFileSync("public/index.html", "utf8");
const uiSource = fs.readFileSync("public/severity-ui.js", "utf8");

assert.strictEqual(PANSS_ITEMS.length, 30, "the UI must render all 30 PANSS items");
assert.deepStrictEqual(PANSS_ITEMS.map(item => item.code), ITEM_CODES);
assert.match(uiSource, /role="progressbar"/);
assert.match(uiSource, /createElement\("fieldset"\)/);
assert.match(uiSource, /aria-pressed/);
assert.match(uiSource, /aria-label/);
assert.match(uiSource, /window\.InsightSeverity = Object\.freeze\(\{ mount, unmount \}\)/);
assert.match(html, /min-width: 44px; min-height: 44px/);
assert.match(html, /:focus-visible/);
assert.match(html, /prefers-reduced-motion: reduce/);
assert.match(html, /--urgent: #b91c1c/);
assert.match(uiSource, /Passed \/ skipped\. No PANSS score was inferred\./);
assert.match(uiSource, /Completed\. Scores below were verified and persisted by the Severity server\./);
assert.match(uiSource, /The error remains visible until another action succeeds\./);
assert.doesNotMatch(uiSource, /setTimeout|localStorage|sessionStorage|patient[_-]?code|history\./i);
assert.doesNotMatch(html, /localStorage|sessionStorage|patient[_-]?code|history\./i);
assert.strictEqual(normalizeApiBasePath(), "/api/severity/v2");
assert.throws(() => normalizeApiBasePath("http://severity.test/api"), /gateway-relative/);
assert.throws(() => normalizeContext(null), /host-provided/);

function relativeLuminance(hex) {
  const channels = hex.match(/[0-9a-f]{2}/gi).map(value => parseInt(value, 16) / 255).map(value =>
    value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
  );
  return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
}

function contrast(foreground, background) {
  const values = [relativeLuminance(foreground), relativeLuminance(background)].sort((a, b) => b - a);
  return (values[0] + 0.05) / (values[1] + 0.05);
}

assert.ok(contrast("087f74", "ffffff") >= 4.5, "primary button text contrast must meet WCAG AA");
assert.ok(contrast("b91c1c", "fef2f2") >= 4.5, "urgent text contrast must meet WCAG AA");
assert.ok(contrast("92400e", "fffbeb") >= 4.5, "warning text contrast must meet WCAG AA");

const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), "severity-ui-"));
const port = 42000 + process.pid % 10000;
const authPort = port + 1;
const origin = `http://127.0.0.1:${port}`;
const patientId = "51111111-1111-4111-8111-111111111111";
const encounterId = "52222222-2222-4222-8222-222222222222";
const actorId = "53333333-3333-4333-8333-333333333333";
const sessionId = "54444444-4444-4444-8444-444444444444";
const allOnes = Object.fromEntries(ITEM_CODES.map(code => [code, 1]));

const authServer = http.createServer((req, res) => {
  if (req.url !== "/api/auth/v2/session" || !req.headers.cookie?.includes("session=psychiatrist")) {
    res.writeHead(401, { "Content-Type": "application/json" }).end("{}");
    return;
  }
  res.writeHead(200, { "Content-Type": "application/json", "X-Schema-Version": "2.0.0" });
  res.end(JSON.stringify({
    authenticated: true,
    authorized: true,
    interfaceVersion: "2.0.0",
    session: { id: sessionId, active: true, expiresAt: "2999-01-01T00:00:00Z" },
    user: { id: actorId, username: "clinician", role: "psychiatrist" },
    gates: { passwordChangeRequired: false, disclaimerRequired: false, disclaimerVersion: "test-v1" },
    compatibility: { legacyUserId: 1, legacyRole: "user" }
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
    SEVERITY_CSRF_SECRET: "test-only-severity-csrf-secret-32-characters"
  }
});
let serverError = "";
server.stderr.on("data", chunk => { serverError += chunk.toString(); });

async function waitForServer() {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      if ((await fetch(`${origin}/healthz`)).ok) return;
    } catch {}
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error(`server did not start: ${serverError}`);
}

let cookie = "session=psychiatrist";
const requestedPaths = [];
async function browserFetch(relativePath, options = {}) {
  assert.match(relativePath, /^\/api\/severity\/v2\//, "UI requests must remain gateway-relative");
  requestedPaths.push(relativePath);
  const headers = new Headers(options.headers || {});
  headers.set("Cookie", cookie);
  const response = await fetch(`${origin}${relativePath}`, { ...options, headers });
  const setCookie = response.headers.get("set-cookie");
  if (setCookie) cookie += `; ${setCookie.split(";", 1)[0]}`;
  return response;
}

try {
  await waitForServer();
  const context = normalizeContext({ patientId, encounterId });
  const client = createSeverityClient({ fetchImpl: browserFetch });
  const completed = await client.save({ context, assessment: null, etag: null, status: "completed", itemScores: allOnes });
  assert.strictEqual(completed.assessment.status, "completed");
  assert.deepStrictEqual(completed.assessment.scores, { positive: 7, negative: 7, general: 16, total: 30 });
  assert.ok(completed.etag);

  const loaded = await client.load(completed.assessment.assessmentId);
  assert.deepStrictEqual(loaded.assessment, completed.assessment);

  const passed = await client.save({ context, assessment: null, etag: null, status: "skipped", itemScores: {} });
  assert.strictEqual(passed.assessment.status, "skipped");
  assert.strictEqual(passed.assessment.evaluation.state, "passed");
  assert.strictEqual(passed.assessment.scores, null);

  await assert.rejects(
    client.save({ context, assessment: null, etag: null, status: "completed", itemScores: { P1: 1 } }),
    /requires the exact 30-item PANSS set/i
  );
  assert.ok(requestedPaths.includes("/api/severity/v2/csrf"));
  console.log("SUCCESS: Severity UI lifecycle, privacy, accessibility, and real HTTP result checks passed");
} finally {
  server.kill("SIGTERM");
  await new Promise(resolve => authServer.close(resolve));
  fs.rmSync(dataDir, { recursive: true, force: true });
}
