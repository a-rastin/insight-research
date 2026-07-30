(function () {
  "use strict";

  const STORAGE_KEYS = {
    meds: "insight-ddi-meds",
    audit: "insight-ddi-audit",
    reviews: "insight-ddi-reviews",
    localKb: "insight-ddi-local-kb",
    sessionCode: "insight-ddi-session-code"
  };

  const engine = window.DDIEngine;
  const kbPersistence = window.DDIKbPersistence;
  const storage = window.DDIStorage.browserStorageAdapter(window.localStorage);
  let storageFailure = null;
  const bundledKb = window.DDI_ACTIVE_KB || createEmptyKb();
  const startupRebase = kbPersistence.rebase(bundledKb, loadLocalKb());
  let kb = startupRebase.kb;
  if (startupRebase.migrated) writeJson(STORAGE_KEYS.localKb, startupRebase.revision);
  let index = engine.buildIndex(kb);
  let medications = readJson(STORAGE_KEYS.meds, []);
  let sessionCode = getSessionCode();
  let latestResult = null;
  let selectedReviewId = kb.interactions[0]?.id || null;

  const els = {
    storageFailure: document.getElementById("storageFailure"),
    kbSummary: document.getElementById("kbSummary"),
    revisionPill: document.getElementById("revisionPill"),
    sessionCode: document.getElementById("sessionCode"),
    resultSummary: document.getElementById("resultSummary"),
    tabs: document.querySelectorAll("[data-view]"),
    views: document.querySelectorAll(".view"),
    medicationForm: document.getElementById("medicationForm"),
    drugInput: document.getElementById("drugInput"),
    doseInput: document.getElementById("doseInput"),
    drugSuggestions: document.getElementById("drugSuggestions"),
    doseSuggestions: document.getElementById("doseSuggestions"),
    medicationList: document.getElementById("medicationList"),
    checkButton: document.getElementById("checkButton"),
    alertsList: document.getElementById("alertsList"),
    unresolvedBox: document.getElementById("unresolvedBox"),
    reviewSearch: document.getElementById("reviewSearch"),
    reviewList: document.getElementById("reviewList"),
    reviewStatusBadge: document.getElementById("reviewStatusBadge"),
    reviewSeverity: document.getElementById("reviewSeverity"),
    reviewMechanism: document.getElementById("reviewMechanism"),
    reviewEffect: document.getElementById("reviewEffect"),
    reviewRecommendation: document.getElementById("reviewRecommendation"),
    reviewMonitoring: document.getElementById("reviewMonitoring"),
    reviewerName: document.getElementById("reviewerName"),
    approveButton: document.getElementById("approveButton"),
    rejectButton: document.getElementById("rejectButton"),
    saveDraftButton: document.getElementById("saveDraftButton"),
    activateRevisionButton: document.getElementById("activateRevisionButton"),
    sourcePath: document.getElementById("sourcePath"),
    sourceExcerpt: document.getElementById("sourceExcerpt"),
    uploadReportForm: document.getElementById("uploadReportForm"),
    reportFileInput: document.getElementById("reportFileInput"),
    uploadStatus: document.getElementById("uploadStatus"),
    addInteractionForm: document.getElementById("addInteractionForm"),
    newDrugA: document.getElementById("newDrugA"),
    newDrugB: document.getElementById("newDrugB"),
    newSeverity: document.getElementById("newSeverity"),
    newEffect: document.getElementById("newEffect"),
    newRecommendation: document.getElementById("newRecommendation"),
    auditList: document.getElementById("auditList"),
    exportAuditButton: document.getElementById("exportAuditButton"),
    exportResultsButton: document.getElementById("exportResultsButton"),
    overrideDialog: document.getElementById("overrideDialog"),
    overrideForm: document.getElementById("overrideForm"),
    overrideReason: document.getElementById("overrideReason"),
    overrideError: document.getElementById("overrideError"),
    cancelOverrideButton: document.getElementById("cancelOverrideButton")
  };

  let pendingOverrideAlertId = null;

  function createEmptyKb() {
    return {
      schemaVersion: "1.0.0",
      version: "empty",
      status: "empty",
      drugs: [],
      interactions: [],
      reports: [],
      clinicalUse: { allowedForProduction: false, reason: "No active KB loaded." }
    };
  }

  function readJson(key, fallback) {
    const result = storage.read(key, fallback);
    if (!result.ok) reportStorageFailure(result);
    return result.ok ? result.value : fallback;
  }

  function writeJson(key, value) {
    const result = storage.write(key, value);
    if (!result.ok) reportStorageFailure(result);
    return result;
  }

  function reportStorageFailure(result) {
    const reason = result.reason === "quota_exceeded" ? "browser storage is full"
      : result.reason === "corrupt_json" ? "saved browser data is corrupt"
      : "browser storage is disabled or unavailable";
    storageFailure = `Changes could not be saved because ${reason}. Reload before continuing to avoid losing work.`;
    const banner = document.getElementById("storageFailure");
    if (banner) {
      banner.textContent = storageFailure;
      banner.hidden = false;
    }
  }

  function clearStorageFailure() {
    storageFailure = null;
    els.storageFailure.textContent = "";
    els.storageFailure.hidden = true;
  }

  function getSessionCode() {
    const existing = sessionStorage.getItem(STORAGE_KEYS.sessionCode);
    if (existing) return existing;
    const datePart = new Date().toISOString().slice(2, 10).replace(/-/g, "");
    const randomPart = Math.random().toString(36).slice(2, 8).toUpperCase();
    const code = `DDI-${datePart}-${randomPart}`;
    sessionStorage.setItem(STORAGE_KEYS.sessionCode, code);
    return code;
  }

  function loadLocalKb() {
    return readJson(STORAGE_KEYS.localKb, null);
  }

  function refreshHeader() {
    const approved = kb.interactions.filter((item) => item.reviewStatus === "approved").length;
    const pending = kb.interactions.filter((item) => item.reviewStatus !== "approved").length;
    const conflictSuffix = kb.rebaseConflicts?.length ? `; ${kb.rebaseConflicts.length} rebase conflict(s) require review` : "";
    els.kbSummary.textContent = (approved
      ? `${kb.drugs.length} drugs, ${approved} approved interaction records, ${pending} awaiting review`
      : `${kb.drugs.length} drugs - no approved interactions available; ${pending} awaiting review`) + conflictSuffix;
    els.revisionPill.textContent = kb.version;
    els.revisionPill.title = kb.clinicalUse?.reason || "";
    els.sessionCode.textContent = sessionCode;
    updateResultSummary();
  }

  function setView(name) {
    els.tabs.forEach((button) => button.classList.toggle("active", button.dataset.view === name));
    els.views.forEach((view) => view.classList.toggle("active", view.id === `${name}View`));
    if (name === "audit") renderAudit();
    if (name === "admin") renderReviewList();
  }

  function renderSuggestions(query) {
    const suggestions = suggestSourceDrugs(query || "", 20);
    els.drugSuggestions.innerHTML = suggestions
      .map((drug) => `<option value="${escapeHtml(drug.name)}"></option>`)
      .join("");
  }

  function sourceDrugPool() {
    const reportDrugIds = new Set((kb.reports || []).map((report) => report.drugId).filter(Boolean));
    const sourceDrugs = kb.drugs.filter((drug) => drug.isSourceReportDrug || reportDrugIds.has(drug.id));
    return (sourceDrugs.length ? sourceDrugs : kb.drugs)
      .filter((drug) => drug?.name && !looksLikeParsedTextFragment(drug.name))
      .sort((a, b) => a.name.localeCompare(b.name));
  }

  function looksLikeParsedTextFragment(value) {
    const normalized = engine.normalizeName(value);
    if (!normalized) return true;
    if (normalized.length > 55) return true;
    if (/^\d/.test(normalized)) return true;
    if (/\b(?:recommended|monitor|patients|dosing|assay|study|initially|postoperatively|discontinuation)\b/i.test(normalized)) return true;
    return false;
  }

  function suggestSourceDrugs(query, limit) {
    const normalized = engine.normalizeName(query);
    const pool = sourceDrugPool();
    if (!normalized) return pool.slice(0, limit);

    return pool
      .map((drug) => {
        const name = engine.normalizeName(drug.name);
        const exact = name === normalized;
        const startsWith = name.startsWith(normalized);
        const contains = name.includes(normalized);
        const score = exact ? 0 : startsWith ? 1 : contains ? 2 : 99;
        return { drug, score };
      })
      .filter((row) => row.score < 99)
      .sort((a, b) => a.score - b.score || a.drug.name.localeCompare(b.drug.name))
      .slice(0, limit)
      .map((row) => row.drug);
  }

  function selectedDrugForDose() {
    const normalized = engine.normalizeName(els.drugInput.value);
    if (!normalized) return null;
    const resolution = engine.resolveDrug(els.drugInput.value, index);
    return resolution.status === "resolved" ? resolution.drug : null;
  }

  function renderDoseSuggestions() {
    const drug = selectedDrugForDose();
    const suggestions = Array.isArray(drug?.doseSuggestions) ? drug.doseSuggestions : [];
    els.doseSuggestions.innerHTML = suggestions
      .slice(0, 30)
      .map((dose) => `<option value="${escapeHtml(dose)}"></option>`)
      .join("");
    if (!els.doseInput.value && suggestions.length) {
      els.doseInput.placeholder = suggestions[0];
    } else {
      els.doseInput.placeholder = "Choose or enter dosage";
    }
  }

  function renderMedications() {
    if (!medications.length) {
      els.medicationList.innerHTML = "<li class=\"notice\">No patient medications added.</li>";
      return;
    }

    els.medicationList.innerHTML = medications.map((med, idx) => `
      <li class="med-item">
        <div>
          <strong>${escapeHtml(med.name)}</strong>
          <span>${escapeHtml(med.dose || "Dose not specified")}</span>
        </div>
        <button data-remove-med="${idx}" aria-label="Remove ${escapeHtml(med.name)}">Remove</button>
      </li>
    `).join("");
  }

  function checkNow() {
    latestResult = engine.checkInteractions(medications, kb, { index });
    latestResult.sessionCode = sessionCode;
    renderAlerts(latestResult);
    recordShownAlerts(latestResult);
    updateResultSummary();
  }

  function updateResultSummary() {
    if (!latestResult) {
      els.resultSummary.textContent = medications.length ? `${medications.length} medication(s)` : "Not checked";
      return;
    }
    els.resultSummary.textContent = `${latestResult.alerts.length} alert(s), ${latestResult.unresolved.length} unresolved, ${latestResult.ambiguous.length} ambiguous`;
  }

  function renderAlerts(result) {
    const identityMessages = [];
    if (result.unresolved.length) {
      identityMessages.push(`Not found in active KB: ${result.unresolved.map((med) => med.name).join(", ")}`);
    }
    for (const match of result.ambiguous) {
      const candidates = match.candidates.map((drug) => `${drug.name} (${drug.id})`).join(", ");
      identityMessages.push(`Ambiguous medication "${match.medication.name}". Choose one identity: ${candidates}`);
    }
    els.unresolvedBox.classList.toggle("hidden", identityMessages.length === 0);
    els.unresolvedBox.textContent = identityMessages.join(" ");

    if (!result.alerts.length) {
      els.alertsList.innerHTML = "<div class=\"panel\">No recorded interactions found for the current medication list.</div>";
      return;
    }

    els.alertsList.innerHTML = result.alerts.map((alert) => `
      <article class="alert-card ${alert.severity}">
        <div class="alert-head">
          <h3>${escapeHtml(alert.interactingDrugs.join(" + "))}</h3>
          <span class="severity-badge ${alert.severity}">${escapeHtml(alert.severityLabel)}</span>
        </div>
        <p><strong>Clinical concern:</strong> ${escapeHtml(alert.clinicalConcern)}</p>
        <p><strong>Recommended psychiatrist action:</strong> ${escapeHtml(alert.recommendedAction)}</p>
        ${alert.monitoring ? `<p><strong>Monitoring:</strong> ${escapeHtml(alert.monitoring)}</p>` : ""}
        <p><strong>Review status:</strong> ${escapeHtml(alert.reviewStatus.replaceAll("_", " "))}</p>
        <div class="evidence">
          <strong>Evidence/source:</strong>
          <p>${escapeHtml(alert.evidenceSource || "Source report excerpt")}</p>
          <p>${escapeHtml(alert.evidenceExcerpt)}</p>
        </div>
        <div class="alert-actions">
          <button data-alert-action="accepted" data-alert-id="${alert.id}">Accepted</button>
          <button data-alert-action="dismissed" data-alert-id="${alert.id}">Dismissed</button>
          <button data-alert-action="overridden" data-alert-id="${alert.id}">Override</button>
        </div>
      </article>
    `).join("");
  }

  function recordAlertAction(alertId, action) {
    const alert = latestResult?.alerts.find((item) => item.id === alertId);
    if (!alert) return;
    if (action === "overridden") {
      pendingOverrideAlertId = alertId;
      els.overrideForm.reset();
      els.overrideError.textContent = "";
      els.overrideDialog.showModal();
      els.overrideReason.focus();
      return;
    }
    persistAlertAction(alert, action, "");
  }

  function persistAlertAction(alert, action, reason) {
    const audit = readJson(STORAGE_KEYS.audit, []);
    audit.unshift(engine.createAuditEntry(alert, action, {
      reason,
      clinician: "standalone-user",
      patientId: "local-test-patient",
      sessionCode
    }));
    writeJson(STORAGE_KEYS.audit, audit.slice(0, 250));
    renderAudit();
  }

  function cancelOverride() {
    pendingOverrideAlertId = null;
    els.overrideForm.reset();
    els.overrideError.textContent = "";
    els.overrideDialog.close();
  }

  function recordShownAlerts(result) {
    if (!result?.alerts?.length) return;
    const audit = readJson(STORAGE_KEYS.audit, []);
    const checkedAt = result.checkedAt || new Date().toISOString();
    const shownEntries = result.alerts.map((alert) => ({
      ...engine.createAuditEntry(alert, "shown", {
        clinician: "standalone-user",
        patientId: "local-test-patient",
        sessionCode
      }),
      createdAt: checkedAt
    }));
    writeJson(STORAGE_KEYS.audit, shownEntries.concat(audit).slice(0, 250));
    renderAudit();
  }

  function renderReviewList() {
    const query = engine.normalizeName(els.reviewSearch.value);
    const records = kb.interactions.filter((record) => {
      if (!query) return true;
      return engine.normalizeName(`${record.drugAName} ${record.drugBName} ${record.severity} ${record.evidenceSource}`).includes(query);
    }).slice(0, 300);

    els.reviewList.innerHTML = records.map((record) => `
      <button class="review-row ${record.id === selectedReviewId ? "active" : ""}" data-review-id="${record.id}">
        <strong>${escapeHtml(record.drugAName)} + ${escapeHtml(record.drugBName)}</strong>
        <span>${escapeHtml(record.severity)} Â· ${escapeHtml((record.reviewStatus || "unknown").replaceAll("_", " "))}</span>
        <span>${escapeHtml(record.mechanism || "No mechanism parsed")}</span>
      </button>
    `).join("");

    renderReviewDetail();
  }

  function selectedRecord() {
    return kb.interactions.find((record) => record.id === selectedReviewId) || null;
  }

  function renderReviewDetail() {
    const record = selectedRecord();
    if (!record) {
      els.reviewStatusBadge.textContent = "Select a record";
      els.sourcePath.textContent = "";
      els.sourceExcerpt.textContent = "";
      return;
    }

    els.reviewStatusBadge.textContent = (record.reviewStatus || "unknown").replaceAll("_", " ");
    els.reviewSeverity.value = record.severity || "unknown";
    els.reviewMechanism.value = record.mechanism || "";
    els.reviewEffect.value = record.clinicalEffect || "";
    els.reviewRecommendation.value = record.recommendation || "";
    els.reviewMonitoring.value = record.monitoring || "";
    els.reviewerName.value = record.reviewedBy || els.reviewerName.value || "";
    els.sourcePath.textContent = record.evidenceSource || "Source report excerpt";
    els.sourceExcerpt.textContent = record.evidenceExcerpt || "";
  }

  function saveReview(status) {
    const record = selectedRecord();
    if (!record) return;
    const snapshot = structuredClone(kb);
    record.severity = els.reviewSeverity.value;
    record.mechanism = els.reviewMechanism.value.trim();
    record.clinicalEffect = els.reviewEffect.value.trim();
    record.recommendation = els.reviewRecommendation.value.trim();
    record.monitoring = els.reviewMonitoring.value.trim();
    record.reviewStatus = status || record.reviewStatus || "edited_pending_review";
    if (status === "approved") {
      record.reviewedBy = els.reviewerName.value.trim() || "standalone-reviewer";
      record.reviewedAt = new Date().toISOString();
    }
    if (status === "rejected") {
      record.reviewedBy = els.reviewerName.value.trim() || "standalone-reviewer";
      record.reviewedAt = new Date().toISOString();
    }
    if (!persistKb()) {
      kb = snapshot;
      renderReviewDetail();
      return;
    }
    renderReviewList();
    checkNow();
  }

  function activateRevision() {
    const approved = kb.interactions.filter((record) => record.reviewStatus === "approved").length;
    if (!approved) {
      els.uploadStatus.textContent = "Activation blocked: no approved interactions available.";
      return;
    }
    const snapshot = structuredClone(kb);
    kb.version = `ikb-local-${new Date().toISOString().slice(0, 10)}-${approved}`;
    kb.status = "active_local_revision";
    kb.activatedAt = new Date().toISOString();
    kb.clinicalUse = {
      allowedForProduction: false,
      reason: "Local standalone activation for testing; production activation should be server-side and permissioned."
    };
    for (const record of kb.interactions) record.knowledgeBaseVersion = kb.version;
    if (!persistKb()) {
      kb = snapshot;
      return;
    }
    refreshHeader();
    renderReviewList();
    checkNow();
  }

  function persistKb() {
    const result = writeJson(STORAGE_KEYS.localKb, kbPersistence.createRevision(bundledKb, kb));
    if (!result.ok) return false;
    clearStorageFailure();
    index = engine.buildIndex(kb);
    refreshHeader();
    return true;
  }

  function addDrugToKb(name) {
    const normalized = engine.normalizeName(name);
    let existing = kb.drugs.find((drug) => engine.normalizeName(drug.name) === normalized);
    if (existing) return existing;
    existing = {
      id: `rxnorm-pending:${normalized.replace(/[^a-z0-9]+/g, "_")}`,
      rxcui: null,
      name: normalized,
      aliases: [],
      identityStatus: "pending_rxnorm_review"
    };
    kb.drugs.push(existing);
    kb.drugs.sort((a, b) => a.name.localeCompare(b.name));
    return existing;
  }

  function mergeDrugIntoKb(importedDrug) {
    const normalized = engine.normalizeName(importedDrug?.name);
    if (!normalized) return null;
    let existing = kb.drugs.find((drug) => engine.normalizeName(drug.name) === normalized);
    if (!existing) {
      existing = {
        ...importedDrug,
        aliases: Array.isArray(importedDrug.aliases) ? [...importedDrug.aliases] : [],
        doseSuggestions: Array.isArray(importedDrug.doseSuggestions) ? [...importedDrug.doseSuggestions] : []
      };
      kb.drugs.push(existing);
      return existing;
    }

    const aliases = new Set(existing.aliases || []);
    for (const alias of importedDrug.aliases || []) aliases.add(alias);
    existing.aliases = [...aliases].filter(Boolean);

    const doseSuggestions = new Set(existing.doseSuggestions || []);
    for (const dose of importedDrug.doseSuggestions || []) doseSuggestions.add(dose);
    existing.doseSuggestions = [...doseSuggestions].filter(Boolean).slice(0, 30);

    existing.isSourceReportDrug = Boolean(existing.isSourceReportDrug || importedDrug.isSourceReportDrug);
    if (!existing.identityStatus) existing.identityStatus = importedDrug.identityStatus || "pending_rxnorm_review";
    return existing;
  }

  function interactionMergeKey(interaction) {
    const left = engine.normalizeName(interaction.drugAName || interaction.drugAId);
    const right = engine.normalizeName(interaction.drugBName || interaction.drugBId);
    const pair = [left, right].sort().join("|");
    return `${pair}|${interaction.severity}|${engine.normalizeName(interaction.evidenceExcerpt)}`;
  }

  function mergeParsedReport(parsed, fileName) {
    const parsedIdToKbDrug = new Map();
    for (const importedDrug of parsed.drugs || []) {
      const merged = mergeDrugIntoKb(importedDrug);
      if (merged) parsedIdToKbDrug.set(importedDrug.id, merged);
    }

    const existingKeys = new Set(kb.interactions.map(interactionMergeKey));
    const importedInteractions = [];
    for (const interaction of parsed.interactions || []) {
      const drugA = parsedIdToKbDrug.get(interaction.drugAId);
      const drugB = parsedIdToKbDrug.get(interaction.drugBId);
      if (!drugA || !drugB || drugA.id === drugB.id) continue;

      const mergedInteraction = {
        ...interaction,
        id: `ddi-upload-${engine.hashString(`${drugA.id}|${drugB.id}|${interaction.severity}|${interaction.evidenceExcerpt}`)}`,
        drugAId: drugA.id,
        drugAName: drugA.name,
        drugBId: drugB.id,
        drugBName: drugB.name,
        evidenceSource: interaction.evidenceSource || "Uploaded TXT report",
        sourceReportPath: `uploaded:${fileName}`,
        sourceReportVersion: `uploaded:${fileName}`,
        knowledgeBaseVersion: kb.version,
        reviewStatus: interaction.reviewStatus || "uploaded_pending_review"
      };

      const key = interactionMergeKey(mergedInteraction);
      if (existingKeys.has(key)) continue;
      existingKeys.add(key);
      importedInteractions.push(mergedInteraction);
    }

    kb.interactions.unshift(...importedInteractions);
    kb.interactions.sort((a, b) => a.drugAName.localeCompare(b.drugAName) || a.drugBName.localeCompare(b.drugBName));
    kb.drugs.sort((a, b) => a.name.localeCompare(b.name));

    if (!Array.isArray(kb.reports)) kb.reports = [];
    const reportDrug = parsedIdToKbDrug.get(parsed.report?.drugId);
    kb.reports.push({
      sourceLabel: fileName,
      path: `uploaded:${fileName}`,
      drugId: reportDrug?.id || null,
      drugName: reportDrug?.name || parsed.report?.drugName || fileName,
      parsedInteractionCount: importedInteractions.length,
      importedAt: new Date().toISOString()
    });

    kb.status = "local_upload_pending_review";
    selectedReviewId = importedInteractions[0]?.id || selectedReviewId;
    return importedInteractions.length;
  }

  async function uploadReports(event) {
    event.preventDefault();
    const snapshot = structuredClone(kb);
    const files = [...(els.reportFileInput.files || [])];
    if (!files.length) {
      els.uploadStatus.textContent = "Choose a TXT file first.";
      return;
    }

    let importedCount = 0;
    const failures = [];
    for (const file of files) {
      try {
        const raw = await file.text();
        const parsed = engine.parseReportText(raw, file.name, { version: kb.version });
        importedCount += mergeParsedReport(parsed, file.name);
      } catch (error) {
        failures.push(`${file.name}: ${error.message}`);
      }
    }

    if (!persistKb()) { kb = snapshot; return; }
    renderSuggestions(els.drugInput.value);
    renderDoseSuggestions();
    renderReviewList();
    checkNow();
    els.reportFileInput.value = "";
    els.uploadStatus.textContent = failures.length
      ? `Imported ${importedCount} interaction records. Failed: ${failures.join("; ")}`
      : `Imported ${importedCount} interaction records from ${files.length} file(s).`;
  }

  function addInteraction(event) {
    event.preventDefault();
    const snapshot = structuredClone(kb);
    const drugA = addDrugToKb(els.newDrugA.value);
    const drugB = addDrugToKb(els.newDrugB.value);
    if (!drugA.name || !drugB.name || drugA.id === drugB.id) return;
    const now = Date.now().toString(16);
    kb.interactions.unshift({
      id: `ddi-local-${now}`,
      drugAId: drugA.id,
      drugAName: drugA.name,
      drugBId: drugB.id,
      drugBName: drugB.name,
      severity: els.newSeverity.value,
      mechanism: "Manually added interaction requiring review",
      clinicalEffect: els.newEffect.value.trim(),
      recommendation: els.newRecommendation.value.trim(),
      monitoring: "",
      evidenceSource: "Manual admin entry",
      evidenceExcerpt: els.newEffect.value.trim(),
      sourceReportPath: "manual-entry",
      reviewedBy: null,
      reviewedAt: null,
      reviewStatus: "manual_pending_review",
      sourceReportVersion: "manual-entry",
      knowledgeBaseVersion: kb.version
    });
    selectedReviewId = kb.interactions[0].id;
    event.target.reset();
    if (!persistKb()) { kb = snapshot; return; }
    renderReviewList();
  }

  function renderAudit() {
    const audit = readJson(STORAGE_KEYS.audit, []);
    if (!audit.length) {
      els.auditList.innerHTML = "<div class=\"notice\">No alert actions recorded yet.</div>";
      return;
    }
    els.auditList.innerHTML = audit.map((entry) => `
      <article class="audit-row">
        <strong>${escapeHtml(entry.action)} Â· ${escapeHtml(entry.interactingDrugs.join(" + "))}</strong>
        <span>${escapeHtml(entry.severity)} Â· ${escapeHtml(entry.knowledgeBaseVersion)} Â· ${escapeHtml(entry.createdAt)}</span>
        ${entry.reason ? `<span>Reason: ${escapeHtml(entry.reason)}</span>` : ""}
      </article>
    `).join("");
  }

  function exportAudit() {
    const audit = readJson(STORAGE_KEYS.audit, []);
    const blob = new Blob([JSON.stringify(audit, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `ddi-audit-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }

  function currentResultsExport() {
    const audit = readJson(STORAGE_KEYS.audit, []).filter((entry) => !entry.sessionCode || entry.sessionCode === sessionCode);
    const result = latestResult || engine.checkInteractions(medications, kb, { index });
    result.sessionCode = sessionCode;
    return {
      sessionCode,
      exportedAt: new Date().toISOString(),
      knowledgeBaseVersion: kb.version,
      medications,
      result,
      audit
    };
  }

  function exportResults() {
    const blob = new Blob([JSON.stringify(currentResultsExport(), null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `ddi-results-${sessionCode}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll("\"", "&quot;")
      .replaceAll("'", "&#039;");
  }

  els.tabs.forEach((button) => button.addEventListener("click", () => setView(button.dataset.view)));
  els.drugInput.addEventListener("input", () => {
    renderSuggestions(els.drugInput.value);
    renderDoseSuggestions();
  });
  els.drugInput.addEventListener("change", renderDoseSuggestions);
  els.medicationForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const name = els.drugInput.value.trim();
    if (!name) return;
    const previous = structuredClone(medications);
    medications.push({ name, dose: els.doseInput.value.trim() });
    if (!writeJson(STORAGE_KEYS.meds, medications).ok) { medications = previous; return; }
    clearStorageFailure();
    els.drugInput.value = "";
    els.doseInput.value = "";
    renderDoseSuggestions();
    renderMedications();
    checkNow();
  });
  els.medicationList.addEventListener("click", (event) => {
    const idx = event.target.dataset.removeMed;
    if (idx === undefined) return;
    const previous = structuredClone(medications);
    medications.splice(Number(idx), 1);
    if (!writeJson(STORAGE_KEYS.meds, medications).ok) { medications = previous; return; }
    clearStorageFailure();
    renderMedications();
    checkNow();
  });
  els.checkButton.addEventListener("click", checkNow);
  els.alertsList.addEventListener("click", (event) => {
    const action = event.target.dataset.alertAction;
    const id = event.target.dataset.alertId;
    if (action && id) recordAlertAction(id, action);
  });
  els.overrideForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const reason = els.overrideReason.value.trim();
    if (!reason) {
      els.overrideError.textContent = "Enter a clinical rationale before recording the override.";
      els.overrideReason.focus();
      return;
    }
    const alert = latestResult?.alerts.find((item) => item.id === pendingOverrideAlertId);
    if (!alert) {
      cancelOverride();
      return;
    }
    persistAlertAction(alert, "overridden", reason);
    pendingOverrideAlertId = null;
    els.overrideDialog.close();
  });
  els.cancelOverrideButton.addEventListener("click", cancelOverride);
  els.overrideDialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    cancelOverride();
  });
  els.reviewSearch.addEventListener("input", renderReviewList);
  els.reviewList.addEventListener("click", (event) => {
    const row = event.target.closest("[data-review-id]");
    if (!row) return;
    selectedReviewId = row.dataset.reviewId;
    renderReviewList();
  });
  els.approveButton.addEventListener("click", () => saveReview("approved"));
  els.rejectButton.addEventListener("click", () => saveReview("rejected"));
  els.saveDraftButton.addEventListener("click", () => saveReview("edited_pending_review"));
  els.activateRevisionButton.addEventListener("click", activateRevision);
  els.uploadReportForm.addEventListener("submit", uploadReports);
  els.addInteractionForm.addEventListener("submit", addInteraction);
  els.exportAuditButton.addEventListener("click", exportAudit);
  els.exportResultsButton.addEventListener("click", exportResults);

  refreshHeader();
  renderSuggestions("");
  renderDoseSuggestions();
  renderMedications();
  renderReviewList();
  renderAudit();
  checkNow();
})();






