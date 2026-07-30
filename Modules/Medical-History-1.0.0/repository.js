const fs = require("fs");
const { createHash } = require("crypto");
const { DatabaseSync } = require("node:sqlite");

const DATABASE_SCHEMA_VERSION = 2;
const IMPORT_ACTOR_ID = "00000000-0000-4000-8000-000000000000";
const CLINICAL_STATES = new Set(["yes", "no", "unknown", "not-assessed"]);
const STATUSES = new Set(["in-progress", "completed", "not-assessed"]);
const HISTORY_OPTIONS = new Set(["Diabetes mellitus", "Hypertension", "Coronary artery disease", "Heart failure", "Chronic obstructive pulmonary disease", "Asthma", "Chronic kidney disease", "Stroke or TIA", "Cancer", "Depression", "Anxiety disorder", "Other"]);
const ANTIPSYCHOTICS = new Set(["Aripiprazole", "Asenapine", "Brexpiprazole", "Cariprazine", "Chlorpromazine", "Clozapine", "Fluphenazine", "Haloperidol", "Iloperidone", "Lurasidone", "Olanzapine", "Paliperidone", "Perphenazine", "Quetiapine", "Risperidone", "Ziprasidone"]);
const CONTRAINDICATIONS = new Set(["Severe neutropenia", "Clozapine-induced myocarditis", "Unmanaged seizure disorder"]);

const MIGRATIONS = [
  {
    version: 1,
    name: "medical-history-assessments-v1",
    sql: `
      CREATE TABLE assessments (
        assessment_id TEXT PRIMARY KEY,
        patient_id TEXT NOT NULL,
        encounter_id TEXT NOT NULL,
        resource_version INTEGER NOT NULL CHECK (resource_version >= 1),
        assessment_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
      ) STRICT;
      CREATE INDEX assessments_encounter_idx ON assessments(encounter_id, updated_at DESC, assessment_id DESC);
      CREATE TABLE assessment_versions (
        assessment_id TEXT NOT NULL,
        resource_version INTEGER NOT NULL,
        actor_id TEXT NOT NULL,
        request_id TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        assessment_json TEXT NOT NULL,
        PRIMARY KEY (assessment_id, resource_version)
      ) STRICT;
      CREATE TABLE idempotency_records (
        actor_id TEXT NOT NULL,
        idempotency_key TEXT NOT NULL,
        fingerprint TEXT NOT NULL,
        response_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY (actor_id, idempotency_key)
      ) STRICT;
      CREATE TABLE activation_aliases (
        code TEXT PRIMARY KEY,
        patient_id TEXT NOT NULL,
        encounter_id TEXT NOT NULL,
        assessment_id TEXT,
        status TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
      ) STRICT;
    `
  },
  {
    version: 2,
    name: "medical-history-json-import-v2",
    sql: `
      CREATE TABLE legacy_quarantine (
        source_name TEXT NOT NULL,
        source_key TEXT NOT NULL,
        reason TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        quarantined_at TEXT NOT NULL,
        PRIMARY KEY (source_name, source_key)
      ) STRICT;
      CREATE TABLE legacy_imports (
        source_name TEXT PRIMARY KEY,
        source_hash TEXT NOT NULL,
        imported_at TEXT NOT NULL,
        imported_count INTEGER NOT NULL,
        quarantined_count INTEGER NOT NULL
      ) STRICT;
    `
  }
];

function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value !== null && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function isUuid(value) {
  return typeof value === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(value);
}

function parseSource(source) {
  if (!source.path || !fs.existsSync(source.path)) return null;
  const bytes = fs.readFileSync(source.path);
  let payload;
  try {
    payload = JSON.parse(bytes.toString("utf8"));
  } catch (error) {
    throw new Error(`Legacy ${source.name} import is corrupt`, { cause: error });
  }
  return { payload, hash: createHash("sha256").update(bytes).digest("hex") };
}

