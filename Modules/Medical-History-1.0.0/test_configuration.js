const assert = require("node:assert/strict");
const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const root = fs.mkdtempSync(path.join(os.tmpdir(), "medical-history-configuration-"));
try {
  const databasePath = path.join(root, "medical-history.db");
  const result = spawnSync(process.execPath, ["server.js"], {
    cwd: __dirname,
    encoding: "utf8",
    env: { ...process.env, NODE_ENV: "production", MEDICAL_HISTORY_DB_PATH: databasePath, MEDICAL_HISTORY_AUTH_BYPASS: "true" }
  });
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /MEDICAL_HISTORY_CSRF_SECRET must contain at least 32 characters/);
  assert.equal(fs.existsSync(databasePath), false);
  console.log("SUCCESS: Medical History production configuration fails closed without secrets or auth bypass");
} finally {
  fs.rmSync(root, { recursive: true, force: true });
}
