import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
function workspaceModel(role) {
  const psychiatrist = role === "PSYCHIATRIST";
  return {
    displayName: psychiatrist ? "Dr. Mina Rahimi" : "Ari Morgan",
    currentDateTime: "2026-07-06T17:30:00Z",
    workspace: {
      kind: role,
      title: "Workspace",
      buttons: [
        { id: "add-new-patient", title: "Add New Patient", state: psychiatrist ? "available" : "unauthorized", reason: psychiatrist ? "Destination available." : "Not authorized for current role.", ...(psychiatrist ? { href: "/modules/add-new-patient" } : {}) },
        { id: "patient-follow-up", title: "Patient Follow-up", state: psychiatrist ? "available" : "unauthorized", reason: psychiatrist ? "Destination available." : "Not authorized for current role.", ...(psychiatrist ? { href: "/modules/patient-follow-up" } : {}) },
        { id: "diagnosis", title: "Diagnosis", state: psychiatrist ? "available" : "unauthorized", reason: psychiatrist ? "Destination available." : "Not authorized for current role.", ...(psychiatrist ? { href: "/modules/diagnosis/" } : {}) },
        { id: "severity", title: "Severity", state: psychiatrist ? "available" : "unauthorized", reason: psychiatrist ? "Destination available." : "Not authorized for current role.", ...(psychiatrist ? { href: "/modules/severity/" } : {}) },
        { id: "medical-history", title: "Medical History", state: psychiatrist ? "available" : "unauthorized", reason: psychiatrist ? "Destination available." : "Not authorized for current role.", ...(psychiatrist ? { href: "/modules/medical-history/" } : {}) },
        { id: "suicide-risk", title: "Suicide Risk", state: psychiatrist ? "available" : "unauthorized", reason: psychiatrist ? "Destination available." : "Not authorized for current role.", ...(psychiatrist ? { href: "/modules/suicide-risk/" } : {}) },
        { id: "treatment-plan", title: "Treatment Plan", state: psychiatrist ? "unavailable" : "unauthorized", reason: psychiatrist ? "Open a generated plan from its patient workflow." : "Not authorized for current role." },
        { id: "list-of-patients", title: "List of Patients", state: psychiatrist ? "unavailable" : "unauthorized", reason: psychiatrist ? "Destination is not available in this release." : "Not authorized for current role." },
        { id: "setting", title: "Setting", state: psychiatrist ? "unavailable" : "unauthorized", reason: psychiatrist ? "Destination is not available in this release." : "Not authorized for current role." },
        { id: "add-new-user", title: "Add New User", state: psychiatrist ? "unauthorized" : "available", reason: psychiatrist ? "Not authorized for current role." : "Destination available.", ...(!psychiatrist ? { href: "/modules/auth/accounts/new" } : {}) },
        { id: "logs", title: "Logs", state: psychiatrist ? "unauthorized" : "unavailable", reason: psychiatrist ? "Not authorized for current role." : "Destination is not available in this release." },
        { id: "backup", title: "Backup", state: psychiatrist ? "unauthorized" : "unavailable", reason: psychiatrist ? "Not authorized for current role." : "Destination is not available in this release." },
        { id: "list-of-users", title: "List of Users", state: psychiatrist ? "unauthorized" : "available", reason: psychiatrist ? "Not authorized for current role." : "Destination available.", ...(!psychiatrist ? { href: "/modules/auth/accounts" } : {}) },
        { id: "ddi-knowledge", title: "DDI Knowledge", state: psychiatrist ? "unauthorized" : "available", reason: psychiatrist ? "Not authorized for current role." : "Destination available.", ...(!psychiatrist ? { href: "/modules/ddi/", providerStatus: { readiness: { state: "not-ready", reason: "Production seam unavailable." }, clinicalUse: { state: "blocked", reason: "Production seam unavailable." } } } : {}) },
        { id: "bn-models", title: "BN Models", state: psychiatrist ? "unauthorized" : "available", reason: psychiatrist ? "Not authorized for current role." : "Destination available.", ...(!psychiatrist ? { href: "/modules/bn-manager", providerStatus: { readiness: { state: "ready", reason: "Provider reports ready." }, clinicalUse: { state: "blocked-by-manifest", reason: "Provider-reported model clinical-use status: blocked-by-manifest." } } } : {}) }
      ]
    }
  };
}

