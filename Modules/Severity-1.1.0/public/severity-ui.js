const SCHEMA_VERSION = "2.0.0";
const DEFAULT_API_BASE_PATH = "/api/severity/v2";
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export const PANSS_ITEMS = [
  ["P1", "P", "Delusions", "Beliefs which are unfounded, unrealistic and highly improbable."],
  ["P2", "P", "Conceptual disorganization", "Disorganized thinking and speech."],
  ["P3", "P", "Hallucinatory behavior", "Perceptions without external stimuli."],
  ["P4", "P", "Excitement", "Hyperactivity, accelerated motor behavior, and heightened responsivity."],
  ["P5", "P", "Grandiosity", "Exaggerated self-opinion and unrealistic beliefs of superiority."],
  ["P6", "P", "Suspiciousness or persecution", "Guardedness, distrustfulness, ideas of reference, or persecution."],
  ["P7", "P", "Hostility", "Verbal or physical expressions of anger, aggression, or sarcasm."],
  ["N1", "N", "Blunted affect", "Diminished facial expression, gestures, or vocal inflection."],
  ["N2", "N", "Emotional withdrawal", "Lack of interest, involvement, or emotional commitment."],
  ["N3", "N", "Poor rapport", "Lack of interpersonal empathy, openness, or warmth."],
  ["N4", "N", "Passive or apathetic social withdrawal", "Passive apathy or lack of drive for social activities."],
  ["N5", "N", "Difficulty in abstract thinking", "Impairment in figurative, symbolic, or abstract reasoning."],
  ["N6", "N", "Lack of spontaneity and flow", "Reduced conversational flow and brief or unspontaneous answers."],
  ["N7", "N", "Stereotyped thinking", "Repetitive, rigid, or monotonous thought contents."],
  ["G1", "G", "Somatic concern", "Physical complaints or beliefs of bodily illness."],
  ["G2", "G", "Anxiety", "Worry, fear, apprehension, or physical tension."],
  ["G3", "G", "Guilt feelings", "Self-blame, regret, or remorse for real or imagined actions."],
  ["G4", "G", "Tension", "Physical signs of nervousness, restlessness, or trembling."],
  ["G5", "G", "Mannerisms and posturing", "Odd, unnatural, or ritualistic movements or postures."],
  ["G6", "G", "Depression", "Feelings of sadness, hopelessness, worthlessness, or helplessness."],
  ["G7", "G", "Motor retardation", "Reduction in motor activity, movements, speech, or gait."],
  ["G8", "G", "Uncooperativeness", "Active refusal to comply, hostility, or resistance to assessment."],
  ["G9", "G", "Unusual thought content", "Strange, bizarre, or highly atypical thought themes."],
  ["G10", "G", "Disorientation", "Lack of awareness of time, place, or person."],
  ["G11", "G", "Poor attention", "Difficulty concentrating or maintaining focused attention."],
  ["G12", "G", "Lack of judgment and insight", "Failure to recognize illness, treatment need, or consequences."],
  ["G13", "G", "Disturbance of volition", "Disturbance in initiating, maintaining, or controlling actions."],
  ["G14", "G", "Poor impulse control", "Impulsive actions, sudden anger, or outbursts without foresight."],
  ["G15", "G", "Preoccupation", "Absorption with internal thoughts or daydreaming."],
  ["G16", "G", "Active social avoidance", "Active avoidance due to fear, suspicion, or anxiety."]
].map(([code, scale, name, description]) => ({ code, scale, name, description }));

const SCORE_LABELS = ["", "Absent", "Minimal", "Mild", "Moderate", "Moderately severe", "Severe", "Extreme"];
let mounted = null;

export function normalizeContext(context) {
  if (!context || !UUID_PATTERN.test(context.patientId || "") || !UUID_PATTERN.test(context.encounterId || "")) {
    throw new Error("Severity requires host-provided Patient and Encounter UUID context.");
  }
  if (context.assessmentId && !UUID_PATTERN.test(context.assessmentId)) {
    throw new Error("Severity assessment context is invalid.");
  }
  return {
    patientId: context.patientId,
    encounterId: context.encounterId,
    assessmentId: context.assessmentId || null
  };
}

