import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const html = readFileSync(resolve(here, "index.html"), "utf8");

test("dashboard view renders with activate control", () => {
  assert.match(html, /id="dashboardView"/);
  assert.match(html, /id="activateModuleButton"[^>]*type="button"/);
  assert.match(html, /id="dashboardTitle"[\s\S]*?>Add New Patient</);
});

test("form exposes demographics + clinical fields", () => {
  for (const name of [
    "firstName",
    "lastName",
    "sex",
    "dob",
    "phoneNumber",
    "presentingComplaint",
    "provisionalDiagnosis",
    "treatmentHistory",
    "allergies",
    "currentMedications",
    "suicidality",
    "substanceUse"
  ]) {
    assert.ok(html.includes(`name="${name}"`), `missing form field: ${name}`);
  }
});

test("status message exposes aria-live region", () => {
  assert.match(html, /id="statusMessage"[^>]*role="status"[^>]*aria-live="polite"/);
});
