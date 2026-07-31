const app = document.querySelector("#app");
const params = new URLSearchParams(location.search);

const ROLE_META = {
  PSYCHIATRIST: {
    label: "Psychiatrist",
    scope: "Clinical operations",
    tone: "clinical",
    modules: {
      "add-new-patient": ["Intake", "Register patient shell", "Info"],
      "patient-follow-up": ["Follow-up", "Review queued follow-up work", "Follow-up"],
      "list-of-patients": ["Registry", "Open patient directory module", "Normal"],
      setting: ["Settings", "Workspace preferences", "Info"]
    }
  },
  ADMIN: {
    label: "Admin",
    scope: "System operations",
    tone: "admin",
    modules: {
      "add-new-user": ["Access", "Create account in Authentication", "Warning"],
      logs: ["Audit", "Review system logs module", "Info"],
      backup: ["Backup", "Open backup module", "Warning"],
      "list-of-users": ["Users", "Open Authentication account directory", "Normal"]
    }
  }
};

const STATUS_META = {
  available: ["normal", "Available"],
  unavailable: ["warning", "Unavailable"],
  unauthorized: ["urgent", "Unauthorized"]
};

let state = {
  sessionId: params.get("session"),
  model: null,
  view: "loading",
  error: null,
  devRole: null,
  signedOut: params.get("signedOut") === "1"
};

const api = {
  activate(role) {
    const headers = role ? { "x-demo-auth-user": role === "PSYCHIATRIST" ? "psy-1" : "admin-1" } : {};
    return request("/internal/dashboard/session", {
      method: "POST",
      headers,
      body: { device: role ? "Standalone dev-only role simulation" : "Dashboard workspace" }
    });
  },
  workspace() {
    return request(`/internal/dashboard/workspace?session=${encodeURIComponent(state.sessionId)}`);
  },
  acceptDisclaimer() {
    return request("/internal/dashboard/disclaimer/accept", { method: "POST" });
  },
  moduleRoute(discoveryUrl) {
    return request(discoveryUrl);
  },
  signOut() {
    return request("/internal/dashboard/session", { method: "DELETE" });
  }
};

async function request(url, options = {}) {
  const headers = {
    "content-type": "application/json",
    ...(state.sessionId ? { "x-dashboard-session": state.sessionId } : {}),
    ...(options.headers || {})
  };
  const response = await fetch(url, {
    method: options.method || "GET",
    headers,
    body: options.body ? JSON.stringify(options.body) : undefined
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || data.detail || "Request failed");
  return data;
}

function escapeHtml(value = "") {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
  })[char]);
}

function fmtDate(value) {
  try {
    return new Intl.DateTimeFormat(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    }).format(new Date(value));
  } catch {
    return value || "Unknown";
  }
}

function isLocalDev() {
  return ["localhost", "127.0.0.1", "::1", ""].includes(location.hostname);
}

function roleMeta(role) {
  return ROLE_META[role] || ROLE_META.PSYCHIATRIST;
}

function buttonMeta(button, role) {
  return roleMeta(role).modules[button.id] || ["Module", "Destination details", "Info"];
}

function statusBadge(status) {
  const [className, label] = STATUS_META[status] || STATUS_META.unavailable;
  return `<span class="status ${className}"><span aria-hidden="true">${label[0]}</span>${escapeHtml(label)}</span>`;
}

function setUrlToSession(url) {
  history.replaceState(null, "", url || `/dashboard/?session=${encodeURIComponent(state.sessionId)}`);
}

function clearUrl(extra = "") {
  history.replaceState(null, "", `/dashboard/${extra}`);
}

async function load() {
  renderLoading();

  if (state.signedOut) {
    renderAccess({ signedOut: true });
    return;
  }

  if (!state.sessionId) {
    try {
      const result = await api.activate();
      state.sessionId = result.sessionId;
      setUrlToSession(result.dashboardUrl);
    } catch (error) {
      state.error = error;
      renderAccess({ error });
      return;
    }
  }

  try {
    state.model = await api.workspace();
    renderWorkspace();
  } catch (error) {
    state.sessionId = null;
    state.model = null;
    state.error = error;
    clearUrl();
    renderAccess({ error });
  }
}

function renderLoading() {
  app.innerHTML = `
    <main class="boot-screen">
      <section class="boot-panel" aria-busy="true">
        <p class="eyebrow">Dashboard workspace</p>
        <h1>Workspace</h1>
        <p class="muted">Verifying authenticated session.</p>
        <div class="skeleton-list" aria-hidden="true">
          <span></span><span></span><span></span>
        </div>
      </section>
    </main>
  `;
}

