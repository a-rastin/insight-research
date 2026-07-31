export const INTERFACE_VERSION = "2.0.0";
export const SCHEMA_VERSION = "2.0.0";
export const SCALE_VERSION = "PANSS-30-1.0.0";
export const RULE_VERSION = "PANSS-SUM-2.0.0";

export const SUBSCALES = Object.freeze({
  positive: Object.freeze(["P1", "P2", "P3", "P4", "P5", "P6", "P7"]),
  negative: Object.freeze(["N1", "N2", "N3", "N4", "N5", "N6", "N7"]),
  general: Object.freeze(Array.from({ length: 16 }, (_, index) => `G${index + 1}`))
});

export const ITEM_CODES = Object.freeze(Object.values(SUBSCALES).flat());
const ITEM_CODE_SET = new Set(ITEM_CODES);
const SCORE_KEYS = Object.freeze(["positive", "negative", "general", "total"]);

export function evaluatePanss(state, itemScores, projectedScores) {
  if (!(["incomplete", "passed", "completed"].includes(state))) {
    return invalid("PANSS_INVALID_STATE", "Evaluation state must be incomplete, passed, or completed.");
  }
  if (!itemScores || typeof itemScores !== "object" || Array.isArray(itemScores)) {
    return invalid("PANSS_INVALID_ITEMS", "itemScores must be an object.");
  }

  const entries = Object.entries(itemScores);
  const unknownItemCodes = entries.map(([code]) => code).filter(code => !ITEM_CODE_SET.has(code));
  if (unknownItemCodes.length > 0) {
    return invalid("PANSS_UNKNOWN_ITEMS", "itemScores contains unknown PANSS item codes.", { unknownItemCodes });
  }
  if (entries.some(([, score]) => !Number.isInteger(score) || score < 1 || score > 7)) {
    return invalid("PANSS_INVALID_ITEM_SCORE", "Each PANSS item score must be an integer from 1 to 7.");
  }

  const missingItemCodes = ITEM_CODES.filter(code => !(code in itemScores));
  if (state === "completed" && missingItemCodes.length > 0) {
    return invalid("PANSS_INCOMPLETE_ITEMS", "A completed evaluation requires the exact 30-item PANSS set.", { missingItemCodes });
  }
  if (state === "incomplete" && missingItemCodes.length === 0) {
    return invalid("PANSS_COMPLETE_ITEMS", "An evaluation with all 30 PANSS items must be completed.");
  }
  if (state === "passed" && entries.length > 0) {
    return invalid("PANSS_PASSED_WITH_ITEMS", "A passed evaluation cannot contain PANSS item scores.");
  }
  if (state !== "completed" && projectedScores !== undefined) {
    return invalid("PANSS_UNEXPECTED_PROJECTED_SCORES", "Only completed evaluations can include projected scores.");
  }

  const scores = state === "completed" ? deriveScores(itemScores) : null;
  if (projectedScores !== undefined) {
    if (!projectedScores || typeof projectedScores !== "object" || Array.isArray(projectedScores)
        || Object.keys(projectedScores).length !== SCORE_KEYS.length
        || SCORE_KEYS.some(key => !Number.isInteger(projectedScores[key]))) {
      return invalid("PANSS_INVALID_PROJECTED_SCORES", "Projected scores must contain exactly four integer PANSS totals.");
    }
    if (SCORE_KEYS.some(key => projectedScores[key] !== scores[key])) {
      return invalid("PANSS_PROJECTED_SCORES_MISMATCH", "Projected scores do not match the server-authoritative PANSS scores.");
    }
  }

  return {
    valid: true,
    state,
    missingItemCodes: state === "incomplete" ? missingItemCodes : [],
    scores,
    scaleVersion: SCALE_VERSION,
    ruleVersion: RULE_VERSION
  };
}

function invalid(code, detail, fields = {}) {
  return { valid: false, code, detail, ...fields };
}

export function validateAssessmentInput(body, includeIdentity) {
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return "Request body must be an object";
  }

  const allowed = new Set(includeIdentity
    ? ["patientId", "encounterId", "status", "itemScores", "scores"]
    : ["status", "itemScores", "scores"]);
  if (Object.keys(body).some(key => !allowed.has(key))) {
    return "Request body contains unsupported fields";
  }
  if (includeIdentity && (!isUuid(body.patientId) || !isUuid(body.encounterId))) {
    return "patientId and encounterId must be UUIDs";
  }
  if (!["in-progress", "completed", "skipped"].includes(body.status)) {
    return "status must be in-progress, completed, or skipped";
  }
  if (!body.itemScores || typeof body.itemScores !== "object" || Array.isArray(body.itemScores)) {
    return "itemScores must be an object";
  }

  const state = { "in-progress": "incomplete", completed: "completed", skipped: "passed" }[body.status];
  const evaluation = evaluatePanss(state, body.itemScores, body.scores);
  if (evaluation.valid) return null;
  const itemDetails = evaluation.missingItemCodes
    ? ` Missing item codes: ${evaluation.missingItemCodes.join(", ")}.`
    : evaluation.unknownItemCodes
      ? ` Unknown item codes: ${evaluation.unknownItemCodes.join(", ")}.`
      : "";
  return `${evaluation.detail}${itemDetails}`;
}

export function deriveScores(itemScores) {
  const scores = Object.fromEntries(Object.entries(SUBSCALES).map(([name, codes]) => [
    name,
    codes.reduce((sum, code) => sum + itemScores[code], 0)
  ]));
  return { ...scores, total: scores.positive + scores.negative + scores.general };
}

export function isUuid(value) {
  return typeof value === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
}