export function normalizeApiBasePath(value = DEFAULT_API_BASE_PATH) {
  if (typeof value !== "string" || !value.startsWith("/") || value.startsWith("//") || /[?#]/.test(value)) {
    throw new Error("Severity API base path must be gateway-relative.");
  }
  return value.replace(/\/$/, "");
}

async function responseBody(response) {
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const message = body?.detail || body?.title || "The Severity service could not complete the request.";
    throw new Error(message);
  }
  return body;
}

export function createSeverityClient({ fetchImpl = fetch, apiBasePath = DEFAULT_API_BASE_PATH } = {}) {
  const basePath = normalizeApiBasePath(apiBasePath);
  const request = (path, options = {}) => fetchImpl(`${basePath}${path}`, { credentials: "include", ...options });

  return {
    async load(assessmentId, signal) {
      const response = await request(`/assessments/${encodeURIComponent(assessmentId)}`, { signal });
      return { assessment: await responseBody(response), etag: response.headers.get("ETag") };
    },
    async save({ context, assessment, etag, status, itemScores, signal }) {
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
      const body = updating
        ? { status, itemScores }
        : { patientId: context.patientId, encounterId: context.encounterId, status, itemScores };
      const path = updating ? `/assessments/${encodeURIComponent(assessment.assessmentId)}` : "/assessments";
      const response = await request(path, { method: updating ? "PUT" : "POST", headers, body: JSON.stringify(body), signal });
      return { assessment: await responseBody(response), etag: response.headers.get("ETag") };
    }
  };
}

function validateServerAssessment(assessment, context) {
  if (!assessment || assessment.interfaceVersion !== SCHEMA_VERSION || assessment.schemaVersion !== SCHEMA_VERSION ||
      assessment.patientId !== context.patientId || assessment.encounterId !== context.encounterId ||
      !UUID_PATTERN.test(assessment.assessmentId || "") || !["in-progress", "completed", "skipped"].includes(assessment.status)) {
    throw new Error("Severity returned an incompatible assessment response.");
  }
  return assessment;
}

function statusContent(assessment) {
  if (!assessment) return { kind: "warning", icon: "Information:", text: "In progress. No assessment result has been persisted yet." };
  if (assessment.status === "skipped") return { kind: "warning", icon: "Warning:", text: "Passed / skipped. No PANSS score was inferred." };
  if (assessment.status === "completed") return { kind: "normal", icon: "Complete:", text: "Completed. Scores below were verified and persisted by the Severity server." };
  return { kind: "warning", icon: "Information:", text: "In progress. The server reports that the assessment is incomplete." };
}

function shell() {
  return `
    <section class="severity-shell" aria-labelledby="severity-title">
      <header class="severity-header">
        <div><span class="severity-wordmark">INSIGHT</span> <span class="severity-context">PANSS Severity</span></div>
        <span class="severity-context">Encounter context supplied by host</span>
      </header>
      <div id="severity-state" class="severity-visually-hidden" aria-live="polite"></div>
      <main class="severity-main">
        <section class="severity-questionnaire" aria-labelledby="severity-title">
          <h1 id="severity-title">PANSS Clinical Evaluation</h1>
          <p class="severity-help">Rate all 30 items from 1 (Absent) to 7 (Extreme). Local selections show completion progress only; the server is authoritative for all scores.</p>
          <div class="severity-tabs" role="tablist" aria-label="PANSS subscales">
            <button class="severity-tab" type="button" role="tab" data-tab="P" aria-selected="true">Positive <span data-count="P">0/7</span></button>
            <button class="severity-tab" type="button" role="tab" data-tab="N" aria-selected="false">Negative <span data-count="N">0/7</span></button>
            <button class="severity-tab" type="button" role="tab" data-tab="G" aria-selected="false">General <span data-count="G">0/16</span></button>
          </div>
          <div id="severity-items"></div>
        </section>
        <aside class="severity-summary" aria-label="Assessment summary">
          <section class="severity-card">
            <h2>Assessment status</h2>
            <div id="severity-banner" class="severity-status" data-kind="warning" role="status"></div>
          </section>
          <section class="severity-card">
            <h2>Completion progress</h2>
            <p id="severity-progress-text">0 of 30 items rated</p>
            <div class="severity-progress" role="progressbar" aria-label="PANSS completion" aria-valuemin="0" aria-valuemax="30" aria-valuenow="0"><span style="width:0%"></span></div>
            <div id="severity-server-result"></div>
          </section>
          <section class="severity-card">
            <h2>Clinician action</h2>
            <p class="severity-help">Decision-support assessment. Psychiatrist final review required.</p>
            <p id="severity-submit-help" class="severity-help">Rate all 30 items before completing the evaluation.</p>
            <div class="severity-actions">
              <button id="severity-complete" class="severity-primary" type="button" disabled>Save completed evaluation</button>
              <button id="severity-pass" class="severity-secondary" type="button">Pass / skip assessment</button>
              <button id="severity-reset" class="severity-secondary" type="button">Reset local selections</button>
            </div>
          </section>
        </aside>
      </main>
    </section>`;
}

