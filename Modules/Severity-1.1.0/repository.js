import fs from "fs";
import { createHash } from "crypto";
import { DatabaseSync } from "node:sqlite";
import { isUuid } from "./panss.js";

export const DATABASE_SCHEMA_VERSION = 2;
const IMPORT_ACTOR_ID = "00000000-0000-4000-8000-000000000000";

const MIGRATIONS = [
  {
    version: 1,
    name: "severity-assessments-v1",
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
      CREATE INDEX assessments_encounter_idx ON assessments(encounter_id, updated_at DESC);
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
    `
  },
  {
    version: 2,
    name: "severity-legacy-import-v2",
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
    return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function parseImportFile(source) {
  if (!source.path || !fs.existsSync(source.path)) return null;
  const bytes = fs.readFileSync(source.path);
  let payload;
  try {
    payload = JSON.parse(bytes.toString("utf8"));
  } catch (error) {
    throw new Error(`Legacy ${source.name} import is corrupt`, { cause: error });
  }
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new Error(`Legacy ${source.name} import must contain a JSON object`);
  }
  return { payload, hash: createHash("sha256").update(bytes).digest("hex") };
}

function importEntries(source, payload) {
  if (source.kind === "v2") {
    if (!payload.assessments || typeof payload.assessments !== "object" || Array.isArray(payload.assessments)) {
      throw new Error("Legacy v2 import must contain an assessments object");
    }
    return Object.entries(payload.assessments);
  }
  return Object.entries(payload);
}

export class SeverityRepository {
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
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        applied_at TEXT NOT NULL
      ) STRICT;
    `);
    const applied = new Set(this.db.prepare("SELECT version FROM schema_migrations").all().map(row => row.version));
    for (const migration of MIGRATIONS) {
      if (applied.has(migration.version)) continue;
      this.#transaction(() => {
        this.db.exec(migration.sql);
        this.db.prepare("INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)")
          .run(migration.version, migration.name, new Date().toISOString());
      });
    }
    const versions = this.db.prepare("SELECT version FROM schema_migrations ORDER BY version").all().map(row => row.version);
    if (versions.length !== DATABASE_SCHEMA_VERSION || versions.some((version, index) => version !== index + 1)) {
      throw new Error("Severity database migration history is unsupported");
    }
  }

  #importLegacy(sources) {
    const parsedSources = sources.map(source => ({ source, parsed: parseImportFile(source) }));
    this.#transaction(() => {
      for (const { source, parsed } of parsedSources) {
        if (!parsed) continue;
        const prior = this.db.prepare("SELECT source_hash FROM legacy_imports WHERE source_name = ?").get(source.name);
        if (prior) {
          if (prior.source_hash !== parsed.hash) throw new Error(`Legacy ${source.name} changed after import`);
          continue;
        }
        let imported = 0;
        let quarantined = 0;
        const now = new Date().toISOString();
        for (const [sourceKey, value] of importEntries(source, parsed.payload)) {
          const payloadJson = canonicalJson(value);
          if (!value || typeof value !== "object" || !isUuid(value.patientId) || !isUuid(value.encounterId) || !isUuid(value.assessmentId)) {
            this.db.prepare(`INSERT INTO legacy_quarantine(source_name, source_key, reason, payload_json, quarantined_at)
              VALUES (?, ?, ?, ?, ?)`)
              .run(source.name, sourceKey, "missing-or-invalid-canonical-identity", payloadJson, now);
            quarantined += 1;
            continue;
          }
          const createdAt = value.provenance?.createdAt || now;
          const updatedAt = value.provenance?.updatedAt || createdAt;
          const assessment = value;
          const assessmentJson = canonicalJson(assessment);
          this.db.prepare(`INSERT INTO assessments(
            assessment_id, patient_id, encounter_id, resource_version, assessment_json, created_at, updated_at
          ) VALUES (?, ?, ?, ?, ?, ?, ?)`)
            .run(assessment.assessmentId, assessment.patientId, assessment.encounterId, assessment.resourceVersion, assessmentJson, createdAt, updatedAt);
          this.db.prepare(`INSERT INTO assessment_versions(
            assessment_id, resource_version, actor_id, request_id, recorded_at, assessment_json
          ) VALUES (?, ?, ?, ?, ?, ?)`)
            .run(assessment.assessmentId, assessment.resourceVersion, IMPORT_ACTOR_ID,
              assessment.provenance?.updatedRequestId || IMPORT_ACTOR_ID, now, assessmentJson);
          imported += 1;
        }
        this.db.prepare(`INSERT INTO legacy_imports(
          source_name, source_hash, imported_at, imported_count, quarantined_count
        ) VALUES (?, ?, ?, ?, ?)`)
          .run(source.name, parsed.hash, now, imported, quarantined);
      }
    });
  }

  get(assessmentId) {
    const row = this.db.prepare("SELECT assessment_json FROM assessments WHERE assessment_id = ?").get(assessmentId);
    return row ? JSON.parse(row.assessment_json) : null;
  }

  createIdempotent({ actorId, key, fingerprint, assessment, requestId }) {
    return this.#transaction(() => {
      this.db.prepare("DELETE FROM idempotency_records WHERE created_at <= ?")
        .run(new Date(Date.now() - 86400000).toISOString());
      const prior = this.db.prepare(`SELECT fingerprint, response_json FROM idempotency_records
        WHERE actor_id = ? AND idempotency_key = ?`).get(actorId, key);
      if (prior) {
        if (prior.fingerprint !== fingerprint) return { conflict: true };
        return { replay: true, assessment: JSON.parse(prior.response_json) };
      }
      const assessmentJson = canonicalJson(assessment);
      this.db.prepare(`INSERT INTO assessments(
        assessment_id, patient_id, encounter_id, resource_version, assessment_json, created_at, updated_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?)`)
        .run(assessment.assessmentId, assessment.patientId, assessment.encounterId, assessment.resourceVersion,
          assessmentJson, assessment.provenance.createdAt, assessment.provenance.updatedAt);
      this.db.prepare(`INSERT INTO assessment_versions(
        assessment_id, resource_version, actor_id, request_id, recorded_at, assessment_json
      ) VALUES (?, ?, ?, ?, ?, ?)`)
        .run(assessment.assessmentId, assessment.resourceVersion, actorId, requestId,
          assessment.provenance.updatedAt, assessmentJson);
      this.db.prepare(`INSERT INTO idempotency_records(
        actor_id, idempotency_key, fingerprint, response_json, created_at
      ) VALUES (?, ?, ?, ?, ?)`)
        .run(actorId, key, fingerprint, assessmentJson, assessment.provenance.createdAt);
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
        .run(assessment.resourceVersion, assessmentJson, assessment.provenance.updatedAt, assessmentId, expectedVersion);
      if (result.changes !== 1) return { stale: true };
      this.db.prepare(`INSERT INTO assessment_versions(
        assessment_id, resource_version, actor_id, request_id, recorded_at, assessment_json
      ) VALUES (?, ?, ?, ?, ?, ?)`)
        .run(assessmentId, assessment.resourceVersion, actorId, requestId,
          assessment.provenance.updatedAt, assessmentJson);
      return { assessment };
    });
  }

  readiness() {
    const integrity = this.db.prepare("PRAGMA quick_check").get();
    const version = this.db.prepare("SELECT MAX(version) AS version FROM schema_migrations").get().version;
    return integrity.quick_check === "ok" && version === DATABASE_SCHEMA_VERSION;
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
