const SCHEMA_VERSION = "2.0.0";
const DEFAULT_API_BASE_PATH = "/api/medical-history/v2";
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const CLINICAL_STATES = [
  ["yes", "Yes"],
  ["no", "No"],
  ["unknown", "Unknown"]
];
const IDENTITY_LABELS = {
  matched: "Matched identity",
  unresolved: "Unresolved identity",
  ambiguous: "Ambiguous identity",
  "not-assessed": "Identity not assessed"
};
let mounted = null;

export function normalizeContext(context) {
  if (!context || !UUID_PATTERN.test(context.patientId || "") ||
      !UUID_PATTERN.test(context.encounterId || "") || !UUID_PATTERN.test(context.actorId || "")) {
    throw new Error("Medical History requires host-provided Patient, Encounter, and Actor UUID context.");
  }
  if (context.assessmentId && !UUID_PATTERN.test(context.assessmentId)) {
    throw new Error("Medical History assessment context is invalid.");
  }
  return {
    patientId: context.patientId,
    encounterId: context.encounterId,
    actorId: context.actorId,
    assessmentId: context.assessmentId || null
  };
}

export function normalizeApiBasePath(value = DEFAULT_API_BASE_PATH) {
  if (typeof value !== "string" || !value.startsWith("/") || value.startsWith("//") || /[?#]/.test(value)) {
    throw new Error("Medical History API base path must be gateway-relative.");
  }
  return value.replace(/\/$/, "");
}

async function responseBody(response, { allowNotFound = false } = {}) {
  const body = await response.json().catch(() => null);
  if (allowNotFound && response.status === 404) return null;
  if (!response.ok) {
    const detail = body?.detail || body?.title || "The Medical History service could not complete the request.";
    const fieldErrors = body?.errors?.map((item) => item.message).filter(Boolean).join(" ");
    throw new Error(fieldErrors ? `${detail} ${fieldErrors}` : detail);
  }
  return body;
}

export function createMedicalHistoryClient({ fetchImpl = fetch, apiBasePath = DEFAULT_API_BASE_PATH } = {}) {
  const basePath = normalizeApiBasePath(apiBasePath);
  const request = (path, options = {}) => fetchImpl(`${basePath}${path}`, { credentials: "include", ...options });

  return {
    async load(context, signal) {
      const path = context.assessmentId
        ? `/assessments/${encodeURIComponent(context.assessmentId)}`
        : `/encounters/${encodeURIComponent(context.encounterId)}/assessments/latest`;
      const response = await request(path, { signal });
      return { assessment: await responseBody(response, { allowNotFound: !context.assessmentId }), etag: response.headers.get("ETag") };
    },
    async options(signal) {
      const response = await fetchImpl("/api/internal/medical-history/options", { credentials: "include", signal });
      return responseBody(response);
    },
    async save({ context, assessment, etag, value, signal }) {
      const csrfResponse = await request("/csrf", { signal });
      const csrf = await responseBody(csrfResponse);
      const updating = Boolean(assessment?.assessmentId);
      const headers = {
        "Content-Type": "application/json",
        "X-Schema-Version": SCHEMA_VERSION,
        "X-CSRF-Token": csrf.token
      };
      if (updating) headers["If-Match"] = etag;
      else headers["Idempotency-Key"] = crypto.randomUUID();
      const body = updating ? value : { patientId: context.patientId, encounterId: context.encounterId, ...value };
      const path = updating ? `/assessments/${encodeURIComponent(assessment.assessmentId)}` : "/assessments";
      const response = await request(path, {
        method: updating ? "PUT" : "POST",
        headers,
        body: JSON.stringify(body),
        signal
      });
      return { assessment: await responseBody(response), etag: response.headers.get("ETag") };
    }
  };
}

export function validateServerAssessment(assessment, context) {
  if (!assessment || assessment.interfaceVersion !== SCHEMA_VERSION || assessment.schemaVersion !== SCHEMA_VERSION ||
      assessment.patientId !== context.patientId || assessment.encounterId !== context.encounterId ||
      !UUID_PATTERN.test(assessment.assessmentId || "") || !["in-progress", "completed", "not-assessed"].includes(assessment.status) ||
      !Number.isInteger(assessment.resourceVersion) || assessment.resourceVersion < 1 ||
      !UUID_PATTERN.test(assessment.actor?.actorId || "") || assessment.actor?.role !== "psychiatrist" ||
      !Array.isArray(assessment.medications)) {
    throw new Error("Medical History returned an incompatible assessment response.");
  }
  for (const medication of assessment.medications) {
    const identity = medication?.normalizedIdentity;
    const matched = identity?.state === "matched";
    if (!medication || typeof medication.originalText !== "string" || !IDENTITY_LABELS[identity?.state] ||
        (matched && (typeof identity.conceptId !== "string" || typeof identity.display !== "string")) ||
        (!matched && (identity.conceptId !== null || identity.display !== null || identity.terminologyVersion !== null))) {
      throw new Error("Medical History returned an incompatible medication identity response.");
    }
  }
  return assessment;
}

export function assessmentToFormValue(assessment) {
  return {
    pastMedicalHistory: [...(assessment?.pastMedicalHistory || [])],
    medications: (assessment?.medications || []).map((medication) => ({
      originalText: medication.originalText,
      doseText: medication.doseText,
      routeText: medication.routeText,
      frequencyText: medication.frequencyText,
      normalizedIdentity: { ...medication.normalizedIdentity }
    })),
    substantialSuicideRisk: assessment?.substantialSuicideRisk === "not-assessed" ? null : assessment?.substantialSuicideRisk || null,
    priorAntipsychoticTherapy: assessment?.priorAntipsychoticTherapy === "not-assessed" ? null : assessment?.priorAntipsychoticTherapy || null,
    priorAntipsychoticTherapySuccessful: assessment?.priorAntipsychoticTherapySuccessful === "not-assessed" ? null : assessment?.priorAntipsychoticTherapySuccessful || null,
    antipsychotic: assessment?.antipsychotic || null,
    clozapineContraindication: assessment?.clozapineContraindication === "not-assessed" ? null : assessment?.clozapineContraindication || null,
    clozapineContraindications: [...(assessment?.clozapineContraindications || [])],
    recurrentNonAdherenceDeterioration: assessment?.recurrentNonAdherenceDeterioration === "not-assessed" ? null : assessment?.recurrentNonAdherenceDeterioration || null
  };
}

function shell() {
  return `
    <section class="medical-history-shell" aria-labelledby="medical-history-title">
      <header class="medical-history-header">
        <div>
          <p class="medical-history-eyebrow">Encounter context supplied by host</p>
          <h1 id="medical-history-title">Medical History</h1>
        </div>
        <span id="medical-history-status" class="medical-history-status" role="status">Loading</span>
      </header>
      <div id="medical-history-live" class="visually-hidden" aria-live="polite"></div>
      <div id="medical-history-error" class="medical-history-alert hidden" role="alert" tabindex="-1"></div>
      <form id="medical-history-form" novalidate>
        <div class="medical-history-grid">
          <section class="field-block" aria-labelledby="history-heading">
            <div class="section-heading"><h2 id="history-heading">Past medical history</h2><span>Select multiple</span></div>
            <label for="past-medical-history">Relevant diseases</label>
            <select id="past-medical-history" multiple size="8"></select>
          </section>
          <section class="field-block" aria-labelledby="medications-heading">
            <div class="section-heading">
              <div><h2 id="medications-heading">Patient medications</h2><p>Each entered row remains a separate medication instance for later DDI review.</p></div>
              <button class="secondary" id="add-medication" type="button">Add medication</button>
            </div>
            <div class="medication-list" id="medication-list"></div>
            <p id="medication-empty" class="empty-state">No medications entered.</p>
          </section>
        </div>
        <section class="field-block clinical-questions" aria-labelledby="clinical-heading">
          <h2 id="clinical-heading">Clinical questions</h2>
          <p class="field-guidance">Questions remain explicitly unanswered until the psychiatrist selects a response and saves.</p>
          ${clinicalQuestion("substantial-suicide-risk", "Substantial suicide risk?")}
          ${clinicalQuestion("prior-antipsychotic-therapy", "Prior antipsychotic therapy?")}
          <div class="conditional hidden" id="antipsychotic-details">
            ${clinicalQuestion("antipsychotic-successful", "Was the therapy successful?")}
            <label for="antipsychotic">Which antipsychotic?</label>
            <select id="antipsychotic"><option value="">Select an antipsychotic</option></select>
          </div>
          ${clinicalQuestion("clozapine-contraindication", "Any contraindication to clozapine?")}
          <fieldset class="conditional hidden checkbox-list" id="clozapine-contraindications"><legend>Select all contraindications that apply</legend></fieldset>
          ${clinicalQuestion("recurrent-non-adherence-deterioration", "Recurrent non-adherence-related deterioration?")}
        </section>
        <footer class="action-bar">
          <p id="save-guidance">Unanswered questions will be saved as not assessed, never as No.</p>
          <button class="primary" id="save-medical-history" type="submit">Save medical history</button>
        </footer>
      </form>
    </section>`;
}

function clinicalQuestion(name, legend) {
  return `<fieldset class="clinical-question" data-question="${name}">
    <legend>${legend}</legend>
    <div class="clinical-options">${CLINICAL_STATES.map(([value, label]) => `<label><input type="radio" name="${name}" value="${value}"> ${label}</label>`).join("")}</div>
    <p class="answer-state" data-answer-state="${name}">Unanswered</p>
  </fieldset>`;
}

function createMedicationRow(state, medication = null) {
  const value = medication || {
    originalText: "",
    doseText: null,
    routeText: null,
    frequencyText: null,
    normalizedIdentity: { state: "not-assessed", conceptId: null, display: null, terminologyVersion: null }
  };
  const row = document.createElement("fieldset");
  row.className = "medication-row";
  row._normalizedIdentity = { ...value.normalizedIdentity };
  const legend = document.createElement("legend");
  legend.textContent = `Medication ${state.root.querySelectorAll(".medication-row").length + 1}`;
  const fields = [
    ["med-original", "Medication as entered", value.originalText, 500],
    ["med-dose", "Dose", value.doseText || "", 160],
    ["med-route", "Route", value.routeText || "", 160],
    ["med-frequency", "Frequency", value.frequencyText || "", 160]
  ];
  row.append(legend);
  for (const [className, labelText, fieldValue, maxLength] of fields) {
    const wrapper = document.createElement("div");
    const label = document.createElement("label");
    const input = document.createElement("input");
    const id = `medical-history-${className}-${crypto.randomUUID()}`;
    input.id = id;
    input.className = className;
    input.type = "text";
    input.maxLength = maxLength;
    input.value = fieldValue;
    label.htmlFor = id;
    label.textContent = labelText;
    wrapper.append(label, input);
    row.append(wrapper);
  }
  const identity = document.createElement("div");
  identity.className = "identity-status";
  identity.dataset.state = value.normalizedIdentity.state;
  identity.textContent = IDENTITY_LABELS[value.normalizedIdentity.state];
  if (value.normalizedIdentity.state === "matched") {
    identity.textContent += `: ${value.normalizedIdentity.display}`;
  }
  const remove = document.createElement("button");
  remove.className = "remove-medication";
  remove.type = "button";
  remove.textContent = "Remove";
  remove.addEventListener("click", () => {
    row.remove();
    updateMedicationControls(state);
    state.root.querySelector("#add-medication").focus();
  });
  row.append(identity, remove);
  return row;
}

function updateMedicationControls(state) {
  const rows = state.root.querySelectorAll(".medication-row");
  state.root.querySelector("#medication-empty").classList.toggle("hidden", rows.length > 0);
  state.root.querySelector("#add-medication").disabled = rows.length >= 20;
  rows.forEach((row, index) => { row.querySelector("legend").textContent = `Medication ${index + 1}`; });
}

function renderMedications(state) {
  const list = state.root.querySelector("#medication-list");
  list.replaceChildren(...state.value.medications.map((medication) => createMedicationRow(state, medication)));
  updateMedicationControls(state);
}

function setQuestion(state, name, value) {
  for (const input of state.root.querySelectorAll(`input[name="${name}"]`)) input.checked = input.value === value;
  state.root.querySelector(`[data-answer-state="${name}"]`).textContent = value ? `Answered: ${CLINICAL_STATES.find(([item]) => item === value)?.[1] || value}` : "Unanswered";
}

function selectedQuestion(state, name) {
  return state.root.querySelector(`input[name="${name}"]:checked`)?.value || null;
}

function updateConditionalFields(state) {
  const prior = selectedQuestion(state, "prior-antipsychotic-therapy") === "yes";
  const contraindication = selectedQuestion(state, "clozapine-contraindication") === "yes";
  state.root.querySelector("#antipsychotic-details").classList.toggle("hidden", !prior);
  state.root.querySelector("#antipsychotic").required = prior;
  state.root.querySelector("#clozapine-contraindications").classList.toggle("hidden", !contraindication);
  if (!contraindication) {
    for (const input of state.root.querySelectorAll("#clozapine-contraindications input")) input.checked = false;
  }
}

function renderValue(state) {
  const history = state.root.querySelector("#past-medical-history");
  for (const option of history.options) option.selected = state.value.pastMedicalHistory.includes(option.value);
  renderMedications(state);
  for (const name of ["substantial-suicide-risk", "prior-antipsychotic-therapy", "antipsychotic-successful", "clozapine-contraindication", "recurrent-non-adherence-deterioration"]) {
    const key = name.replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
    setQuestion(state, name, state.value[key]);
  }
  state.root.querySelector("#antipsychotic").value = state.value.antipsychotic || "";
  for (const input of state.root.querySelectorAll("#clozapine-contraindications input")) input.checked = state.value.clozapineContraindications.includes(input.value);
  updateConditionalFields(state);
}

function medicationPayload(state) {
  return Array.from(state.root.querySelectorAll(".medication-row")).map((row) => ({
    originalText: row.querySelector(".med-original").value.trim(),
    doseText: row.querySelector(".med-dose").value.trim() || null,
    routeText: row.querySelector(".med-route").value.trim() || null,
    frequencyText: row.querySelector(".med-frequency").value.trim() || null,
    normalizedIdentity: { ...row._normalizedIdentity }
  }));
}

export function deriveStatus(value) {
  const required = [value.substantialSuicideRisk, value.priorAntipsychoticTherapy, value.clozapineContraindication, value.recurrentNonAdherenceDeterioration];
  if (value.priorAntipsychoticTherapy === "yes") required.push(value.priorAntipsychoticTherapySuccessful, value.antipsychotic);
  if (value.clozapineContraindication === "yes") required.push(value.clozapineContraindications.length ? "answered" : null);
  return required.every((item) => Boolean(item) && item !== "not-assessed") ? "completed" : "in-progress";
}

function collectValue(state) {
  const prior = selectedQuestion(state, "prior-antipsychotic-therapy");
  const contraindication = selectedQuestion(state, "clozapine-contraindication");
  const value = {
    pastMedicalHistory: Array.from(state.root.querySelector("#past-medical-history").selectedOptions).map((option) => option.value),
    medications: medicationPayload(state),
    substantialSuicideRisk: selectedQuestion(state, "substantial-suicide-risk") || "not-assessed",
    priorAntipsychoticTherapy: prior || "not-assessed",
    priorAntipsychoticTherapySuccessful: prior === "yes" ? selectedQuestion(state, "antipsychotic-successful") || "not-assessed" : "not-assessed",
    antipsychotic: prior === "yes" ? state.root.querySelector("#antipsychotic").value || null : null,
    clozapineContraindication: contraindication || "not-assessed",
    clozapineContraindications: contraindication === "yes" ? Array.from(state.root.querySelectorAll("#clozapine-contraindications input:checked")).map((input) => input.value) : [],
    recurrentNonAdherenceDeterioration: selectedQuestion(state, "recurrent-non-adherence-deterioration") || "not-assessed",
    actor: { actorId: state.context.actorId, role: "psychiatrist" }
  };
  value.status = deriveStatus(value);
  return value;
}

function showError(state, message) {
  state.error = message;
  const alert = state.root.querySelector("#medical-history-error");
  alert.textContent = `Save failed: ${message} This error remains visible until a save succeeds.`;
  alert.classList.remove("hidden");
  alert.focus();
  state.root.querySelector("#medical-history-status").textContent = "Save failed";
  state.root.querySelector("#medical-history-live").textContent = `Save failed: ${message}`;
}

function clearErrorAfterSuccess(state) {
  state.error = null;
  const alert = state.root.querySelector("#medical-history-error");
  alert.textContent = "";
  alert.classList.add("hidden");
}

async function persist(state) {
  const value = collectValue(state);
  if (value.medications.some((medication) => !medication.originalText)) {
    showError(state, "Medication as entered is required for every medication row.");
    return;
  }
  state.saving = true;
  const submit = state.root.querySelector("#save-medical-history");
  submit.disabled = true;
  submit.textContent = "Saving...";
  try {
    const result = await state.client.save({ context: state.context, assessment: state.assessment, etag: state.etag, value, signal: state.abort.signal });
    if (mounted !== state) return;
    if (!result.etag) throw new Error("Medical History returned an incompatible assessment response.");
    state.assessment = validateServerAssessment(result.assessment, state.context);
    state.etag = result.etag;
    state.value = assessmentToFormValue(state.assessment);
    clearErrorAfterSuccess(state);
    renderValue(state);
    state.root.querySelector("#medical-history-status").textContent = state.assessment.status === "completed" ? "Saved: completed" : "Saved: in progress";
    state.root.querySelector("#medical-history-live").textContent = "Medical history saved successfully.";
    state.onAssessmentChange?.({ assessmentId: state.assessment.assessmentId, status: state.assessment.status });
  } catch (error) {
    if (error.name !== "AbortError" && mounted === state) showError(state, error.message);
  } finally {
    if (mounted === state) {
      state.saving = false;
      submit.disabled = false;
      submit.textContent = "Save medical history";
    }
  }
}

function handleChange(state, event) {
  if (event.target.matches('input[type="radio"]')) {
    const answer = state.root.querySelector(`[data-answer-state="${event.target.name}"]`);
    answer.textContent = `Answered: ${CLINICAL_STATES.find(([value]) => value === event.target.value)[1]}`;
    updateConditionalFields(state);
  }
}

export async function mount({ root, context, apiBasePath = DEFAULT_API_BASE_PATH, fetchImpl = fetch, onAssessmentChange } = {}) {
  unmount();
  if (!(root instanceof Element)) throw new Error("Medical History mount requires a root Element.");
  root.innerHTML = shell();
  let normalized;
  try {
    normalized = normalizeContext(context);
  } catch (error) {
    const unavailable = { root, abort: new AbortController(), error, changeHandler: null, submitHandler: null, addHandler: null };
    mounted = unavailable;
    showError(unavailable, error.message);
    for (const control of root.querySelectorAll("button, input, select")) control.disabled = true;
    return null;
  }
  const state = {
    root,
    context: normalized,
    client: createMedicalHistoryClient({ fetchImpl, apiBasePath }),
    assessment: null,
    etag: null,
    value: assessmentToFormValue(null),
    saving: false,
    error: null,
    abort: new AbortController(),
    onAssessmentChange
  };
  mounted = state;
  state.changeHandler = (event) => handleChange(state, event);
  state.submitHandler = (event) => { event.preventDefault(); persist(state); };
  state.addHandler = () => {
    const list = state.root.querySelector("#medication-list");
    if (list.children.length >= 20) return;
    const row = createMedicationRow(state);
    list.append(row);
    updateMedicationControls(state);
    row.querySelector("input").focus();
  };
  root.addEventListener("change", state.changeHandler);
  root.querySelector("#medical-history-form").addEventListener("submit", state.submitHandler);
  root.querySelector("#add-medication").addEventListener("click", state.addHandler);

  try {
    const [options, result] = await Promise.all([state.client.options(state.abort.signal), state.client.load(normalized, state.abort.signal)]);
    if (mounted !== state) return null;
    for (const label of options.pastMedicalHistory) state.root.querySelector("#past-medical-history").add(new Option(label, label));
    for (const label of options.antipsychotics) state.root.querySelector("#antipsychotic").add(new Option(label, label));
    for (const label of options.clozapineContraindications) {
      const item = document.createElement("label");
      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = label;
      item.append(input, ` ${label}`);
      state.root.querySelector("#clozapine-contraindications").append(item);
    }
    if (result.assessment) {
      if (!result.etag) throw new Error("Medical History returned an incompatible assessment response.");
      state.assessment = validateServerAssessment(result.assessment, normalized);
      state.etag = result.etag;
      state.value = assessmentToFormValue(state.assessment);
    }
    renderValue(state);
    state.root.querySelector("#medical-history-status").textContent = state.assessment ? "Loaded" : "Not yet saved";
  } catch (error) {
    if (error.name !== "AbortError" && mounted === state) showError(state, error.message);
  }
  return { unmount, getAssessmentId: () => state.assessment?.assessmentId || null };
}

export function unmount() {
  if (!mounted) return;
  mounted.abort.abort();
  if (mounted.changeHandler) mounted.root.removeEventListener("change", mounted.changeHandler);
  if (mounted.submitHandler) mounted.root.querySelector("#medical-history-form")?.removeEventListener("submit", mounted.submitHandler);
  if (mounted.addHandler) mounted.root.querySelector("#add-medication")?.removeEventListener("click", mounted.addHandler);
  mounted.root.replaceChildren();
  mounted = null;
}

if (typeof window !== "undefined") {
  window.InsightMedicalHistory = Object.freeze({ mount, unmount });
  const standaloneRoot = document.querySelector("#medical-history-root[data-standalone]");
  if (standaloneRoot) mount({ root: standaloneRoot, context: window.__INSIGHT_MEDICAL_HISTORY_CONTEXT__ });
}