function renderItems(state) {
  const container = state.root.querySelector("#severity-items");
  container.replaceChildren(...PANSS_ITEMS.filter(item => item.scale === state.tab).map(item => {
    const fieldset = document.createElement("fieldset");
    fieldset.className = "severity-item";
    const legend = document.createElement("legend");
    legend.textContent = `${item.code} - ${item.name}`;
    const description = document.createElement("p");
    description.className = "severity-description";
    description.id = `severity-description-${item.code}`;
    description.textContent = item.description;
    const scores = document.createElement("div");
    scores.className = "severity-scores";
    scores.setAttribute("aria-describedby", description.id);
    for (let score = 1; score <= 7; score += 1) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "severity-score";
      button.dataset.item = item.code;
      button.dataset.score = String(score);
      button.setAttribute("aria-label", `${item.code}: ${score}, ${SCORE_LABELS[score]}`);
      button.setAttribute("aria-pressed", String(state.answers[item.code] === score));
      button.textContent = String(score);
      scores.append(button);
    }
    const label = document.createElement("div");
    label.className = "severity-label";
    label.textContent = state.answers[item.code] ? `Selected: ${SCORE_LABELS[state.answers[item.code]]}` : "Unrated";
    fieldset.append(legend, description, scores, label);
    return fieldset;
  }));
}

function renderSummary(state) {
  const counts = { P: 0, N: 0, G: 0 };
  for (const item of PANSS_ITEMS) if (state.answers[item.code]) counts[item.scale] += 1;
  for (const scale of ["P", "N", "G"]) state.root.querySelector(`[data-count="${scale}"]`).textContent = `${counts[scale]}/${scale === "G" ? 16 : 7}`;
  const total = Object.keys(state.answers).length;
  state.root.querySelector("#severity-progress-text").textContent = `${total} of 30 items rated`;
  const progress = state.root.querySelector('[role="progressbar"]');
  progress.setAttribute("aria-valuenow", String(total));
  progress.firstElementChild.style.width = `${Math.round(total / 30 * 100)}%`;
  const complete = state.root.querySelector("#severity-complete");
  complete.disabled = total !== 30 || state.saving;
  state.root.querySelector("#severity-pass").disabled = state.saving;
  state.root.querySelector("#severity-submit-help").textContent = total === 30 ? "All items are rated. Saving will request server verification." : `Rate ${30 - total} more item${30 - total === 1 ? "" : "s"} before completing.`;
  const banner = state.root.querySelector("#severity-banner");
  if (state.error) {
    banner.dataset.kind = "urgent";
    banner.setAttribute("role", "alert");
    banner.textContent = `Error: ${state.error} The error remains visible until another action succeeds.`;
  } else {
    const status = statusContent(state.assessment);
    banner.dataset.kind = status.kind;
    banner.setAttribute("role", status.kind === "urgent" ? "alert" : "status");
    banner.textContent = `${status.icon} ${status.text}`;
  }
  const result = state.root.querySelector("#severity-server-result");
  result.replaceChildren();
  if (state.assessment?.evaluation?.state === "completed" && state.assessment.scores) {
    const values = [["Positive", "positive"], ["Negative", "negative"], ["General", "general"], ["Total PANSS", "total"]];
    const list = document.createElement("dl");
    list.className = "severity-server-scores";
    list.setAttribute("aria-label", "Server-verified PANSS scores");
    for (const [label, key] of values) {
      const term = document.createElement("dt");
      term.textContent = label;
      const value = document.createElement("dd");
      value.textContent = String(state.assessment.scores[key]);
      list.append(term, value);
    }
    result.append(list);
  }
}

