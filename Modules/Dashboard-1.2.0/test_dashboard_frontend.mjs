import assert from "node:assert/strict";
function workspaceModel(role) {
  const psychiatrist = role === "PSYCHIATRIST";
  return {
    displayName: psychiatrist ? "Dr. Mina Rahimi" : "Ari Morgan",
    currentDateTime: "2026-07-06T17:30:00Z",
    workspace: {
      kind: role,
      title: "Workspace",
      buttons: psychiatrist
        ? [
            { id: "add-new-patient", title: "Add New Patient", routeDiscovery: { method: "GET", href: "/internal/dashboard/module-routes/add-new-patient" } },
            { id: "patient-follow-up", title: "Patient Follow-up", routeDiscovery: { method: "GET", href: "/internal/dashboard/module-routes/patient-follow-up" } },
            { id: "list-of-patients", title: "List of Patients", routeDiscovery: { method: "GET", href: "/internal/dashboard/module-routes/list-of-patients" } },
            { id: "setting", title: "Setting", routeDiscovery: { method: "GET", href: "/internal/dashboard/module-routes/setting" } }
          ]
        : [
            { id: "add-new-user", title: "Add New User", routeDiscovery: { method: "GET", href: "/internal/dashboard/module-routes/add-new-user" } },
            { id: "logs", title: "Logs", routeDiscovery: { method: "GET", href: "/internal/dashboard/module-routes/logs" } },
            { id: "backup", title: "Backup", routeDiscovery: { method: "GET", href: "/internal/dashboard/module-routes/backup" } },
            { id: "list-of-users", title: "List of Users", routeDiscovery: { method: "GET", href: "/internal/dashboard/module-routes/list-of-users" } }
          ]
    },
    ...(psychiatrist ? { requiresDisclaimer: false, disclaimer: { acceptedAt: "2026-07-06T17:00:00Z" } } : {})
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
    search: `?session=${role.toLowerCase()}-session`,
    hostname: "127.0.0.1",
    assign() {}
  };
  globalThis.history = { replaceState() {} };
  globalThis.fetch = async (url) => {
    assert.match(String(url), /\/internal\/dashboard\/workspace\?session=/);
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
  return app.innerHTML;
}

const psychiatristHtml = await renderScenario("PSYCHIATRIST");
assert.match(psychiatristHtml, /<h1>Workspace<\/h1>/);
assert.match(psychiatristHtml, /Dr\. Mina Rahimi/);
assert.match(psychiatristHtml, /Jul|07\/06|6\/7|06\/07/);
for (const title of ["Add New Patient", "Patient Follow-up", "List of Patients", "Setting"]) {
  assert.match(psychiatristHtml, new RegExp(title));
}

const adminHtml = await renderScenario("ADMIN");
assert.match(adminHtml, /<h1>Workspace<\/h1>/);
assert.match(adminHtml, /Ari Morgan/);
assert.doesNotMatch(adminHtml, /Dr\. Ari Morgan/);
for (const title of ["Add New User", "Logs", "Backup", "List of Users"]) {
  assert.match(adminHtml, new RegExp(title));
}


