const CLIENT_VALIDATION_MESSAGES = {
  firstNameRequired: "First name is required.",
  firstNameMaxLength: "First name must be 80 characters or fewer.",
  lastNameRequired: "Last name is required.",
  lastNameMaxLength: "Last name must be 80 characters or fewer.",
  sex: "Select Male or Female.",
  dob: "Enter a date of birth at least 1 year ago and not in the future.",
  phoneNumber: "Enter exactly 10 digits, or leave it blank.",
  presentingComplaint: "Presenting complaint is required.",
  presentingComplaintMaxLength: "Presenting complaint must be 2000 characters or fewer.",
  provisionalDiagnosis: "Provisional diagnosis is required.",
  provisionalDiagnosisMaxLength: "Provisional diagnosis must be 240 characters or fewer."
};

const CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
const FIELD_INPUT_NAMES = {
  "demographics.patientCode": "patientCode",
  "demographics.firstName": "firstName",
  "demographics.lastName": "lastName",
  "demographics.sex": "sex",
  "demographics.dob": "dob",
  "demographics.phoneNumber": "phoneNumber",
  "clinical.presentingComplaint": "presentingComplaint",
  "clinical.provisionalDiagnosis": "provisionalDiagnosis",
  "clinical.treatmentHistory": "treatmentHistory",
  "clinical.allergies": "allergies",
  "clinical.currentMedications": "currentMedications",
  "clinical.riskFlags.suicidality": "suicidality",
  "clinical.riskFlags.substanceUse": "substanceUse"
};

function generateBrowserPatientCode() {
  let code = "";
  for (let i = 0; i < 6; i += 1) {
    code += CODE_ALPHABET[Math.floor(Math.random() * CODE_ALPHABET.length)];
  }
  return code;
}

function getRequiredElement(root, selector) {
  const element = root.querySelector(selector);

  if (!element) {
    throw new Error(`Add New Patient module is missing required element: ${selector}`);
  }

  return element;
}

async function readJsonResponse(response) {
  try {
    return await response.json();
  } catch {
    return {};
  }
}

function escapeHtml(value = "") {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
  })[character]);
}

// ponytail: client-side validation kept minimal — server is contract source. Duplicate rules risk drift.
function validatePatientPayload(patient) {
  const errors = {};
  const demographics = patient.demographics || {};
  const clinical = patient.clinical || {};

  if (!demographics.firstName) {
    errors["demographics.firstName"] = CLIENT_VALIDATION_MESSAGES.firstNameRequired;
  } else if (demographics.firstName.length > 80) {
    errors["demographics.firstName"] = CLIENT_VALIDATION_MESSAGES.firstNameMaxLength;
  }

  if (!demographics.lastName) {
    errors["demographics.lastName"] = CLIENT_VALIDATION_MESSAGES.lastNameRequired;
  } else if (demographics.lastName.length > 80) {
    errors["demographics.lastName"] = CLIENT_VALIDATION_MESSAGES.lastNameMaxLength;
  }

  if (!["Male", "Female"].includes(demographics.sex)) {
    errors["demographics.sex"] = CLIENT_VALIDATION_MESSAGES.sex;
  }

  if (!isValidDob(demographics.dob)) {
    errors["demographics.dob"] = CLIENT_VALIDATION_MESSAGES.dob;
  }

  if (demographics.phoneNumber && !/^\d{10}$/.test(demographics.phoneNumber)) {
    errors["demographics.phoneNumber"] = CLIENT_VALIDATION_MESSAGES.phoneNumber;
  }

  if (!clinical.presentingComplaint) {
    errors["clinical.presentingComplaint"] = CLIENT_VALIDATION_MESSAGES.presentingComplaint;
  } else if (clinical.presentingComplaint.length > 2000) {
    errors["clinical.presentingComplaint"] = CLIENT_VALIDATION_MESSAGES.presentingComplaintMaxLength;
  }

  if (!clinical.provisionalDiagnosis) {
    errors["clinical.provisionalDiagnosis"] = CLIENT_VALIDATION_MESSAGES.provisionalDiagnosis;
  } else if (clinical.provisionalDiagnosis.length > 240) {
    errors["clinical.provisionalDiagnosis"] = CLIENT_VALIDATION_MESSAGES.provisionalDiagnosisMaxLength;
  }

  return errors;
}

