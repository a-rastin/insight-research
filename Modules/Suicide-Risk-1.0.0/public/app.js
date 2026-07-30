const VERSION = "1.0.0";
const DEFAULT_BASE = "/api/suicide-risk/v1";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const OPTIONS = [
  ["unknown", "Unknown", "Required risk information has not been established."],
  ["unavailable", "Unavailable", "The approved assessment cannot currently be obtained."],
  ["conflicting", "Conflicting", "Available source information conflicts and requires resolution."],
  ["imminent-suicide-risk", "Imminent suicide risk", "Psychiatrist assertion requiring urgent handling."],
  ["substantial-suicide-risk-requiring-urgent-evaluation", "Substantial suicide risk requiring urgent evaluation", "Psychiatrist assertion requiring urgent handling."]
];
let mounted = null;

export function normalizeContext(value) {
  if (!value || !UUID.test(value.patientId || "") || !UUID.test(value.encounterId || "") || !UUID.test(value.actorId || "")) {
    throw new Error("Suicide Risk requires host-provided Patient, Encounter, and Actor UUID context.");
  }
  if (value.assessmentId && !UUID.test(value.assessmentId)) throw new Error("Suicide Risk assessment context is invalid.");
  return { patientId: value.patientId, encounterId: value.encounterId, actorId: value.actorId, assessmentId: value.assessmentId || null };
}

