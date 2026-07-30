(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./report-parser.js"));
  } else {
    root.DDIEngine = factory(root.DDIReportParser);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (reportParser) {
  if (!reportParser?.parseReport) throw new Error("DDIReportParser must be loaded before DDIEngine");
  "use strict";

  const SEVERITY_ORDER = {
    contraindicated: 0,
    major: 1,
    moderate: 2,
    minor: 3,
    unknown: 4
  };

  const DISPLAY_SEVERITY = {
    contraindicated: "Contraindicated",
    major: "Major",
    moderate: "Moderate",
    minor: "Minor",
    unknown: "Unknown"
  };

  function normalizeName(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/\([^)]*\)/g, " ")
      .replace(/\b(rx|generic|dsc|all forms|various forms)\b/g, " ")
      .replace(/[^a-z0-9+/-]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function normalizeId(value) {
    return String(value || "").toLowerCase().trim();
  }

  function pairKey(a, b) {
    const left = normalizeId(a);
    const right = normalizeId(b);
    return [left, right].sort().join("|");
  }

  function severityRank(severity) {
    return SEVERITY_ORDER[severity] ?? SEVERITY_ORDER.unknown;
  }

  function slugify(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/\([^)]*\)/g, "")
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "");
  }

  function hashString(value) {
    let hash = 2166136261;
    const input = String(value || "");
    for (let i = 0; i < input.length; i += 1) {
      hash ^= input.charCodeAt(i);
      hash = Math.imul(hash, 16777619);
    }
    return (hash >>> 0).toString(16).padStart(8, "0");
  }

  function cleanReportLine(line) {
    return String(line || "")
      .replace(/\[[^\]]*cite:[^\]]*\]/gi, "")
      .replace(/\s+/g, " ")
      .replace(/^[-\u2022*]\s*/, "")
      .trim();
  }

  function isReportNoiseLine(line) {
    return !line ||
      /^https?:\/\//i.test(line) ||
      /^\d+\/\d+\/\d+,\s+\d+:\d+/i.test(line) ||
      /^this site is intended/i.test(line) ||
      /^interaction checker$/i.test(line) ||
      /^enter a drug name/i.test(line) ||
      /^no interactions found$/i.test(line) ||
      /^interactions found$/i.test(line) ||
      /^all interactions sort by/i.test(line);
  }

  function reportDrugIdFor(name) {
    return `rxnorm-pending:${slugify(normalizeName(name)) || "unknown"}`;
  }

  function getOrCreateParsedDrug(drugs, name, aliases) {
    const normalized = normalizeName(name);
    if (!normalized) return null;
    const id = reportDrugIdFor(normalized);
    if (!drugs.has(id)) {
      drugs.set(id, {
        id,
        rxcui: null,
        name: normalized,
        aliases: [],
        doseSuggestions: [],
        isSourceReportDrug: false,
        identityStatus: "pending_rxnorm_review"
      });
    }
    const drug = drugs.get(id);
    for (const alias of aliases || []) {
      const cleanAlias = cleanReportLine(alias);
      if (cleanAlias && !drug.aliases.includes(cleanAlias)) drug.aliases.push(cleanAlias);
    }
    return drug;
  }

  function addDoseSuggestions(drug, suggestions) {
    if (!drug) return;
    if (!Array.isArray(drug.doseSuggestions)) drug.doseSuggestions = [];
    for (const suggestion of suggestions) {
      const cleanSuggestion = cleanReportLine(suggestion);
      if (cleanSuggestion && !drug.doseSuggestions.includes(cleanSuggestion)) {
        drug.doseSuggestions.push(cleanSuggestion);
      }
    }
    drug.doseSuggestions = drug.doseSuggestions.slice(0, 30);
  }

  function extractDoseSuggestions(raw) {
    return reportParser.extractDoseSuggestions(raw);
  }

  function createParsedInteraction({ drugA, drugB, parsed, sourceName, version }) {
    const idBase = `${drugA.id}|${drugB.id}|${parsed.severity}|${parsed.evidenceExcerpt}`;
    return {
      id: `ddi-upload-${hashString(idBase)}`,
      drugAId: drugA.id, drugAName: drugA.name, drugBId: drugB.id, drugBName: drugB.name,
      severity: parsed.severity, mechanism: parsed.mechanism, clinicalEffect: parsed.clinicalEffect,
      recommendation: parsed.recommendation, monitoring: parsed.monitoring,
      evidenceSource: "Uploaded TXT report; verify against licensed source and RxNorm before production use.",
      evidenceExcerpt: parsed.evidenceExcerpt, sourceReportPath: `uploaded:${sourceName || "report"}`,
      reviewedBy: null, reviewedAt: null, reviewStatus: "uploaded_pending_review",
      parserConfidence: drugB.identityStatus === "pending_rxnorm_review" ? "medium" : "high",
      sourceReportVersion: `uploaded:${sourceName || "report"}`,
      knowledgeBaseVersion: version || "local-upload", sequence: parsed.sequence
    };
  }
  function parseReportText(raw, sourceName, options) {
    const version = options?.version || "local-upload";
    const neutral = reportParser.parseReport(raw, sourceName, options);
    const drugs = new Map();
    const header = neutral.primaryDrug;
    const drugA = getOrCreateParsedDrug(drugs, header.name, header.aliases);
    if (!drugA) {
      return { drug: null, drugs: [], interactions: [], report: { ...neutral.report, drugId: null } };
    }
    drugA.isSourceReportDrug = true;
    addDoseSuggestions(drugA, header.doseSuggestions);
    const interactions = neutral.interactions.flatMap((item) => {
      const drugB = getOrCreateParsedDrug(drugs, item.drugBName);
      return drugB && drugB.id !== drugA.id ? [createParsedInteraction({
        drugA, drugB, parsed: item,
        sourceName, version
      })] : [];
    });
    return {
      drug: drugA,
      drugs: [...drugs.values()],
      interactions,
      report: { ...neutral.report, drugId: drugA.id }
    };
  }
  function createEmptyIndex() {
    return {
      byId: new Map(),
      byName: new Map(),
      interactionsByPair: new Map(),
      suggestions: [],
      identityCollisions: []
    };
  }

  function addIdentityCandidate(index, label, drug) {
    const normalized = normalizeName(label);
    if (!normalized) return;
    if (!index.byName.has(normalized)) index.byName.set(normalized, []);
    const candidates = index.byName.get(normalized);
    if (!candidates.some((candidate) => normalizeId(candidate.id) === normalizeId(drug.id))) candidates.push(drug);
  }
  function isInteractionEligible(record, knowledgeBase, options) {
    if (!record || typeof record !== "object") return false;
    if (options?.adminPreview === true) return true;
    return record.reviewStatus === "approved";
  }

  function buildIndex(knowledgeBase, options) {
    const index = createEmptyIndex();
    const drugs = Array.isArray(knowledgeBase?.drugs) ? knowledgeBase.drugs : [];
    const interactions = Array.isArray(knowledgeBase?.interactions) ? knowledgeBase.interactions : [];

    for (const drug of drugs) {
      if (!drug?.id) continue;
      index.byId.set(normalizeId(drug.id), drug);
      addIdentityCandidate(index, drug.name, drug);
      for (const alias of drug.aliases || []) {
        addIdentityCandidate(index, alias, drug);
      }
    }

    index.identityCollisions = [...index.byName.entries()]
      .filter(([, candidates]) => candidates.length > 1)
      .map(([label, candidates]) => ({
        label,
        candidates: candidates.map((candidate) => ({ id: candidate.id, name: candidate.name }))
      }))
      .sort((a, b) => a.label.localeCompare(b.label));

    index.suggestions = drugs
      .map((drug) => ({
        id: drug.id,
        name: drug.name,
        aliases: drug.aliases || [],
        identityStatus: drug.identityStatus || "unknown"
      }))
      .sort((a, b) => a.name.localeCompare(b.name));

    for (const interaction of interactions) {
      if (!isInteractionEligible(interaction, knowledgeBase, options)) continue;
      if (!interaction?.drugAId || !interaction?.drugBId) continue;
      const key = pairKey(interaction.drugAId, interaction.drugBId);
      if (!index.interactionsByPair.has(key)) index.interactionsByPair.set(key, []);
      index.interactionsByPair.get(key).push(interaction);
    }

    for (const records of index.interactionsByPair.values()) {
      records.sort((a, b) => severityRank(a.severity) - severityRank(b.severity));
    }

    return index;
  }

  function resolveDrug(input, index) {
    const raw = typeof input === "string" ? input : input?.name;
    const normalized = normalizeName(raw);
    if (!normalized) return { status: "unknown", input: raw || "" };

    const matches = new Map();
    const addMatches = (candidates) => {
      for (const drug of candidates || []) matches.set(normalizeId(drug.id), drug);
    };

    addMatches(index.byName.get(normalized));
    if (!matches.size) {
      const compact = normalized.replace(/\s+/g, "");
      for (const [name, candidates] of index.byName.entries()) {
        if (name.replace(/\s+/g, "") === compact) addMatches(candidates);
      }
    }

    const candidates = [...matches.values()].sort((a, b) =>
      String(a.name || "").localeCompare(String(b.name || "")) ||
      String(a.id || "").localeCompare(String(b.id || ""))
    );
    if (candidates.length === 1) return { status: "resolved", drug: candidates[0] };
    if (candidates.length > 1) return { status: "ambiguous", candidates };
    return { status: "unknown", input: raw || "" };
  }

  function suggestDrugs(query, knowledgeBase, options) {
    const index = options?.index || buildIndex(knowledgeBase, options);
    const normalized = normalizeName(query);
    const limit = options?.limit || 12;
    if (!normalized) return index.suggestions.slice(0, limit);

    return index.suggestions
      .map((drug) => {
        const names = [drug.name].concat(drug.aliases || []).map(normalizeName);
        const exact = names.some((name) => name === normalized);
        const startsWith = names.some((name) => name.startsWith(normalized));
        const contains = names.some((name) => name.includes(normalized));
        const score = exact ? 0 : startsWith ? 1 : contains ? 2 : 99;
        return { drug, score };
      })
      .filter((row) => row.score < 99)
      .sort((a, b) => a.score - b.score || a.drug.name.localeCompare(b.drug.name))
      .slice(0, limit)
      .map((row) => row.drug);
  }

  function toMedication(input) {
    if (typeof input === "string") return { name: input, dose: "" };
    return {
      name: input?.name || "",
      dose: input?.dose || "",
      route: input?.route || "",
      frequency: input?.frequency || ""
    };
  }

  function assignMedicationInstanceIds(medications) {
    const occurrences = new Map();
    return medications.map((medication) => {
      const identity = ["name", "dose", "route", "frequency"]
        .map((field) => String(medication[field] || "").trim().toLowerCase())
        .join("\u001f");
      const fingerprint = hashString(identity);
      const occurrence = (occurrences.get(fingerprint) || 0) + 1;
      occurrences.set(fingerprint, occurrence);
      return { ...medication, instanceId: `med-${fingerprint}-${occurrence}` };
    });
  }

  /**
   * Every input row is a distinct medication instance, including exact duplicate rows.
   * Alerts are unique by interaction record plus unordered medication-instance pair.
   */
  function checkInteractions(medications, knowledgeBase, options) {
    const index = options?.index || buildIndex(knowledgeBase, options);
    const meds = assignMedicationInstanceIds(
      (Array.isArray(medications) ? medications : []).map(toMedication)
    );
    const resolved = meds.map((med) => ({ medication: med, resolution: resolveDrug(med, index) }));
    const alerts = [];
    const unresolved = resolved.filter((row) =>
      row.resolution.status === "unknown" && normalizeName(row.medication.name)
    );
    const ambiguous = resolved.filter((row) => row.resolution.status === "ambiguous");
    const seen = new Set();

    for (let i = 0; i < resolved.length; i += 1) {
      for (let j = i + 1; j < resolved.length; j += 1) {
        const left = resolved[i];
        const right = resolved[j];
        if (left.resolution.status !== "resolved" || right.resolution.status !== "resolved") continue;
        const leftDrug = left.resolution.drug;
        const rightDrug = right.resolution.drug;
        const records = index.interactionsByPair.get(pairKey(leftDrug.id, rightDrug.id)) || [];

        for (const record of records) {
          const medicationPairId = pairKey(left.medication.instanceId, right.medication.instanceId);
          const alertId = `${record.id}::${medicationPairId}`;
          if (seen.has(alertId)) continue;
          seen.add(alertId);
          alerts.push({
            id: alertId,
            interactionId: record.id,
            severity: record.severity || "unknown",
            severityLabel: DISPLAY_SEVERITY[record.severity] || DISPLAY_SEVERITY.unknown,
            interactingDrugs: [leftDrug.name, rightDrug.name],
            patientMedications: [left.medication, right.medication],
            clinicalConcern: record.clinicalEffect || record.mechanism || "Interaction record requires review.",
            recommendedAction: record.recommendation || "Review interaction and document clinical plan.",
            monitoring: record.monitoring || "",
            mechanism: record.mechanism || "",
            evidenceSource: record.evidenceSource || "",
            evidenceExcerpt: record.evidenceExcerpt || "",
            sourceReportPath: record.sourceReportPath || "",
            reviewStatus: record.reviewStatus || "unknown",
            knowledgeBaseVersion: record.knowledgeBaseVersion || knowledgeBase?.version || "unknown",
            record
          });
        }
      }
    }

    alerts.sort((a, b) => {
      const severity = severityRank(a.severity) - severityRank(b.severity);
      if (severity !== 0) return severity;
      return a.interactingDrugs.join(" ").localeCompare(b.interactingDrugs.join(" "));
    });

    return {
      knowledgeBaseVersion: knowledgeBase?.version || "unknown",
      checkedAt: new Date().toISOString(),
      alerts,
      unresolved: unresolved.map((row) => row.medication),
      ambiguous: ambiguous.map((row) => ({
        medication: row.medication,
        candidates: row.resolution.candidates
      })),
      medicationCount: meds.length
    };
  }

  function createAuditEntry(alert, action, details) {
    const reason = typeof details?.reason === "string" ? details.reason.trim() : "";
    if (action === "overridden" && !reason) {
      throw new TypeError("A nonblank rationale is required for an overridden alert.");
    }
    if (reason.length > 500) {
      throw new RangeError("Audit rationale must not exceed 500 characters.");
    }
    return {
      id: `audit-${Date.now()}-${Math.random().toString(16).slice(2)}`,
      alertId: alert.id,
      action,
      reason,
      clinician: details?.clinician || "",
      patientId: details?.patientId || "",
      sessionCode: details?.sessionCode || "",
      interactionId: alert.record?.id || alert.id,
      interactingDrugs: alert.interactingDrugs,
      severity: alert.severity,
      knowledgeBaseVersion: alert.knowledgeBaseVersion,
      sourceReportPath: alert.sourceReportPath || "",
      createdAt: new Date().toISOString()
    };
  }

  return {
    SEVERITY_ORDER,
    DISPLAY_SEVERITY,
    normalizeName,
    pairKey,
    hashString,
    isInteractionEligible,
    buildIndex,
    resolveDrug,
    suggestDrugs,
    checkInteractions,
    createAuditEntry,
    extractDoseSuggestions,
    parseReportText
  };
});
