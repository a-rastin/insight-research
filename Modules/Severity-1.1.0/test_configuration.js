import assert from "assert";
import { spawnSync } from "child_process";
import fs from "fs";
import os from "os";
import path from "path";

const root = fs.mkdtempSync(path.join(os.tmpdir(), "severity-configuration-"));
try {
  const result = spawnSync("node", ["server.js"], {
    encoding: "utf8",
    env: {
      ...process.env,
      NODE_ENV: "production",
      SEVERITY_DB_PATH: path.join(root, "severity.db"),
      SEVERITY_DATA_FILE: path.join(root, "missing-v1.json"),
      SEVERITY_V2_DATA_FILE: path.join(root, "missing-v2.json"),
      SEVERITY_AUTH_BYPASS: "true"
    }
  });
  assert.notStrictEqual(result.status, 0);
  assert.match(result.stderr, /SEVERITY_CSRF_SECRET must contain at least 32 characters/);
  assert.strictEqual(fs.existsSync(path.join(root, "severity.db")), false);
  console.log("SUCCESS: production cannot start with development defaults or an auth bypass flag");
} finally {
  fs.rmSync(root, { recursive: true, force: true });
}
