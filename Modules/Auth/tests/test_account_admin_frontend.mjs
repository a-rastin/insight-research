import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const html = readFileSync(new URL("../static/accounts.html", import.meta.url), "utf8");

test("account administration browser contract", () => {
  assert.match(html, /<form id="create-form">/);
  assert.match(html, /<table>/);
  assert.match(html, /scope="col"/);
  assert.match(html, /role="status"/);
  assert.match(html, /prefers-reduced-motion/);
  assert.match(html, /POST/);
  assert.match(html, /PATCH/);
  assert.match(html, /\/api\/auth\/v2\/admin\/accounts/);
  assert.match(html, /Previous/);
  assert.match(html, /Next/);
  assert.match(html, /Disable/);
  assert.match(html, /Reset password/);
  assert.match(html, /Request failed \(\$\{response.status\}\)/);
  assert.doesNotMatch(html, /localStorage|sessionStorage|console\.log/);
});
