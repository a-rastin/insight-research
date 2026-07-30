import assert from "assert";
import { execFile } from "child_process";
import fs from "fs";
import http from "http";
import os from "os";
import path from "path";

const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), "severity-legacy-"));
const port = 45000 + process.pid % 10000;
const authPort = port + 1;
const authServer = http.createServer((_req, res) => res.writeHead(401).end());
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

try {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      if ((await fetch(`http://127.0.0.1:${port}/healthz`)).ok) break;
    } catch {}
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  if (server.exitCode !== null) throw new Error(`server did not start: ${serverError}`);
  const legacy = await fetch(`http://127.0.0.1:${port}/api/severity/TEST-PATIENT-99`);
  assert.strictEqual(legacy.status, 410);
  assert.strictEqual((await legacy.json()).code, "SEVERITY_LEGACY_IDENTITY_UNMAPPED");
  console.log("SUCCESS: legacy records fail closed without canonical identity");
} finally {
  server.kill("SIGTERM");
  await new Promise(resolve => authServer.close(resolve));
  fs.rmSync(dataDir, { recursive: true, force: true });
}
