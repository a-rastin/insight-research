(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.DDIReportParser = factory();
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const PARSER_VERSION = "2.0.0";
  const SECTION_MAP = [
    [/^contraindicated(?:\s*\(\d+\))?/i, "contraindicated"],
    [/^serious(?:\s*\(\d+\))?/i, "major"],
    [/^(significant\s*-\s*)?monitor closely(?:\s*\(\d+\))?/i, "moderate"],
    [/^minor(?:\s*\(\d+\))?/i, "minor"]
  ];
  const STOP_SECTION = /^(adverse effects|warnings|pregnancy|pharmacology|administration|contraindications|cautions|overdose)\b/i;

  function cleanLine(line) {
    return String(line || "")
      .replace(/\[[^\]]*cite:[^\]]*\]/gi, "")
      .replace(/\s+/g, " ")
      .replace(/^[-\u2022*]\s*/, "")
      .trim();
  }

  function isNoiseLine(line) {
    return !line || /^https?:\/\//i.test(line) || /^\d+\/\d+\/\d+,\s+\d+:\d+/i.test(line) ||
      /^this site is intended/i.test(line) || /^interaction checker$/i.test(line) ||
      /^enter a drug name/i.test(line) || /^no interactions found$/i.test(line) ||
      /^interactions found$/i.test(line) || /^all interactions sort by/i.test(line);
  }

  function normalizeDrugName(value) {
    return String(value || "").toLowerCase().replace(/\([^)]*\)/g, " ")
      .replace(/\b(rx|generic|dsc|all forms|various forms)\b/g, " ")
      .replace(/[^a-z0-9+/-]+/g, " ").replace(/\s+/g, " ").trim();
  }

  function sourceStem(sourceLabel) {
    const normalized = String(sourceLabel || "report").replace(/\\/g, "/");
    return normalized.slice(normalized.lastIndexOf("/") + 1).replace(/\.[^.]+$/, "");
  }

  function parseHeader(raw, sourceLabel) {
    const fallback = sourceStem(sourceLabel);
    const lines = String(raw || "").split(/\r?\n/).map(cleanLine).filter((line) => line && !isNoiseLine(line));
    const drugLine = lines.find((line) => /\(Rx\)/i.test(line)) || fallback;
    const name = normalizeDrugName(cleanLine(drugLine).replace(/\(Rx\).*/i, "")) || normalizeDrugName(fallback);
    const brandLine = lines.find((line) => /^brand and other names:/i.test(line));
    const aliases = brandLine ? brandLine.replace(/^brand and other names:/i, "").split(",").map(cleanLine).filter(Boolean) : [];
    return { name, aliases };
  }

  function extractDoseSuggestions(raw) {
    const lines = String(raw || "").split(/\r?\n/).map(cleanLine);
    const suggestions = [];
    let formContext = "";
    const add = (value) => {
      const clean = cleanLine(value).replace(/\s*https?:\/\/\S+.*/i, "").trim();
      if (clean && clean.length <= 150 && !/^(adult|pediatric|geriatric|dosing & uses|dosage forms & strengths)$/i.test(clean) && !suggestions.includes(clean)) suggestions.push(clean);
    };
    for (const line of lines) {
      if (/^interactions\b/i.test(line)) break;
      if (isNoiseLine(line)) continue;
      const isForm = /^(tablet|capsule|solution|oral solution|injection|suspension|liquid|patch|spray|inhaler|extended release|delayed-release|syrup|powder|film|cream|gel|suppository|vial)\b/i.test(line);
      const hasDose = /\b\d+(?:\.\d+)?\s*(?:mg|mcg|g|mEq|units?|iu|%)\b/i.test(line);
      const hasSchedule = /\b(?:po|iv|im|subq|qday|qdaily|bid|tid|qid|qhs|q\d+hr|daily|weekly|monthly|bedtime|initial|maintenance|maximum|not to exceed|dose|dosage|increase|titrate)\b/i.test(line);
      if (isForm && !hasDose) formContext = line;
      else if (hasDose && formContext && line.length <= 60 && !hasSchedule) add(`${formContext}: ${line}`);
      else if (hasDose && hasSchedule) add(line);
    }
    return suggestions.slice(0, 30);
  }

  function collectSections(raw) {
    const sections = [];
    let current = null;
    for (const line of String(raw || "").split(/\r?\n/).map(cleanLine)) {
      if (!line) { if (current) current.lines.push(""); continue; }
      if (isNoiseLine(line)) continue;
      const match = SECTION_MAP.find(([pattern]) => pattern.test(line));
      if (match) { if (current) sections.push(current); current = { severity: match[1], lines: [] }; continue; }
      if (current && STOP_SECTION.test(line)) { sections.push(current); current = null; continue; }
      if (current) current.lines.push(line);
    }
    if (current) sections.push(current);
    return sections;
  }

  function looksLikeDrugHeading(value) {
    const block = cleanLine(value);
    return Boolean(block && block.length <= 90 && !/[.:;]$/.test(block) && !/^\d/.test(block) &&
      !/^(contraindicated|serious|minor|monitor closely|significant)/i.test(block) &&
      !/\b(increases|decreases|avoid|monitor|contraindicated|toxicity|levels|effect|recommended|patients|dosing|assay|study|initially|postoperatively|discontinuation|years?|weeks?|daily|tablet|capsule|dose)\b/i.test(block) && /[a-z]/i.test(block));
  }

  function splitBlocks(lines) {
    const blocks = [];
    let block = [];
    const flush = () => {
      if (!block.length) return;
      if (block.length > 1 && looksLikeDrugHeading(block[0])) blocks.push(block[0], block.slice(1).join(" "));
      else blocks.push(block.join(" "));
      block = [];
    };
    for (const line of lines) line ? block.push(line) : flush();
    flush();
    return blocks;
  }

  function extractListDrugs(value) {
    const beforePeriod = String(value || "").split(". ")[0] || value;
    return beforePeriod.split(/,\s*|\s+and\s+/i).map((part) => normalizeDrugName(part)).filter(looksLikeDrugHeading);
  }

  function parseBullet(block) {
    const colon = block.indexOf(":");
    if (colon < 1) return null;
    const label = block.slice(0, colon).trim();
    const body = block.slice(colon + 1).trim();
    if (!label || !body) return null;
    if (/\(|\//.test(label) || label.split(/\s+/).length > 3) return { type: "category-list", category: label, drugs: extractListDrugs(body), body };
    return { type: "single", drugName: normalizeDrugName(label), body };
  }

  function inferMechanism(text) {
    const lower = String(text || "").toLowerCase();
    if (lower.includes("qtc") || lower.includes("torsade")) return "QTc prolongation / torsades risk";
    if (lower.includes("serotonin")) return "Serotonergic toxicity risk";
    if (lower.includes("cyp3a4")) return "CYP3A4-mediated pharmacokinetic interaction";
    if (lower.includes("cyp2d6")) return "CYP2D6-mediated pharmacokinetic interaction";
    if (lower.includes("cyp2c19")) return "CYP2C19-mediated pharmacokinetic interaction";
    if (lower.includes("sedation") || lower.includes("cns depression")) return "Additive sedation / CNS depression";
    if (lower.includes("renal clearance")) return "Altered renal clearance";
    if (lower.includes("bleeding") || lower.includes("hemorrhage")) return "Bleeding risk";
    return "Drug interaction described in source report";
  }

  function inferRecommendation(severity, text) {
    const lower = String(text || "").toLowerCase();
    if (severity === "contraindicated" || lower.includes("contraindicated")) return "Do not coadminister unless a specialist documents an exceptional rationale.";
    if (lower.includes("avoid or use alternate")) return "Avoid combination or use an alternate drug when clinically feasible.";
    if (lower.includes("modify therapy")) return "Modify therapy and document monitoring plan.";
    if (lower.includes("monitor")) return "Monitor closely and adjust treatment based on clinical response.";
    if (severity === "major") return "Avoid or use an alternate drug when clinically feasible.";
    if (severity === "moderate") return "Monitor closely and consider dose or therapy adjustment.";
    if (severity === "minor") return "Document low-level interaction awareness.";
    return "Review interaction and document clinical plan.";
  }

  function inferMonitoring(text) {
    const lower = String(text || "").toLowerCase();
    const values = [];
    if (lower.includes("qtc") || lower.includes("ecg")) values.push("ECG/QTc monitoring");
    if (lower.includes("serotonin")) values.push("Serotonin toxicity and mental status");
    if (lower.includes("sedation") || lower.includes("cns")) values.push("Sedation, respiratory status, falls risk");
    if (lower.includes("glucose") || lower.includes("hyperglycemia")) values.push("Glucose control");
    if (lower.includes("lithium")) values.push("Lithium level and renal function");
    return values.join("; ");
  }

  function makeInteraction(drugAName, drugBName, severity, excerpt, sequence) {
    const sentence = String(excerpt || "").match(/^(.{20,240}?[.!?])(?:\s|$)/);
    return { drugAName, drugBName, severity, mechanism: inferMechanism(excerpt), clinicalEffect: sentence ? sentence[1] : String(excerpt || "").slice(0, 220), recommendation: inferRecommendation(severity, excerpt), monitoring: inferMonitoring(excerpt), evidenceExcerpt: excerpt, sequence };
  }

  function parseReport(raw, sourceLabel, options) {
    const normalizedOptions = { sourceLabel: String(sourceLabel || options?.sourceLabel || "report"), parserVersion: PARSER_VERSION };
    const primaryDrug = parseHeader(raw, normalizedOptions.sourceLabel);
    primaryDrug.doseSuggestions = extractDoseSuggestions(raw);
    const interactions = [];
    let sequence = 0;
    for (const section of collectSections(raw)) {
      let currentName = null;
      let currentParts = [];
      const flush = () => {
        if (currentName && currentParts.length && currentName !== primaryDrug.name) interactions.push(makeInteraction(primaryDrug.name, currentName, section.severity, currentParts.join(" ").replace(/\s+/g, " ").trim(), ++sequence));
        currentName = null; currentParts = [];
      };
      for (const block of splitBlocks(section.lines)) {
        const bullet = parseBullet(block);
        if (bullet?.type === "single") { flush(); if (bullet.drugName !== primaryDrug.name) interactions.push(makeInteraction(primaryDrug.name, bullet.drugName, section.severity, bullet.body, ++sequence)); continue; }
        if (bullet?.type === "category-list") { flush(); for (const name of bullet.drugs) if (name !== primaryDrug.name) interactions.push(makeInteraction(primaryDrug.name, name, section.severity, `${bullet.category}: ${bullet.body}`, ++sequence)); continue; }
        if (looksLikeDrugHeading(block)) { flush(); currentName = normalizeDrugName(block); }
        else if (currentName) currentParts.push(block);
      }
      flush();
    }
    const drugNames = [...new Set([primaryDrug.name, ...interactions.map((item) => item.drugBName)].filter(Boolean))];
    return { parserVersion: PARSER_VERSION, sourceLabel: normalizedOptions.sourceLabel, primaryDrug, drugNames, interactions, report: { sourceLabel: normalizedOptions.sourceLabel, drugName: primaryDrug.name || sourceStem(normalizedOptions.sourceLabel), parsedInteractionCount: interactions.length } };
  }

  return { PARSER_VERSION, cleanLine, normalizeDrugName, extractDoseSuggestions, looksLikeDrugHeading, parseReport };
});
