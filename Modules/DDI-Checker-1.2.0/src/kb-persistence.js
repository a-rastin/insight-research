(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.DDIKbPersistence = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const STORAGE_VERSION = 2;
  const REVIEW_FIELDS = ["severity", "mechanism", "clinicalEffect", "recommendation", "monitoring", "reviewStatus", "reviewedBy", "reviewedAt"];
  const clone = (value) => value == null ? value : JSON.parse(JSON.stringify(value));
  const same = (left, right) => JSON.stringify(left) === JSON.stringify(right);
  const byId = (records) => new Map((records || []).filter((record) => record?.id).map((record) => [record.id, record]));
  const reportKey = (report) => report?.id || report?.sourceReportPath || report?.fileName || null;

  function reviewChanges(baseRecord, editedRecord) {
    const changes = {};
    for (const field of REVIEW_FIELDS) {
      if (!same(baseRecord?.[field], editedRecord?.[field])) changes[field] = clone(editedRecord?.[field]);
    }
    return changes;
  }

  function createRevision(baseKb, workingKb) {
    const baseDrugs = byId(baseKb?.drugs);
    const baseInteractions = byId(baseKb?.interactions);
    const interactionOverrides = [];
    for (const record of workingKb?.interactions || []) {
      const baseRecord = baseInteractions.get(record.id);
      if (!baseRecord) continue;
      const changes = reviewChanges(baseRecord, record);
      if (Object.keys(changes).length) interactionOverrides.push({ id: record.id, baseRecord: clone(baseRecord), changes });
    }
    return {
      storageVersion: STORAGE_VERSION,
      baseVersion: baseKb?.version || null,
      savedAt: new Date().toISOString(),
      localRevision: {
        version: workingKb?.version, status: workingKb?.status, activatedAt: workingKb?.activatedAt,
        clinicalUse: clone(workingKb?.clinicalUse)
      },
      localDrugs: clone((workingKb?.drugs || []).filter((record) => !baseDrugs.has(record.id))),
      localInteractions: clone((workingKb?.interactions || []).filter((record) => !baseInteractions.has(record.id))),
      localReports: clone((workingKb?.reports || []).filter((report) =>
        !(baseKb?.reports || []).some((baseReport) => baseReport.id && baseReport.id === report.id)
      )),
      interactionOverrides
    };
  }

  function revisionFromLegacy(baseKb, legacyKb) {
    const revision = createRevision(baseKb, legacyKb || baseKb);
    const baseInteractions = byId(baseKb?.interactions);
    const localInteractions = (legacyKb?.interactions || []).filter((record) => /^(ddi-local-|ddi-upload-)/.test(record?.id || ""));
    const localDrugIds = new Set(localInteractions.flatMap((record) => [record.drugAId, record.drugBId]));
    revision.localInteractions = clone(localInteractions);
    revision.localDrugs = clone((legacyKb?.drugs || []).filter((drug) => localDrugIds.has(drug.id)));
    revision.interactionOverrides = [];
    for (const record of legacyKb?.interactions || []) {
      const baseRecord = baseInteractions.get(record.id);
      if (!baseRecord) continue;
      const changes = {};
      for (const field of ["reviewStatus", "reviewedBy", "reviewedAt"]) {
        if (record[field] !== undefined) changes[field] = clone(record[field]);
      }
      if (Object.keys(changes).length) revision.interactionOverrides.push({ id: record.id, baseRecord: clone(baseRecord), changes });
    }
    return revision;
  }

  function rebase(baseKb, saved) {
    const revision = saved?.storageVersion === STORAGE_VERSION ? clone(saved) : revisionFromLegacy(baseKb, saved);
    const kb = clone(baseKb);
    const currentInteractions = byId(kb.interactions);
    const conflicts = [];
    kb.drugs.push(...clone(revision.localDrugs || []));
    kb.interactions.push(...clone(revision.localInteractions || []));
    kb.reports = [...(kb.reports || []), ...clone(revision.localReports || [])];
    for (const override of revision.interactionOverrides || []) {
      const current = currentInteractions.get(override.id);
      if (!current) {
        conflicts.push({ id: override.id, type: "bundled_record_removed", localChanges: clone(override.changes) });
        continue;
      }
      if (!same(current, override.baseRecord)) conflicts.push({ id: override.id, type: "bundled_record_changed", localChanges: clone(override.changes) });
      Object.assign(current, clone(override.changes));
    }
    const local = revision.localRevision || {};
    if (local.version) kb.version = local.version;
    if (local.status) kb.status = local.status;
    if (local.activatedAt) kb.activatedAt = local.activatedAt;
    if (local.clinicalUse) kb.clinicalUse = clone(local.clinicalUse);
    kb.baseVersion = baseKb.version || null;
    kb.rebaseConflicts = conflicts;
    const migratedRevision = createRevision(baseKb, kb);
    migratedRevision.conflicts = clone(conflicts);
    return { kb, revision: migratedRevision, conflicts, migrated: saved?.storageVersion !== STORAGE_VERSION || saved?.baseVersion !== baseKb.version };
  }

  return { STORAGE_VERSION, REVIEW_FIELDS, createRevision, rebase };
});
