const state = {
  activation: null,
  returnUrl: "/dashboard"
};

const elements = {
  status: document.querySelector("#status-pill"),
  activationPanel: document.querySelector("#activation-panel"),
  activationForm: document.querySelector("#activation-form"),
  activationCode: document.querySelector("#activation-code"),
  historyForm: document.querySelector("#history-form"),
  activeCode: document.querySelector("#active-code"),
  pastMedicalHistory: document.querySelector("#past-medical-history"),
  medicationList: document.querySelector("#medication-list"),
  addMedication: document.querySelector("#add-medication"),
  backDashboard: document.querySelector("#back-dashboard"),
  resultPanel: document.querySelector("#result-panel"),
  resultSummary: document.querySelector("#result-summary"),
  resultDashboard: document.querySelector("#result-dashboard"),
  newEntry: document.querySelector("#new-entry"),
  antipsychoticDetails: document.querySelector("#antipsychotic-details"),
  antipsychotic: document.querySelector("#antipsychotic"),
  clozapineContraindications: document.querySelector("#clozapine-contraindications")
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data?.error?.message || "Request failed");
  }
  return data;
}

function setStatus(label, mode = "") {
  elements.status.textContent = label;
  elements.status.className = `status-pill ${mode}`.trim();
}

function showError(message) {
  const existing = document.querySelector(".toast");
  if (existing) existing.remove();
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = message;
  document.querySelector(".workspace").insertBefore(toast, elements.activationPanel.nextSibling);
  setStatus("Needs attention", "error");
}

function clearError() {
  const existing = document.querySelector(".toast");
  if (existing) existing.remove();
}

function showForm(activation) {
  clearError();
  state.activation = activation;
  state.returnUrl = activation.context?.returnUrl || "/dashboard";
  elements.activeCode.value = activation.code;
  elements.activationPanel.classList.add("hidden");
  elements.resultPanel.classList.add("hidden");
  elements.historyForm.classList.remove("hidden");
  setStatus("Active", "active");
}

function addMedicationRow(value = {}) {
  if (elements.medicationList.children.length >= 20) { showError("A maximum of 20 drugs can be added."); return; }
  const row = document.createElement("div");
  row.className = "medication-row";
  row.innerHTML = `
    <div>
      <label>Drug</label>
      <input class="med-name" type="text" maxlength="160" placeholder="Drug name" value="${escapeAttribute(value.name || "")}">
    </div>
    <div>
      <label>Dose</label>
      <input class="med-dose" type="text" placeholder="Dose" value="${escapeAttribute(value.dose || "")}">
    </div>
    <div>
      <label>Route</label>
      <input class="med-route" type="text" placeholder="Oral" value="${escapeAttribute(value.route || "")}">
    </div>
    <div>
      <label>Frequency</label>
      <input class="med-frequency" type="text" placeholder="Daily" value="${escapeAttribute(value.frequency || "")}">
    </div>
    <button class="remove-medication" type="button" aria-label="Remove medication">x</button>
  `;
  row.querySelector(".remove-medication").addEventListener("click", () => { row.remove(); elements.addMedication.disabled = false; });
  elements.medicationList.appendChild(row);
  elements.addMedication.disabled = elements.medicationList.children.length >= 20;
}

function escapeAttribute(value) {
  return String(value).replaceAll("&", "&amp;").replaceAll('"', "&quot;").replaceAll("<", "&lt;");
}

function getSelectedPastMedicalHistory() {
  return Array.from(elements.pastMedicalHistory.selectedOptions).map((option) => option.value);
}

function getMedications() {
  return Array.from(elements.medicationList.querySelectorAll(".medication-row"))
    .map((row) => ({
      name: row.querySelector(".med-name").value.trim(),
      dose: row.querySelector(".med-dose").value.trim(),
      route: row.querySelector(".med-route").value.trim(),
      frequency: row.querySelector(".med-frequency").value.trim()
    }))
    .filter((medication) => medication.name || medication.dose || medication.route || medication.frequency);
}