function parseListInput(value) {
  return String(value || "")
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function isValidDob(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(value || ""))) {
    return false;
  }
  const dob = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(dob.getTime()) || dob.toISOString().slice(0, 10) !== value) {
    return false;
  }
  const today = new Date();
  const age = today.getUTCFullYear() - dob.getUTCFullYear()
    - ((today.getUTCMonth() < dob.getUTCMonth()
      || (today.getUTCMonth() === dob.getUTCMonth() && today.getUTCDate() < dob.getUTCDate())) ? 1 : 0);
  return dob <= today && age >= 1;
}

function normalizePatientInput(input) {
  return {
    demographics: {
      patientCode: String(input.patientCode || "").trim().toUpperCase(),
      firstName: String(input.firstName || "").trim(),
      lastName: String(input.lastName || "").trim(),
      sex: String(input.sex || "").trim(),
      dob: String(input.dob || "").trim(),
      phoneNumber: String(input.phoneNumber || "").replace(/\D/g, "")
    },
    clinical: {
      presentingComplaint: String(input.presentingComplaint || "").trim(),
      provisionalDiagnosis: String(input.provisionalDiagnosis || "").trim(),
      treatmentHistory: parseListInput(input.treatmentHistory),
      allergies: parseListInput(input.allergies),
      currentMedications: parseListInput(input.currentMedications),
      riskFlags: {
        suicidality: String(input.suicidality || "suicidality_none").trim(),
        substanceUse: Boolean(input.substanceUse)
      }
    }
  };
}