function renderAccess({ error, signedOut } = {}) {
  const local = isLocalDev();
  app.innerHTML = `
    <main class="access-screen">
      <section class="access-panel">
        <div>
          <p class="eyebrow">Dashboard workspace</p>
          <h1>Workspace</h1>
          <p class="muted">${signedOut ? "Dashboard session ended." : "Authenticated activation is required before workspace data loads."}</p>
        </div>
        ${error ? `<p class="inline-error">${escapeHtml(error.message)}</p>` : ""}
        ${local ? renderDevAccess() : renderAuthNotice()}
      </section>
    </main>
  `;

  app.querySelectorAll("[data-dev-role]").forEach((button) => {
    button.addEventListener("click", () => activateDevRole(button.dataset.devRole));
  });
  const resume = app.querySelector("#resumeWorkspace");
  if (resume) resume.addEventListener("click", () => {
    state.signedOut = false;
    clearUrl();
    load();
  });
}

function renderDevAccess() {
  return `
    <div class="dev-panel">
      <div>
        <span class="dev-badge">Development access only</span>
        <p>Role simulation sends <code>x-demo-auth-user</code> to local mock auth. Integrated environments should use real Authentication credentials.</p>
      </div>
      <div class="dev-actions">
        <button data-dev-role="PSYCHIATRIST">Clinician dev</button>
        <button data-dev-role="ADMIN">Admin dev</button>
        <button id="resumeWorkspace" class="primary">Retry auth</button>
      </div>
    </div>
  `;
}

function renderAuthNotice() {
  return `
    <div class="auth-panel">
      <strong>Authentication required</strong>
      <p>Open Dashboard from authenticated host app, or pass a valid Dashboard session URL.</p>
    </div>
  `;
}

async function activateDevRole(role) {
  renderLoading();
  try {
    const result = await api.activate(role);
    state.sessionId = result.sessionId;
    state.devRole = role;
    state.signedOut = false;
    setUrlToSession(result.dashboardUrl);
    state.model = await api.workspace();
    renderWorkspace();
  } catch (error) {
    state.error = error;
    renderAccess({ error });
  }
}

function renderWorkspace() {
  const model = state.model;
  const workspace = model.workspace;
  const role = workspace.kind;
  const meta = roleMeta(role);
  const requiresDisclaimer = Boolean(model.requiresDisclaimer);
  const buttons = workspace.buttons || [];

  app.innerHTML = `
    <div class="workspace-frame ${meta.tone}">
      <aside class="sidebar" aria-label="Workspace navigation">
        <div class="brand-block">
          <span class="brand-mark">IN</span>
          <div>
            <strong>INSIGHT</strong>
            <span>Dashboard</span>
          </div>
        </div>
        <nav class="module-nav" aria-label="Modules">
          ${buttons.map((button, index) => renderNavButton(button, role, index === 0)).join("")}
        </nav>
        <div class="sidebar-status">
          <span>Auth</span>
          <strong>Verified</strong>
          <span>Session</span>
          <code>${escapeHtml((state.sessionId || "").slice(0, 8))}</code>
          ${state.devRole ? `<span class="dev-badge compact">Dev-only role</span>` : ""}
        </div>
      </aside>

      <main class="workspace-main">
        <header class="topbar">
          <div>
            <p class="eyebrow">${escapeHtml(meta.scope)}</p>
            <h1>${escapeHtml(workspace.title || "Workspace")}</h1>
            <p class="muted">${escapeHtml(model.displayName)} - ${escapeHtml(fmtDate(model.currentDateTime))}</p>
          </div>
          <div class="topbar-actions">
            <span class="role-chip">${escapeHtml(meta.label)}</span>
            <button id="signOut">Sign out</button>
          </div>
        </header>

        ${requiresDisclaimer ? renderDisclaimer(model.disclaimer) : ""}

        <section class="metric-strip" aria-label="Workspace summary">
          ${renderMetric("Role", meta.label, "Verified identity")}
          ${renderMetric("Available", String(buttons.filter((button) => button.state === "available").length).padStart(2, "0"), "Role scoped")}
          ${renderMetric("Destinations", String(buttons.length).padStart(2, "0"), "Explicit states")}
          ${renderMetric("Status", requiresDisclaimer ? "Review" : "Ready", requiresDisclaimer ? "Accept notice" : "Operational")}
        </section>

        ${state.error ? `<p class="inline-error" role="alert">${escapeHtml(state.error.message)}</p>` : ""}

        <section class="work-grid">
          <div class="module-table-wrap">
            <div class="section-heading">
              <div>
                <h2>Module Launch</h2>
                <p>Role-scoped destinations. Unavailable and unauthorized routes remain explicit.</p>
              </div>
            </div>
            <div class="table-shell">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Module</th>
                    <th scope="col">Scope</th>
                    <th scope="col">State</th>
                    <th scope="col">Route</th>
                    <th scope="col">Action</th>
                  </tr>
                </thead>
                <tbody>
                  ${buttons.map((button) => renderModuleRow(button, role, requiresDisclaimer)).join("")}
                </tbody>
              </table>
            </div>
          </div>

          <aside class="operations-panel" aria-label="Session details">
            <h2>Session</h2>
            <dl class="facts">
              <div><dt>User</dt><dd>${escapeHtml(model.displayName)}</dd></div>
              <div><dt>Workspace</dt><dd>${escapeHtml(role)}</dd></div>
              <div><dt>Boundary</dt><dd>Internal REST only</dd></div>
              <div><dt>Auth check</dt><dd>GET /api/auth/v2/session</dd></div>
            </dl>
          </aside>
        </section>
      </main>
    </div>
  `;

  app.querySelector("#signOut").addEventListener("click", signOut);
  const accept = app.querySelector("#acceptDisclaimer");
  if (accept) accept.addEventListener("click", acceptDisclaimer);
  app.querySelectorAll("[data-module]").forEach((button) => {
    button.addEventListener("click", () => launchModule(button.dataset.module));
  });
}