async function loadOptions() {
  const options = await api("/api/internal/medical-history/options");
  elements.pastMedicalHistory.innerHTML = "";
  options.pastMedicalHistory.forEach((label) => {
    const option = document.createElement("option");
    option.value = label;
    option.textContent = label;
    elements.pastMedicalHistory.appendChild(option);
  });
  options.antipsychotics.forEach((label) => elements.antipsychotic.add(new Option(label, label)));
  options.clozapineContraindications.forEach((label) => {
    const item = document.createElement("label");
    item.innerHTML = `<input type="checkbox" value="${escapeAttribute(label)}"> ${label}`;
    elements.clozapineContraindications.appendChild(item);
  });
}


function isYes(name) { return document.querySelector(`input[name="${name}"]:checked`)?.value === "yes"; }
function updateConditionalFields() {
  const prior = isYes("prior-antipsychotic-therapy");
  const contraindication = isYes("clozapine-contraindication");
  elements.antipsychoticDetails.classList.toggle("hidden", !prior);
  elements.antipsychotic.required = prior;
  elements.clozapineContraindications.classList.toggle("hidden", !contraindication);
  if (!contraindication) elements.clozapineContraindications.querySelectorAll("input").forEach((input) => { input.checked = false; });
}
async function activateFromCode(code) {
  if (!/^[A-Za-z0-9]{6}$/.test(code)) {
    showError("Enter a valid 6-character activation code.");
    return;
  }
  const activation = await api("/api/internal/medical-history/activate", {
    method: "POST",
    body: JSON.stringify({
      code,
      requestedByModule: "standalone-launcher",
      returnUrl: "/dashboard"
    })
  });
  window.history.replaceState(null, "", `/?code=${encodeURIComponent(activation.code)}`);
  showForm(activation);
}

async function restoreActivationFromUrl() {
  const code = new URLSearchParams(window.location.search).get("code");
  if (!code) {
    setStatus("Waiting");
    addMedicationRow();
    return;
  }

  try {
    const activation = await api(`/api/internal/medical-history/activation/${encodeURIComponent(code)}`);
    showForm(activation);
    if (elements.medicationList.children.length === 0) addMedicationRow();
  } catch (error) {
    elements.activationCode.value = code;
    showError(error.message);
  }
}

function goToDashboard() {
  window.location.assign(state.returnUrl || "/dashboard");
}

elements.activationForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await activateFromCode(elements.activationCode.value.trim());
  } catch (error) {
    showError(error.message);
  }
});

elements.addMedication.addEventListener("click", () => addMedicationRow());
document.querySelectorAll('input[name="prior-antipsychotic-therapy"], input[name="clozapine-contraindication"]').forEach((input) => input.addEventListener("change", updateConditionalFields));
elements.backDashboard.addEventListener("click", goToDashboard);
elements.resultDashboard.addEventListener("click", goToDashboard);
elements.newEntry.addEventListener("click", () => {
  window.location.assign("/");
});

elements.historyForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearError();

  const medications = getMedications();
  const invalidMedication = medications.some((medication) => !medication.name);
  if (invalidMedication) {
    showError("Medication name is required when a medication row has data.");
    return;
  }

  try {
    const submission = await api("/api/internal/medical-history/submissions", {
      method: "POST",
      body: JSON.stringify({
        code: elements.activeCode.value,
        pastMedicalHistory: getSelectedPastMedicalHistory(),
        drugs: medications,
        substantialSuicideRisk: isYes("substantial-suicide-risk"),
        priorAntipsychoticTherapy: isYes("prior-antipsychotic-therapy"),
        priorAntipsychoticTherapySuccessful: isYes("prior-antipsychotic-therapy") ? isYes("antipsychotic-successful") : null,
        antipsychotic: isYes("prior-antipsychotic-therapy") ? elements.antipsychotic.value : null,
        clozapineContraindication: isYes("clozapine-contraindication"),
        clozapineContraindications: Array.from(elements.clozapineContraindications.querySelectorAll("input:checked")).map((input) => input.value),
        recurrentNonAdherenceDeterioration: isYes("recurrent-non-adherence-deterioration"),
        submittedBy: "current-user",
        source: "standalone-ui"
      })
    });

    elements.historyForm.classList.add("hidden");
    elements.resultPanel.classList.remove("hidden");
    elements.resultSummary.textContent = `Submission ${submission.submissionId} was saved for activation code ${submission.code}.`;
    setStatus("Submitted", "active");
  } catch (error) {
    showError(error.message);
  }
});

loadOptions()
  .then(restoreActivationFromUrl)
  .catch((error) => showError(error.message));