function createAddNewPatientModule({ root = document, apiBaseUrl = window.ADD_NEW_PATIENT_API_BASE_URL || "" } = {}) {
  const normalizedApiBaseUrl = apiBaseUrl.replace(/\/$/, "");
  const dashboardView = getRequiredElement(root, "#dashboardView");
  const patientView = getRequiredElement(root, "#patientView");
  const activateModuleButton = getRequiredElement(root, "#activateModuleButton");
  const backButton = getRequiredElement(root, "#backButton");
  const patientForm = getRequiredElement(root, "#patientForm");
  const patientCode = getRequiredElement(root, "#patientCode");
  const regenerateCodeButton = getRequiredElement(root, "#regenerateCodeButton");
  const statusMessage = getRequiredElement(root, "#statusMessage");
  const followUpView = getRequiredElement(root, "#followUpView");
  const followUpSearchForm = getRequiredElement(root, "#followUpSearchForm");
  const followUpSearchStatus = getRequiredElement(root, "#followUpSearchStatus");
  const followUpResults = getRequiredElement(root, "#followUpResults");
  const followUpWorkspace = getRequiredElement(root, "#followUpWorkspace");
  const selectedPatient = getRequiredElement(root, "#selectedPatient");
  const encounterHistory = getRequiredElement(root, "#encounterHistory");
  const planHistory = getRequiredElement(root, "#planHistory");
  const followUpForm = getRequiredElement(root, "#followUpForm");
  const followUpStatus = getRequiredElement(root, "#followUpStatus");
  let followUpSelection = null;
  let followUpIdempotencyKey = null;

  function setStatus(message, tone = "") {
    statusMessage.textContent = message;

    if (tone) {
      statusMessage.dataset.tone = tone;
    } else {
      delete statusMessage.dataset.tone;
    }
  }

  function clearErrors() {
    root.querySelectorAll("[data-error-for]").forEach((node) => {
      node.textContent = "";
    });

    patientForm.querySelectorAll("[aria-invalid]").forEach((node) => {
      node.removeAttribute("aria-invalid");
    });

    root.querySelectorAll("[data-error-section]").forEach((node) => {
      node.hidden = true;
      const list = node.querySelector("[data-section-error-list]");
      if (list) {
        list.replaceChildren();
      }
    });
  }

  function showErrors(errors) {
    Object.entries(errors).forEach(([field, message]) => {
      const errorNode = root.querySelector(`[data-error-for="${field}"]`);
      const inputName = FIELD_INPUT_NAMES[field] || field.split(".").pop();
      const inputNode = patientForm.elements[inputName];
      const [section] = field.split(".");
      const sectionNode = root.querySelector(`[data-error-section="${section}"]`);

      if (errorNode) {
        errorNode.textContent = message;
      }

      if (sectionNode) {
        sectionNode.hidden = false;
        const list = sectionNode.querySelector("[data-section-error-list]");
        if (list) {
          const item = document.createElement("li");
          item.textContent = message;
          list.append(item);
        }
      }

      if (inputNode instanceof RadioNodeList) {
        inputNode.forEach((node) => node.setAttribute("aria-invalid", "true"));
      } else if (inputNode) {
        inputNode.setAttribute("aria-invalid", "true");
      }
    });
  }

  function setPatientCode(code = generateBrowserPatientCode()) {
    patientCode.value = code;
    patientCode.textContent = code;
  }

  function activateModule() {
    patientForm.reset();
    setPatientCode();
    clearErrors();
    setStatus("");
    dashboardView.hidden = true;
    patientView.hidden = false;
    patientForm.elements.firstName.focus();
  }

  function returnToDashboard() {
    patientView.hidden = true;
    dashboardView.hidden = false;
    activateModuleButton.focus();
  }

  function getPatientPayload() {
    const formData = new FormData(patientForm);

    return normalizePatientInput({
      patientCode: patientCode.value,
      firstName: formData.get("firstName"),
      lastName: formData.get("lastName"),
      sex: formData.get("sex"),
      dob: formData.get("dob"),
      phoneNumber: formData.get("phoneNumber"),
      presentingComplaint: formData.get("presentingComplaint"),
      provisionalDiagnosis: formData.get("provisionalDiagnosis"),
      treatmentHistory: formData.get("treatmentHistory"),
      allergies: formData.get("allergies"),
      currentMedications: formData.get("currentMedications"),
      suicidality: formData.get("suicidality"),
      substanceUse: formData.get("substanceUse") === "on"
    });
  }

  async function getCsrfToken() {
    const response = await fetch(`${normalizedApiBaseUrl}/api/add-new-patient/csrf`, {
      credentials: "include"
    });
    const result = await readJsonResponse(response);

    if (!response.ok || !result.csrfToken) {
      throw new Error("CSRF token unavailable");
    }

    return result.csrfToken;
  }

  async function apiJson(path, options = {}) {
    const response = await fetch(`${normalizedApiBaseUrl}${path}`, {
      credentials: "include",
      ...options,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) }
    });
    const result = await readJsonResponse(response);
    if (!response.ok) {
      throw new Error(result.title || result.detail || result.message || "Request failed.");
    }
    return { result, response };
  }

  async function searchFollowUpPatients(event) {
    event.preventDefault();
    const query = String(new FormData(followUpSearchForm).get("query") || "").trim();
    if (!query) return;
    followUpSearchStatus.textContent = "Searching patients...";
    followUpResults.replaceChildren();
    followUpWorkspace.hidden = true;
    try {
      const { result } = await apiJson("/api/add-new-patient/v2/patients/search", {
        method: "POST",
        headers: { "X-Schema-Version": "2.0.0" },
        body: JSON.stringify({ query, pageSize: 50 })
      });
      if (!result.items.length) {
        followUpSearchStatus.textContent = "No matching patients found.";
        return;
      }
      followUpSearchStatus.textContent = `${result.items.length} patient result${result.items.length === 1 ? "" : "s"}.`;
      followUpResults.innerHTML = result.items.map(({ patient, patientCodeAlias }) => `
        <button class="result-item" type="button" data-patient-id="${escapeHtml(patient.patientId)}">
          <strong>${escapeHtml(patient.lastName)}, ${escapeHtml(patient.firstName)}</strong>
          <span>Patient code ${escapeHtml(patientCodeAlias.patientCode)}</span>
        </button>
      `).join("");
      followUpResults.querySelectorAll("[data-patient-id]").forEach((button) => {
        button.addEventListener("click", () => loadFollowUpPatient(button.dataset.patientId));
      });
    } catch (error) {
      followUpSearchStatus.textContent = `Patient search failed: ${error.message}`;
    }
  }

  function renderEncounterHistory(items) {
    encounterHistory.innerHTML = items.length ? items.map(({ encounter, followUpDelta }) => `
      <div class="history-item">
        <strong>${encounter.encounterType === "follow-up" ? "Follow-up" : "Initial"} Encounter</strong>
        <span>${escapeHtml(new Date(encounter.occurredAt).toLocaleString())}</span>
        <span>${followUpDelta ? `${followUpDelta.changes.length} recorded change(s)` : "Initial intake"}</span>
      </div>
    `).join("") : '<p class="status-message">No Encounter history available.</p>';
  }

  function renderPlanHistory(items) {
    planHistory.innerHTML = items.length ? items.map(({ planView, finalPlan, supersession }) => `
      <div class="history-item">
        <strong>${finalPlan ? "Final Treatment Plan" : "Primary Treatment Plan"}</strong>
        <span>${escapeHtml(finalPlan ? finalPlan.finalizedAt : planView.primaryPlan.createdAt || "Date unavailable")}</span>
        <span>${supersession ? "Superseded by a later plan" : finalPlan ? "Immutable final plan" : "Review in progress"}</span>
      </div>
    `).join("") : '<p class="status-message">No Treatment Plans available.</p>';
  }

  async function loadFollowUpPatient(patientId) {
    followUpSearchStatus.textContent = "Loading patient history and Treatment Plans...";
    followUpWorkspace.hidden = true;
    const patientRequest = apiJson(`/api/add-new-patient/v2/patients/${encodeURIComponent(patientId)}`);
    const historyRequest = apiJson(`/api/add-new-patient/v2/patients/${encodeURIComponent(patientId)}/history`);
    const planRequest = apiJson(`/api/treatment-plan/v1/patients/${encodeURIComponent(patientId)}/plans`);
    const [patientResult, historyResult, planResult] = await Promise.allSettled([
      patientRequest, historyRequest, planRequest
    ]);
    if (patientResult.status === "rejected") {
      followUpSearchStatus.textContent = `Patient load failed: ${patientResult.reason.message}`;
      return;
    }
    const patient = patientResult.value.result;
    const history = historyResult.status === "fulfilled" ? historyResult.value.result.items : [];
    const plans = planResult.status === "fulfilled" ? planResult.value.result.items : [];
    const finalPlans = plans.map((item) => item.finalPlan).filter(Boolean);
    followUpSelection = {
      patient,
      patientEtag: patientResult.value.response.headers.get("ETag"),
      history,
      finalPlans
    };
    followUpIdempotencyKey = null;
    selectedPatient.textContent = `${patient.lastName}, ${patient.firstName}`;
    renderEncounterHistory(history);
    renderPlanHistory(plans);
    const encounterSelect = followUpForm.elements.priorEncounterId;
    encounterSelect.innerHTML = history.map(({ encounter }) => `
      <option value="${escapeHtml(encounter.encounterId)}">${encounter.encounterType} - ${escapeHtml(new Date(encounter.occurredAt).toLocaleString())}</option>
    `).join("");
    const planSelect = followUpForm.elements.priorFinalPlanId;
    planSelect.innerHTML = finalPlans.map((plan) => `
      <option value="${escapeHtml(plan.planId)}" data-encounter-id="${escapeHtml(plan.encounterId)}">Finalized ${escapeHtml(new Date(plan.finalizedAt).toLocaleString())}</option>
    `).join("");
    if (finalPlans[0]) encounterSelect.value = finalPlans[0].encounterId;
    followUpWorkspace.hidden = false;
    const failures = [];
    if (historyResult.status === "rejected") failures.push(`Encounter history failed: ${historyResult.reason.message}`);
    if (planResult.status === "rejected") failures.push(`Treatment Plan retrieval failed: ${planResult.reason.message}`);
    if (!finalPlans.length && !failures.length) failures.push("A prior Final Treatment Plan is required before follow-up capture.");
    followUpSearchStatus.textContent = failures.join(" ") || "Patient history loaded.";
    followUpForm.querySelector('button[type="submit"]').disabled = Boolean(failures.length || !followUpSelection.patientEtag);
  }

  function syncPriorEncounter() {
    const option = followUpForm.elements.priorFinalPlanId.selectedOptions[0];
    if (option?.dataset.encounterId) followUpForm.elements.priorEncounterId.value = option.dataset.encounterId;
  }

  async function submitFollowUp(event) {
    event.preventDefault();
    if (!followUpSelection?.patientEtag) return;
    const data = new FormData(followUpForm);
    const occurredAt = new Date(String(data.get("occurredAt")));
    if (Number.isNaN(occurredAt.getTime())) {
      followUpStatus.textContent = "Enter a valid follow-up date and time.";
      return;
    }
    const payload = {
      priorEncounterId: data.get("priorEncounterId"),
      priorFinalPlanId: data.get("priorFinalPlanId"),
      occurredAt: occurredAt.toISOString(),
      changes: [{
        domain: data.get("domain"),
        summary: String(data.get("summary") || "").trim(),
        sourceResourceId: String(data.get("sourceResourceId") || "").trim()
      }]
    };
    followUpStatus.textContent = "Creating Follow-up Encounter...";
    followUpIdempotencyKey ||= `follow-up-${crypto.randomUUID()}`;
    try {
      const csrfToken = await getCsrfToken();
      const { result } = await apiJson(
        `/api/add-new-patient/v2/patients/${encodeURIComponent(followUpSelection.patient.patientId)}/follow-ups`,
        {
          method: "POST",
          headers: {
            "X-CSRF-Token": csrfToken,
            "X-Schema-Version": "2.0.0",
            "Idempotency-Key": followUpIdempotencyKey,
            "If-Match": followUpSelection.patientEtag
          },
          body: JSON.stringify(payload)
        }
      );
      followUpIdempotencyKey = null;
      followUpStatus.textContent = "Follow-up Encounter and Delta saved. Treatment Plan history remains unchanged until a successor is generated.";
      followUpSelection.history.unshift({ encounter: result.encounter, followUpDelta: result.followUpDelta });
      renderEncounterHistory(followUpSelection.history);
      followUpForm.querySelector('button[type="submit"]').disabled = true;
    } catch (error) {
      followUpStatus.textContent = `Follow-up was not saved: ${error.message}`;
    }
  }

  async function savePatient(payload) {
    const csrfToken = await getCsrfToken();
    const response = await fetch(`${normalizedApiBaseUrl}/api/patients`, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken
      },
      body: JSON.stringify(payload)
    });

    const result = await readJsonResponse(response);

    if (!response.ok) {
      return {
        ok: false,
        errors: result.errors || {},
        message: result.message || "Patient could not be saved."
      };
    }

    return {
      ok: true,
      patient: result.patient
    };
  }

  async function submitPatient(event) {
    event.preventDefault();
    clearErrors();

    const payload = getPatientPayload();
    const clientErrors = validatePatientPayload(payload);

    if (Object.keys(clientErrors).length > 0) {
      showErrors(clientErrors);
      setStatus("Review the highlighted fields.", "error");
      return;
    }

    setStatus("Saving patient...");

    try {
      const result = await savePatient(payload);

      if (!result.ok) {
        showErrors(result.errors);
        setStatus(result.message, "error");
        return;
      }

      setStatus(`Patient ${result.patient.patientCode} saved.`, "success");
      patientForm.reset();
      setPatientCode();
      patientForm.elements.firstName.focus();
    } catch {
      setStatus("Patient could not be saved. Check your connection and try again.", "error");
    }
  }

  function formatPhoneInput(event) {
    const digits = event.target.value.replace(/\D/g, "").slice(0, 10);
    const parts = [];

    if (digits.length > 0) {
      parts.push(digits.slice(0, 3));
    }

    if (digits.length > 3) {
      parts.push(digits.slice(3, 6));
    }

    if (digits.length > 6) {
      parts.push(digits.slice(6, 10));
    }

    event.target.value = parts.join("-");
  }

  function regenerateCode() {
    setPatientCode();
    setStatus("New patient code generated.");
  }

  activateModuleButton.addEventListener("click", activateModule);
  backButton.addEventListener("click", returnToDashboard);
  regenerateCodeButton.addEventListener("click", regenerateCode);
  patientForm.addEventListener("submit", submitPatient);
  patientForm.elements.phoneNumber.addEventListener("input", formatPhoneInput);
  followUpSearchForm.addEventListener("submit", searchFollowUpPatients);
  followUpForm.addEventListener("submit", submitFollowUp);
  followUpForm.elements.priorFinalPlanId.addEventListener("change", syncPriorEncounter);

  if (location.pathname.startsWith("/modules/patient-follow-up")) {
    dashboardView.hidden = true;
    patientView.hidden = true;
    followUpView.hidden = false;
  }

  return {
    activate: activateModule,
    back: returnToDashboard,
    generateCode: generateBrowserPatientCode,
    destroy() {
      activateModuleButton.removeEventListener("click", activateModule);
      backButton.removeEventListener("click", returnToDashboard);
      regenerateCodeButton.removeEventListener("click", regenerateCode);
      patientForm.removeEventListener("submit", submitPatient);
      patientForm.elements.phoneNumber.removeEventListener("input", formatPhoneInput);
      followUpSearchForm.removeEventListener("submit", searchFollowUpPatients);
      followUpForm.removeEventListener("submit", submitFollowUp);
      followUpForm.elements.priorFinalPlanId.removeEventListener("change", syncPriorEncounter);
    }
  };
}

window.createAddNewPatientModule = createAddNewPatientModule;

if (window.ADD_NEW_PATIENT_AUTO_INIT !== false) {
  window.AddNewPatientModule = createAddNewPatientModule();
}