function fakeElement() {
  return {
    disabled: false,
    addEventListener() {}
  };
}

async function renderScenario(role) {
  const app = {
    innerHTML: "",
    querySelector() {
      return fakeElement();
    },
    querySelectorAll() {
      return [];
    }
  };

  globalThis.document = {
    querySelector(selector) {
      assert.equal(selector, "#app");
      return app;
    }
  };
  globalThis.location = {
    search: "",
    hostname: "127.0.0.1",
    assign() {}
  };
  const historyUrls = [];
  globalThis.history = { replaceState(_state, _title, url) { historyUrls.push(url); } };
  globalThis.fetch = async (url, options = {}) => {
    if (String(url) === "/internal/dashboard/session") {
      assert.equal(options.method, "POST");
      return { ok: true, async json() { return { sessionId: `${role.toLowerCase()}-session`, dashboardUrl: "/dashboard/" }; } };
    }
    assert.equal(String(url), "/internal/dashboard/workspace");
    assert.equal(options.headers["x-dashboard-session"], `${role.toLowerCase()}-session`);
    return {
      ok: true,
      async json() {
        return workspaceModel(role);
      }
    };
  };

  const moduleUrl = new URL("./dashboard.js", import.meta.url);
  moduleUrl.search = `role=${role}&t=${Date.now()}`;
  await import(moduleUrl.href);

  const deadline = Date.now() + 1000;
  while (!app.innerHTML.includes("Module Launch") && Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
  assert.ok(historyUrls.length > 0);
  assert.ok(historyUrls.every((url) => !String(url).includes("session=")));
  return app.innerHTML;
}

const psychiatristHtml = await renderScenario("PSYCHIATRIST");
assert.match(psychiatristHtml, /<h1>Workspace<\/h1>/);
assert.match(psychiatristHtml, /Dr\. Mina Rahimi/);
assert.match(psychiatristHtml, /Jul|07\/06|6\/7|06\/07/);
for (const title of ["Add New Patient", "Patient Follow-up", "Diagnosis", "Severity", "Medical History", "Suicide Risk", "Treatment Plan", "List of Patients", "Setting"]) {
  assert.match(psychiatristHtml, new RegExp(title));
}
for (const state of ["Available", "Unavailable", "Unauthorized"]) {
  assert.match(psychiatristHtml, new RegExp(state));
}

const adminHtml = await renderScenario("ADMIN");
assert.match(adminHtml, /<h1>Workspace<\/h1>/);
assert.match(adminHtml, /Ari Morgan/);
assert.doesNotMatch(adminHtml, /Dr\. Ari Morgan/);
for (const title of ["Add New User", "Logs", "Backup", "List of Users", "DDI Knowledge", "BN Models"]) {
  assert.match(adminHtml, new RegExp(title));
}
assert.match(adminHtml, /Unavailable/);
assert.match(adminHtml, /Unauthorized/);
assert.match(adminHtml, /\/modules\/auth\/accounts\/new/);
assert.match(adminHtml, /\/modules\/auth\/accounts/);
assert.match(adminHtml, /Readiness:<\/strong> not-ready/);
assert.match(adminHtml, /Clinical use:<\/strong> blocked-by-manifest/);

const source = readFileSync(new URL("./dashboard.js", import.meta.url), "utf8");
assert.doesNotMatch(source, /workspace\?session=/);
assert.match(source, /fetch\("\/api\/auth\/csrf"/);
assert.match(source, /fetch\("\/api\/auth\/logout"/);
assert.match(source, /"x-csrf-token": csrf\.csrf_token/);