function legacyAssessment(value, now) {
  if (!value || typeof value !== "object" || !isUuid(value.submissionId) || !isUuid(value.patientId) || !isUuid(value.encounterId) ||
      !Array.isArray(value.pastMedicalHistory) || value.pastMedicalHistory.some((item) => !HISTORY_OPTIONS.has(item)) ||
      !Array.isArray(value.drugs) || value.drugs.length > 20 || value.drugs.some((drug) => typeof drug?.name !== "string" || !drug.name.trim()) ||
      !Array.isArray(value.clozapineContraindications) || value.clozapineContraindications.some((item) => !CONTRAINDICATIONS.has(item)) ||
      ["substantialSuicideRisk", "priorAntipsychoticTherapy", "clozapineContraindication", "recurrentNonAdherenceDeterioration"].some((field) => typeof value[field] !== "boolean") ||
      (value.priorAntipsychoticTherapy && (typeof value.priorAntipsychoticTherapySuccessful !== "boolean" || !ANTIPSYCHOTICS.has(value.antipsychotic))) ||
      (value.clozapineContraindication && value.clozapineContraindications.length === 0) ||
      (!value.clozapineContraindication && value.clozapineContraindications.length > 0)) return null;
  const timestamp = typeof value.submittedAt === "string" && Number.isFinite(Date.parse(value.submittedAt)) ? value.submittedAt : now;
  return {
    interfaceVersion: "2.0.0",
    schemaVersion: "2.0.0",
    assessmentId: value.submissionId,
    patientId: value.patientId,
    encounterId: value.encounterId,
    status: "completed",
    pastMedicalHistory: value.pastMedicalHistory,
    medications: value.drugs.map((drug) => ({
      originalText: String(drug?.name || "").trim(),
      doseText: drug?.dose ? String(drug.dose).trim() : null,
      routeText: drug?.route ? String(drug.route).trim() : null,
      frequencyText: drug?.frequency ? String(drug.frequency).trim() : null,
      normalizedIdentity: { state: "not-assessed", conceptId: null, display: null, terminologyVersion: null }
    })),
    substantialSuicideRisk: value.substantialSuicideRisk ? "yes" : "no",
    priorAntipsychoticTherapy: value.priorAntipsychoticTherapy ? "yes" : "no",
    priorAntipsychoticTherapySuccessful: value.priorAntipsychoticTherapy ? (value.priorAntipsychoticTherapySuccessful ? "yes" : "no") : "not-assessed",
    antipsychotic: value.priorAntipsychoticTherapy ? value.antipsychotic : null,
    clozapineContraindication: value.clozapineContraindication ? "yes" : "no",
    clozapineContraindications: value.clozapineContraindication ? value.clozapineContraindications : [],
    recurrentNonAdherenceDeterioration: value.recurrentNonAdherenceDeterioration ? "yes" : "no",
    actor: { actorId: IMPORT_ACTOR_ID, role: "psychiatrist" },
    createdAt: timestamp,
    updatedAt: timestamp,
    resourceVersion: 1,
    provenance: { sourceModule: "medical-history", optionSetVersion: "2.0.0", createdRequestId: IMPORT_ACTOR_ID, updatedRequestId: IMPORT_ACTOR_ID }
  };
}

function validCanonicalAssessment(value) {
  if (!value || typeof value !== "object" || value.interfaceVersion !== "2.0.0" || value.schemaVersion !== "2.0.0" ||
      !isUuid(value.assessmentId) || !isUuid(value.patientId) || !isUuid(value.encounterId) || !STATUSES.has(value.status) ||
      !Number.isInteger(value.resourceVersion) || value.resourceVersion < 1 || !Number.isFinite(Date.parse(value.createdAt)) ||
      !Number.isFinite(Date.parse(value.updatedAt)) || !Array.isArray(value.pastMedicalHistory) ||
      value.pastMedicalHistory.some((item) => !HISTORY_OPTIONS.has(item)) || new Set(value.pastMedicalHistory).size !== value.pastMedicalHistory.length ||
      !Array.isArray(value.medications) || value.medications.length > 20 || !Array.isArray(value.clozapineContraindications) ||
      value.clozapineContraindications.some((item) => !CONTRAINDICATIONS.has(item)) ||
      new Set(value.clozapineContraindications).size !== value.clozapineContraindications.length ||
      !isUuid(value.actor?.actorId) || value.actor?.role !== "psychiatrist" || value.provenance?.sourceModule !== "medical-history" ||
      value.provenance?.optionSetVersion !== "2.0.0" || !isUuid(value.provenance?.createdRequestId) || !isUuid(value.provenance?.updatedRequestId)) return false;
  if (value.medications.some((medication) => typeof medication?.originalText !== "string" || !medication.originalText.trim() ||
      !["matched", "unresolved", "ambiguous", "not-assessed"].includes(medication.normalizedIdentity?.state))) return false;
  for (const field of ["substantialSuicideRisk", "priorAntipsychoticTherapy", "priorAntipsychoticTherapySuccessful", "clozapineContraindication", "recurrentNonAdherenceDeterioration"]) {
    if (!CLINICAL_STATES.has(value[field])) return false;
  }
  if (value.priorAntipsychoticTherapy === "yes") {
    if (!ANTIPSYCHOTICS.has(value.antipsychotic)) return false;
  } else if (value.antipsychotic !== null || value.priorAntipsychoticTherapySuccessful !== "not-assessed") return false;
  if ((value.clozapineContraindication === "yes") !== (value.clozapineContraindications.length > 0)) return false;
  if (value.status === "not-assessed" && (value.pastMedicalHistory.length || value.medications.length ||
      ["substantialSuicideRisk", "priorAntipsychoticTherapy", "priorAntipsychoticTherapySuccessful", "clozapineContraindication", "recurrentNonAdherenceDeterioration"].some((field) => value[field] !== "not-assessed"))) return false;
  return true;
}

