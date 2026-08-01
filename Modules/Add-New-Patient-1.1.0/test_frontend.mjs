import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const html = readFileSync(resolve(here, "index.html"), "utf8");
const css = readFileSync(resolve(here, "styles.css"), "utf8");

test("dashboard view renders with activate control", () => {
  assert.match(html, /id="dashboardView"/);
  assert.match(html, /id="activateModuleButton"[^>]*type="button"/);
  assert.match(html, /id="dashboardTitle"[\s\S]*?>Add New Patient</);
});

test("embedded assets resolve beneath canonical module path", () => {
  assert.match(html, /href="\.\/styles\.css"/);
  assert.match(html, /src="\.\/app\.js"/);
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

test("interactive UI supports focus and reduced motion", () => {
  assert.match(css, /:focus-visible/);
  assert.match(css, /prefers-reduced-motion: reduce/);
  assert.match(css, /min-height: 44px/);
});

test("follow-up UI exposes search, history, and owner capture", () => {
  assert.match(html, /id="followUpSearchForm"/);
  assert.match(html, /id="encounterHistory"/);
  assert.match(html, /id="planHistory"/);
  assert.match(html, /id="followUpForm"/);
});