function renderNavButton(button, role, active) {
  const [kind] = buttonMeta(button, role);
  return `
    <button class="nav-item ${active && button.state === "available" ? "active" : ""}" data-module="${escapeHtml(button.id)}" ${button.state === "available" ? "" : "disabled"} title="${escapeHtml(button.reason)}">
      <span>${escapeHtml(kind.slice(0, 2).toUpperCase())}</span>
      ${escapeHtml(button.title)}
    </button>
  `;
}

function renderDisclaimer(disclaimer = {}) {
  return `
    <section class="notice-band warning" role="status">
      <div>
        <strong>Research prototype notice</strong>
        <p>${escapeHtml(disclaimer.text || "Review and accept prototype notice before launching clinical modules.")}</p>
      </div>
      <button id="acceptDisclaimer" class="primary">Accept notice</button>
    </section>
  `;
}

function renderMetric(label, value, helper) {
  return `
    <div class="metric">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
      <small>${escapeHtml(helper)}</small>
    </div>
  `;
}

function renderModuleRow(button, role, locked) {
  const [kind, description] = buttonMeta(button, role);
  const enabled = !locked && button.state === "available";
  return `
    <tr>
      <th scope="row">
        <span class="module-title">${escapeHtml(button.title)}</span>
        <span class="module-desc">${escapeHtml(description)}</span>
      </th>
      <td>${escapeHtml(kind)}</td>
      <td>${statusBadge(locked && button.state === "available" ? "unavailable" : button.state)}<span class="state-reason">${escapeHtml(locked && button.state === "available" ? "Accept notice before opening." : button.reason)}</span></td>
      <td><code>${escapeHtml(button.href || "No route")}</code></td>
      <td><button class="table-action" data-module="${escapeHtml(button.id)}" ${enabled ? "" : "disabled"}>Open</button></td>
    </tr>
  `;
}

async function acceptDisclaimer() {
  const button = app.querySelector("#acceptDisclaimer");
  if (button) button.disabled = true;
  try {
    state.model = await api.acceptDisclaimer();
    renderWorkspace();
  } catch (error) {
    state.error = error;
    renderWorkspace();
  }
}

async function launchModule(moduleId) {
  const button = state.model.workspace.buttons.find((item) => item.id === moduleId);
  if (!button || button.state !== "available" || state.model.requiresDisclaimer) return;
  try {
    const route = await api.moduleRoute(`/internal/dashboard/module-routes/${encodeURIComponent(button.id)}`);
    location.assign(route.href);
  } catch (error) {
    state.error = error;
    renderWorkspace();
  }
}

async function signOut() {
  if (state.sessionId) {
    try {
      await api.signOut();
    } catch {
      // Local reset still ends Dashboard session in this browser.
    }
  }
  state = { sessionId: null, model: null, view: "access", error: null, devRole: null, signedOut: true };
  clearUrl("?signedOut=1");
  renderAccess({ signedOut: true });
}

load();