function showError(state, message) {
  state.error = message;
  const banner = state.root.querySelector("#severity-banner");
  banner.dataset.kind = "urgent";
  banner.setAttribute("role", "alert");
  banner.textContent = `Error: ${message} The error remains visible until another action succeeds.`;
  state.root.querySelector("#severity-state").textContent = `Error: ${message}`;
}

async function persist(state, status) {
  state.saving = true;
  renderSummary(state);
  try {
    const result = await state.client.save({
      context: state.context,
      assessment: state.assessment,
      etag: state.etag,
      status,
      itemScores: status === "skipped" ? {} : { ...state.answers },
      signal: state.abort.signal
    });
    if (mounted !== state) return;
    state.assessment = validateServerAssessment(result.assessment, state.context);
    state.etag = result.etag;
    state.answers = { ...state.assessment.itemScores };
    state.error = null;
    state.onAssessmentChange?.({ assessmentId: state.assessment.assessmentId, status: state.assessment.status });
    renderItems(state);
    state.root.querySelector("#severity-state").textContent = statusContent(state.assessment).text;
  } catch (error) {
    if (error.name !== "AbortError" && mounted === state) showError(state, error.message);
  } finally {
    if (mounted === state) {
      state.saving = false;
      renderSummary(state);
    }
  }
}

function handleClick(state, event) {
  const score = event.target.closest("[data-item][data-score]");
  if (score) {
    state.answers[score.dataset.item] = Number(score.dataset.score);
    renderItems(state);
    renderSummary(state);
    return;
  }
  const tab = event.target.closest("[data-tab]");
  if (tab) {
    state.tab = tab.dataset.tab;
    for (const button of state.root.querySelectorAll("[data-tab]")) button.setAttribute("aria-selected", String(button === tab));
    renderItems(state);
    return;
  }
  if (event.target.closest("#severity-complete")) persist(state, "completed");
  if (event.target.closest("#severity-pass")) persist(state, "skipped");
  if (event.target.closest("#severity-reset")) {
    state.answers = {};
    renderItems(state);
    renderSummary(state);
  }
}

export async function mount({ root, context, apiBasePath = DEFAULT_API_BASE_PATH, fetchImpl = fetch, onAssessmentChange } = {}) {
  unmount();
  if (!(root instanceof Element)) throw new Error("Severity mount requires a root Element.");
  root.innerHTML = shell();
  let normalized;
  try {
    normalized = normalizeContext(context);
  } catch (error) {
    const unavailable = { root, abort: new AbortController(), clickHandler: null };
    mounted = unavailable;
    showError(unavailable, error.message);
    for (const button of root.querySelectorAll("button")) button.disabled = true;
    return null;
  }
  const state = {
    root,
    context: normalized,
    client: createSeverityClient({ fetchImpl, apiBasePath }),
    assessment: null,
    etag: null,
    answers: {},
    tab: "P",
    saving: false,
    error: null,
    abort: new AbortController(),
    onAssessmentChange
  };
  mounted = state;
  state.clickHandler = event => handleClick(state, event);
  root.addEventListener("click", state.clickHandler);
  renderItems(state);
  renderSummary(state);
  if (normalized.assessmentId) {
    try {
      const result = await state.client.load(normalized.assessmentId, state.abort.signal);
      if (mounted !== state) return null;
      state.assessment = validateServerAssessment(result.assessment, normalized);
      state.etag = result.etag;
      state.answers = { ...state.assessment.itemScores };
      state.error = null;
      renderItems(state);
      renderSummary(state);
    } catch (error) {
      if (error.name !== "AbortError" && mounted === state) showError(state, error.message);
    }
  }
  return { unmount, getAssessmentId: () => state.assessment?.assessmentId || null };
}

export function unmount() {
  if (!mounted) return;
  mounted.abort.abort();
  if (mounted.clickHandler) mounted.root.removeEventListener("click", mounted.clickHandler);
  mounted.root.replaceChildren();
  mounted = null;
}

if (typeof window !== "undefined") window.InsightSeverity = Object.freeze({ mount, unmount });
