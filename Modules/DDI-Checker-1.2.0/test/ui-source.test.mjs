import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, "..");

test("admin workflow and report upload controls are reachable", () => {
  const html = fs.readFileSync(path.join(projectRoot, "index.html"), "utf8");
  assert.match(html, /data-view="admin"/);
  assert.match(html, /class="admin-shortcut"/);
  assert.match(html, /id="uploadReportForm"/);
  assert.match(html, /type="file"/);
});

test("controls have visible focus, labels, and reduced-motion support", () => {
  const html = fs.readFileSync(path.join(projectRoot, "index.html"), "utf8");
  const css = fs.readFileSync(path.join(projectRoot, "src", "styles.css"), "utf8");
  for (const id of ["reviewSearch", "reportFileInput", "newDrugA", "newDrugB", "newSeverity", "newEffect", "newRecommendation"]) {
    assert.match(html, new RegExp(`<label for="${id}">`));
  }
  assert.match(css, /:focus-visible/);
  assert.match(css, /prefers-reduced-motion: reduce/);
});

test("dashboard shows session code and result export controls", () => {
  const html = fs.readFileSync(path.join(projectRoot, "index.html"), "utf8");
  const app = fs.readFileSync(path.join(projectRoot, "src", "app.js"), "utf8");
  assert.match(html, /id="sessionCode"/);
  assert.match(html, /id="resultSummary"/);
  assert.match(html, /id="exportResultsButton"/);
  assert.match(app, /sessionStorage\.getItem/);
  assert.match(app, /ddi-results-\$\{sessionCode\}\.json/);
});

test("Evidence/source alert markup does not render sourceReportPath", () => {
  const app = fs.readFileSync(path.join(projectRoot, "src", "app.js"), "utf8");
  const evidenceTemplate = app.match(/<strong>Evidence\/source:<\/strong>[\s\S]*?<\/div>/)?.[0] || "";
  assert.ok(evidenceTemplate);
  assert.doesNotMatch(evidenceTemplate, /sourceReportPath/);
  assert.match(evidenceTemplate, /evidenceSource/);
  assert.match(evidenceTemplate, /evidenceExcerpt/);
});


test("activation is blocked and clearly reported when no interactions are approved", () => {
  const app = fs.readFileSync(path.join(projectRoot, "src", "app.js"), "utf8");
  assert.match(app, /if \(!approved\)/);
  assert.doesNotMatch(app, /activation_blocked_no_approved_records/);
  assert.match(app, /no approved interactions available/);
});

test("ambiguous medication identities are shown with candidate names and IDs", () => {
  const app = fs.readFileSync(path.join(projectRoot, "src", "app.js"), "utf8");
  assert.match(app, /result\.ambiguous/);
  assert.match(app, /Choose one identity/);
  assert.match(app, /drug\.id/);
});
test("override rationale uses a cancelable required form and never window.prompt", () => {
  const html = fs.readFileSync(path.join(projectRoot, "index.html"), "utf8");
  const app = fs.readFileSync(path.join(projectRoot, "src", "app.js"), "utf8");
  assert.match(html, /<dialog id="overrideDialog"/);
  assert.match(html, /id="overrideReason"[^>]*maxlength="500"[^>]*required/);
  assert.match(app, /overrideDialog\.addEventListener\("cancel"/);
  assert.match(app, /pendingOverrideAlertId = null/);
  assert.doesNotMatch(app, /window\.prompt/);
});

test("storage failures are persistent and KB mutations roll back", () => {
  const html = fs.readFileSync(path.join(projectRoot, "index.html"), "utf8");
  const app = fs.readFileSync(path.join(projectRoot, "src", "app.js"), "utf8");
  assert.match(html, /id="storageFailure"[^>]*role="alert"/);
  assert.match(app, /if \(!persistKb\(\)\) \{\s*kb = snapshot/);
  assert.match(app, /if \(!writeJson\(STORAGE_KEYS\.meds, medications\)\.ok\) \{ medications = previous; return; \}/);
  assert.match(app, /quota_exceeded/);
});