export function normalizeBase(value = DEFAULT_BASE) {
  if (typeof value !== "string" || !value.startsWith("/") || value.startsWith("//") || /[?#]/.test(value)) throw new Error("Suicide Risk API base must be gateway-relative.");
  return value.replace(/\/$/, "");
}

async function responseBody(response, allowNotFound = false) {
  const value = await response.json().catch(() => null);
  if (allowNotFound && response.status === 404) return null;
  if (!response.ok) {
    const fields = value?.errors?.map((item) => item.message).filter(Boolean).join(" ");
    throw new Error(fields || value?.detail || value?.title || "The Suicide Risk service could not complete the request.");
  }
  return value;
}

export function createClient({ fetchImpl = fetch, apiBase = DEFAULT_BASE } = {}) {
  const base = normalizeBase(apiBase);
  const request = (suffix, options = {}) => fetchImpl(`${base}${suffix}`, { credentials: "include", ...options });
  return {
    async load(context, signal) {
      const suffix = context.assessmentId ? `/assessments/${encodeURIComponent(context.assessmentId)}` : `/encounters/${encodeURIComponent(context.encounterId)}/assessments/latest`;
      const response = await request(suffix, { signal });
      return { assessment: await responseBody(response, !context.assessmentId), etag: response.headers.get("ETag") };
    },
    async save({ context, assessment, etag, riskState, signal }) {
      const csrf = await responseBody(await request("/csrf", { signal }));
      const updating = Boolean(assessment);
      const headers = { "Content-Type": "application/json", "X-Schema-Version": VERSION, "X-CSRF-Token": csrf.token };
      if (updating) headers["If-Match"] = etag;
      else headers["Idempotency-Key"] = crypto.randomUUID();
      const assertion = { riskState, actor: { actorId: context.actorId, role: "psychiatrist" } };
      const payload = updating ? assertion : { patientId: context.patientId, encounterId: context.encounterId, ...assertion };
      const suffix = updating ? `/assessments/${encodeURIComponent(assessment.assessmentId)}` : "/assessments";
      const response = await request(suffix, { method: updating ? "PUT" : "POST", headers, body: JSON.stringify(payload), signal });
      return { assessment: await responseBody(response), etag: response.headers.get("ETag") };
    }
  };
}

export function validateAssessment(value, context) {
  if (!value || value.interfaceVersion !== VERSION || value.schemaVersion !== VERSION || value.patientId !== context.patientId ||
      value.encounterId !== context.encounterId || !UUID.test(value.assessmentId || "") || !OPTIONS.some(([state]) => state === value.riskState) ||
      value.riskScore !== null || value.instrument?.completionClaimed !== false || value.instrument?.questionsDefined !== false ||
      value.instrument?.scoringDefined !== false || value.actor?.role !== "psychiatrist" || !UUID.test(value.actor?.actorId || "") ||
      !Number.isInteger(value.resourceVersion) || value.resourceVersion < 1 || !value.safetyDisposition?.code) {
    throw new Error("Suicide Risk returned an incompatible assessment response.");
  }
  return value;
}

function markup() {
  return `<section class="suicide-risk-shell" aria-labelledby="suicide-risk-title">
    <header>
      <div><p class="eyebrow">Encounter-scoped clinical assertion</p><h1 id="suicide-risk-title">Suicide Risk</h1></div>
      <span id="suicide-risk-status" role="status">Loading</span>
    </header>
    <div id="suicide-risk-live" class="visually-hidden" aria-live="polite"></div>
    <div id="suicide-risk-error" class="alert hidden" role="alert" tabindex="-1"></div>
    <div class="boundary" role="note">
      <strong>Instrument unavailable</strong>
      <p>No C-SSRS questions or score are implemented because an approved source and licensing handoff is unavailable. This form records only an explicit psychiatrist assertion; it does not infer low or absent risk.</p>
    </div>
    <form id="suicide-risk-form">
      <fieldset><legend>Record the current source-backed assertion</legend>
        <p>Select a state only after clinical review. No option is preselected.</p>
        <div class="options">${OPTIONS.map(([value, label, help]) => `<label><input type="radio" name="risk-state" value="${value}"><span><strong>${label}</strong><small>${help}</small></span></label>`).join("")}</div>
      </fieldset>
      <section id="suicide-risk-disposition" class="disposition hidden" aria-live="polite"></section>
      <footer><p>Decision-support input. Psychiatrist authority and review remain explicit.</p><button type="submit">Save assertion</button></footer>
    </form>
  </section>`;
}

function renderDisposition(state, assessment) {
  const panel = state.root.querySelector("#suicide-risk-disposition");
  if (!assessment) {
    panel.classList.add("hidden");
    panel.replaceChildren();
    return;
  }
  panel.className = `disposition ${assessment.safetyDisposition.outcome === "emergency-blocked" ? "urgent" : "blocked"}`;
  const heading = document.createElement("h2");
  heading.textContent = assessment.safetyDisposition.outcome === "emergency-blocked" ? "Urgent: routine planning blocked" : "Blocked: risk information unresolved";
  const text = document.createElement("p");
  text.textContent = assessment.safetyDisposition.guidance;
  const code = document.createElement("p");
  code.className = "code";
  code.textContent = `Policy code: ${assessment.safetyDisposition.code}. This state persists until resolved and cannot be overridden.`;
  panel.replaceChildren(heading, text, code);
}

function showError(state, message) {
  const alert = state.root.querySelector("#suicide-risk-error");
  alert.textContent = `Save failed: ${message} This error remains visible until a save succeeds.`;
  alert.classList.remove("hidden");
  alert.focus();
  state.root.querySelector("#suicide-risk-status").textContent = "Save failed";
}

async function save(state) {
  const riskState = state.root.querySelector('input[name="risk-state"]:checked')?.value;
  if (!riskState) return showError(state, "Select an explicit risk state before saving.");
  const button = state.root.querySelector("button[type=submit]");
  button.disabled = true;
  try {
    const result = await state.client.save({ context: state.context, assessment: state.assessment, etag: state.etag, riskState, signal: state.abort.signal });
    if (mounted !== state || !result.etag) return;
    state.assessment = validateAssessment(result.assessment, state.context);
    state.etag = result.etag;
    const alert = state.root.querySelector("#suicide-risk-error");
    alert.textContent = "";
    alert.classList.add("hidden");
    renderDisposition(state, state.assessment);
    state.root.querySelector("#suicide-risk-status").textContent = "Saved";
    state.root.querySelector("#suicide-risk-live").textContent = "Suicide-risk assertion saved.";
    state.onAssessmentChange?.({ assessmentId: state.assessment.assessmentId, riskState: state.assessment.riskState });
  } catch (error) {
    if (error.name !== "AbortError" && mounted === state) showError(state, error.message);
  } finally {
    if (mounted === state) button.disabled = false;
  }
}

export async function mount({ root, context, apiBase = DEFAULT_BASE, fetchImpl = fetch, onAssessmentChange } = {}) {
  unmount();
  if (!(root instanceof Element)) throw new Error("Suicide Risk mount requires a root Element.");
  root.innerHTML = markup();
  let normalized;
  try { normalized = normalizeContext(context); } catch (error) {
    const failed = { root, abort: new AbortController() };
    mounted = failed;
    showError(failed, error.message);
    for (const control of root.querySelectorAll("button, input")) control.disabled = true;
    return null;
  }
  const state = { root, context: normalized, client: createClient({ fetchImpl, apiBase }), assessment: null, etag: null, abort: new AbortController(), onAssessmentChange };
  mounted = state;
  state.submit = (event) => { event.preventDefault(); save(state); };
  root.querySelector("form").addEventListener("submit", state.submit);
  try {
    const result = await state.client.load(state.context, state.abort.signal);
    if (mounted !== state) return null;
    if (result.assessment) {
      state.assessment = validateAssessment(result.assessment, state.context);
      state.etag = result.etag;
      root.querySelector(`input[value="${state.assessment.riskState}"]`).checked = true;
      renderDisposition(state, state.assessment);
      root.querySelector("#suicide-risk-status").textContent = "Loaded";
    } else root.querySelector("#suicide-risk-status").textContent = "Not assessed";
  } catch (error) {
    if (error.name !== "AbortError" && mounted === state) showError(state, error.message);
  }
  return { unmount };
}

export function unmount() {
  if (!mounted) return;
  mounted.abort.abort();
  mounted.root.querySelector("form")?.removeEventListener("submit", mounted.submit);
  mounted.root.replaceChildren();
  mounted = null;
}

if (typeof window !== "undefined") window.InsightSuicideRisk = Object.freeze({ mount, unmount });