class MedicalHistoryRepository {
  constructor(databasePath, importSources = []) {
    this.db = new DatabaseSync(databasePath);
    try {
      this.db.exec("PRAGMA foreign_keys = ON; PRAGMA journal_mode = WAL; PRAGMA busy_timeout = 5000;");
      this.#migrate();
      this.#importLegacy(importSources);
    } catch (error) {
      this.db.close();
      throw error;
    }
  }

  #transaction(work) {
    this.db.exec("BEGIN IMMEDIATE");
    try {
      const result = work();
      this.db.exec("COMMIT");
      return result;
    } catch (error) {
      this.db.exec("ROLLBACK");
      throw error;
    }
  }

  #migrate() {
    this.db.exec(`CREATE TABLE IF NOT EXISTS schema_migrations (
      version INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, applied_at TEXT NOT NULL
    ) STRICT;`);
    const applied = new Set(this.db.prepare("SELECT version FROM schema_migrations").all().map((row) => row.version));
    for (const migration of MIGRATIONS) {
      if (applied.has(migration.version)) continue;
      this.#transaction(() => {
        this.db.exec(migration.sql);
        this.db.prepare("INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)")
          .run(migration.version, migration.name, new Date().toISOString());
      });
    }
    const versions = this.db.prepare("SELECT version FROM schema_migrations ORDER BY version").all().map((row) => row.version);
    if (versions.length !== DATABASE_SCHEMA_VERSION || versions.some((version, index) => version !== index + 1)) {
      throw new Error("Medical History database migration history is unsupported");
    }
  }

  #importLegacy(sources) {
    const parsed = sources.map((source) => ({ source, parsed: parseSource(source) }));
    this.#transaction(() => {
      for (const item of parsed) {
        if (!item.parsed) continue;
        const { source } = item;
        const prior = this.db.prepare("SELECT source_hash FROM legacy_imports WHERE source_name = ?").get(source.name);
        if (prior) {
          if (prior.source_hash !== item.parsed.hash) throw new Error(`Legacy ${source.name} changed after import`);
          continue;
        }
        const entries = source.kind === "v2"
          ? Object.entries(item.parsed.payload?.assessments || {})
          : Array.isArray(item.parsed.payload) ? item.parsed.payload.map((value, index) => [String(index), value]) : null;
        if (!entries) throw new Error(`Legacy ${source.name} import has an invalid root`);
        if (source.kind === "v2" && (!item.parsed.payload?.assessments || Array.isArray(item.parsed.payload.assessments))) {
          throw new Error("Legacy Medical History v2 import must contain an assessments object");
        }
        let imported = 0;
        let quarantined = 0;
        const now = new Date().toISOString();
        for (const [sourceKey, value] of entries) {
          if (source.kind === "aliases") {
            const code = typeof value?.code === "string" ? value.code.trim().toUpperCase() : "";
            if (!/^[A-Z0-9]{6}$/.test(code) || !isUuid(value.patientId || value.context?.patientId) || !isUuid(value.encounterId || value.context?.encounterId)) {
              this.db.prepare(`INSERT INTO legacy_quarantine(source_name, source_key, reason, payload_json, quarantined_at)
                VALUES (?, ?, ?, ?, ?)`)
                .run(source.name, sourceKey, "activation-alias-missing-canonical-identity", canonicalJson(value), now);
              quarantined += 1;
              continue;
            }
            this.db.prepare(`INSERT INTO activation_aliases(code, patient_id, encounter_id, assessment_id, status, expires_at, updated_at)
              VALUES (?, ?, ?, ?, ?, ?, ?)
              ON CONFLICT(code) DO UPDATE SET patient_id = excluded.patient_id, encounter_id = excluded.encounter_id,
              assessment_id = excluded.assessment_id, status = excluded.status, expires_at = excluded.expires_at, updated_at = excluded.updated_at`)
              .run(code, value.patientId || value.context.patientId, value.encounterId || value.context.encounterId,
                isUuid(value.submissionId) ? value.submissionId : null, value.status || "active",
                Number.isFinite(Date.parse(value.expiresAt)) ? value.expiresAt : now, now);
            imported += 1;
            continue;
          }
          const assessment = source.kind === "v2"
            ? { ...value, provenance: { ...value?.provenance, optionSetVersion: value?.provenance?.optionSetVersion || "2.0.0" } }
            : legacyAssessment(value, now);
          if (!validCanonicalAssessment(assessment)) {
            this.db.prepare(`INSERT INTO legacy_quarantine(source_name, source_key, reason, payload_json, quarantined_at)
              VALUES (?, ?, ?, ?, ?)`)
              .run(source.name, sourceKey, "not-canonical-v2-assessment", canonicalJson(value), now);
            quarantined += 1;
            continue;
          }
          const createdAt = assessment.createdAt || now;
          const updatedAt = assessment.updatedAt || createdAt;
          const assessmentJson = canonicalJson(assessment);
          this.db.prepare(`INSERT INTO assessments(assessment_id, patient_id, encounter_id, resource_version, assessment_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)`)
            .run(assessment.assessmentId, assessment.patientId, assessment.encounterId, assessment.resourceVersion, assessmentJson, createdAt, updatedAt);
          this.db.prepare(`INSERT INTO assessment_versions(assessment_id, resource_version, actor_id, request_id, recorded_at, assessment_json)
            VALUES (?, ?, ?, ?, ?, ?)`)
            .run(assessment.assessmentId, assessment.resourceVersion, IMPORT_ACTOR_ID, assessment.provenance?.updatedRequestId || IMPORT_ACTOR_ID, now, assessmentJson);
          if (source.kind === "legacy" && /^[A-Za-z0-9]{6}$/.test(value.code || "")) {
            this.db.prepare(`INSERT INTO activation_aliases(code, patient_id, encounter_id, assessment_id, status, expires_at, updated_at)
              VALUES (?, ?, ?, ?, 'submitted', ?, ?)
              ON CONFLICT(code) DO UPDATE SET assessment_id = excluded.assessment_id, status = 'submitted', updated_at = excluded.updated_at`)
              .run(value.code.toUpperCase(), assessment.patientId, assessment.encounterId, assessment.assessmentId, updatedAt, now);
          }
          imported += 1;
        }
        this.db.prepare(`INSERT INTO legacy_imports(source_name, source_hash, imported_at, imported_count, quarantined_count)
          VALUES (?, ?, ?, ?, ?)`)
          .run(source.name, item.parsed.hash, now, imported, quarantined);
      }
    });
  }

  get(assessmentId) {
    const row = this.db.prepare("SELECT assessment_json FROM assessments WHERE assessment_id = ?").get(assessmentId);
    return row ? JSON.parse(row.assessment_json) : null;
  }

  latest(encounterId) {
    const row = this.db.prepare(`SELECT assessment_json FROM assessments WHERE encounter_id = ?
      ORDER BY updated_at DESC, assessment_id DESC LIMIT 1`).get(encounterId);
    return row ? JSON.parse(row.assessment_json) : null;
  }

  createIdempotent({ actorId, key, fingerprint, assessment, requestId, aliasCode = null }) {
    return this.#transaction(() => {
      this.db.prepare("DELETE FROM idempotency_records WHERE created_at <= ?").run(new Date(Date.now() - 86400000).toISOString());
      const prior = this.db.prepare(`SELECT fingerprint, response_json FROM idempotency_records
        WHERE actor_id = ? AND idempotency_key = ?`).get(actorId, key);
      if (prior) {
        if (prior.fingerprint !== fingerprint) return { conflict: true };
        return { replay: true, assessment: JSON.parse(prior.response_json) };
      }
      const assessmentJson = canonicalJson(assessment);
      this.db.prepare(`INSERT INTO assessments(assessment_id, patient_id, encounter_id, resource_version, assessment_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)`)
        .run(assessment.assessmentId, assessment.patientId, assessment.encounterId, assessment.resourceVersion,
          assessmentJson, assessment.createdAt, assessment.updatedAt);
      this.db.prepare(`INSERT INTO assessment_versions(assessment_id, resource_version, actor_id, request_id, recorded_at, assessment_json)
        VALUES (?, ?, ?, ?, ?, ?)`)
        .run(assessment.assessmentId, assessment.resourceVersion, actorId, requestId, assessment.updatedAt, assessmentJson);
      this.db.prepare(`INSERT INTO idempotency_records(actor_id, idempotency_key, fingerprint, response_json, created_at)
        VALUES (?, ?, ?, ?, ?)`)
        .run(actorId, key, fingerprint, assessmentJson, assessment.createdAt);
      if (aliasCode) {
        this.db.prepare(`UPDATE activation_aliases SET assessment_id = ?, status = 'submitted', updated_at = ? WHERE code = ?`)
          .run(assessment.assessmentId, assessment.updatedAt, aliasCode);
      }
      return { replay: false, assessment };
    });
  }

  update({ assessmentId, expectedVersion, assessment, actorId, requestId }) {
    return this.#transaction(() => {
      const current = this.db.prepare("SELECT resource_version FROM assessments WHERE assessment_id = ?").get(assessmentId);
      if (!current) return { missing: true };
      if (current.resource_version !== expectedVersion) return { stale: true };
      const assessmentJson = canonicalJson(assessment);
      const result = this.db.prepare(`UPDATE assessments SET resource_version = ?, assessment_json = ?, updated_at = ?
        WHERE assessment_id = ? AND resource_version = ?`)
        .run(assessment.resourceVersion, assessmentJson, assessment.updatedAt, assessmentId, expectedVersion);
      if (result.changes !== 1) return { stale: true };
      this.db.prepare(`INSERT INTO assessment_versions(assessment_id, resource_version, actor_id, request_id, recorded_at, assessment_json)
        VALUES (?, ?, ?, ?, ?, ?)`)
        .run(assessmentId, assessment.resourceVersion, actorId, requestId, assessment.updatedAt, assessmentJson);
      return { assessment };
    });
  }

  putAlias({ code, patientId, encounterId, expiresAt }) {
    const now = new Date().toISOString();
    this.db.prepare(`INSERT INTO activation_aliases(code, patient_id, encounter_id, assessment_id, status, expires_at, updated_at)
      VALUES (?, ?, ?, NULL, 'active', ?, ?)
      ON CONFLICT(code) DO UPDATE SET patient_id = excluded.patient_id, encounter_id = excluded.encounter_id,
      assessment_id = NULL, status = 'active', expires_at = excluded.expires_at, updated_at = excluded.updated_at`)
      .run(code, patientId, encounterId, expiresAt, now);
    return this.getAlias(code);
  }

  getAlias(code) {
    const row = this.db.prepare(`SELECT code, patient_id, encounter_id, assessment_id, status, expires_at, updated_at
      FROM activation_aliases WHERE code = ?`).get(code);
    if (!row) return null;
    return {
      code: row.code,
      patientId: row.patient_id,
      encounterId: row.encounter_id,
      assessmentId: row.assessment_id,
      status: row.status,
      expiresAt: row.expires_at,
      updatedAt: row.updated_at
    };
  }

  readiness() {
    const integrity = this.db.prepare("PRAGMA quick_check").get();
    const versions = this.db.prepare("SELECT version FROM schema_migrations ORDER BY version").all().map((row) => row.version);
    return integrity.quick_check === "ok" && versions.length === DATABASE_SCHEMA_VERSION &&
      versions.every((version, index) => version === index + 1);
  }

  stats() {
    return {
      assessments: this.db.prepare("SELECT COUNT(*) AS count FROM assessments").get().count,
      versions: this.db.prepare("SELECT COUNT(*) AS count FROM assessment_versions").get().count,
      quarantined: this.db.prepare("SELECT COUNT(*) AS count FROM legacy_quarantine").get().count
    };
  }

  close() {
    this.db.close();
  }
}

module.exports = { DATABASE_SCHEMA_VERSION, MedicalHistoryRepository, canonicalJson };
