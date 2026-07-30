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

export function validateAssessmentInput(body, includeIdentity) {
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return "Request body must be an object";
  }

  const allowed = new Set(includeIdentity
    ? ["patientId", "encounterId", "status", "itemScores"]
    : ["status", "itemScores"]);
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

  const entries = Object.entries(body.itemScores);
  if (entries.some(([code, score]) => !ITEM_CODE_SET.has(code) || !Number.isInteger(score) || score < 1 || score > 7)) {
    return "Each item must be a PANSS code scored with an integer from 1 to 7";
  }
  if (body.status === "completed" && (entries.length !== 30 || ITEM_CODES.some(code => !(code in body.itemScores)))) {
    return "completed assessments require all 30 PANSS items";
  }
  if (body.status === "in-progress" && entries.length === 30) {
    return "An assessment with all 30 PANSS items must be completed";
  }
  if (body.status === "skipped" && entries.length !== 0) {
    return "skipped assessments cannot contain item scores";
  }
  return null;
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
