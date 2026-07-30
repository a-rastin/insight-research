const { DatabaseSync } = require("node:sqlite");

const DATABASE_SCHEMA_VERSION = 1;

function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value !== null && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

class SuicideRiskRepository {
  constructor(databasePath) {
    this.db = new DatabaseSync(databasePath);
    try {
      this.db.exec("PRAGMA journal_mode = WAL; PRAGMA busy_timeout = 5000;");
      this.#migrate();
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
    if (!this.db.prepare("SELECT version FROM schema_migrations WHERE version = 1").get()) {
      this.#transaction(() => {
        this.db.exec(`
          CREATE TABLE assessments (
            assessment_id TEXT PRIMARY KEY,
            encounter_id TEXT NOT NULL,
            resource_version INTEGER NOT NULL CHECK(resource_version >= 1),
            assessment_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
          ) STRICT;
          CREATE INDEX assessments_encounter_idx ON assessments(encounter_id, updated_at DESC, assessment_id DESC);
          CREATE TABLE assessment_versions (
            assessment_id TEXT NOT NULL,
            resource_version INTEGER NOT NULL,
            actor_id TEXT NOT NULL,
            request_id TEXT NOT NULL,
            assessment_json TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            PRIMARY KEY(assessment_id, resource_version)
          ) STRICT;
          CREATE TABLE idempotency_records (
            actor_id TEXT NOT NULL,
            idempotency_key TEXT NOT NULL,
            fingerprint TEXT NOT NULL,
            response_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY(actor_id, idempotency_key)
          ) STRICT;
        `);
        this.db.prepare("INSERT INTO schema_migrations(version, name, applied_at) VALUES (1, ?, ?)")
          .run("suicide-risk-assessments-v1", new Date().toISOString());
      });
    }
    const versions = this.db.prepare("SELECT version FROM schema_migrations ORDER BY version").all().map((row) => row.version);
    if (versions.length !== DATABASE_SCHEMA_VERSION || versions[0] !== 1) throw new Error("Unsupported migration history");
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

  createIdempotent({ actorId, key, fingerprint, assessment, requestId }) {
    return this.#transaction(() => {
      this.db.prepare("DELETE FROM idempotency_records WHERE created_at <= ?").run(new Date(Date.now() - 86400000).toISOString());
      const prior = this.db.prepare("SELECT fingerprint, response_json FROM idempotency_records WHERE actor_id = ? AND idempotency_key = ?")
        .get(actorId, key);
      if (prior) return prior.fingerprint === fingerprint
        ? { replay: true, assessment: JSON.parse(prior.response_json) }
        : { conflict: true };
      const json = canonicalJson(assessment);
      this.db.prepare("INSERT INTO assessments VALUES (?, ?, ?, ?, ?)")
        .run(assessment.assessmentId, assessment.encounterId, assessment.resourceVersion, json, assessment.updatedAt);
      this.db.prepare("INSERT INTO assessment_versions VALUES (?, ?, ?, ?, ?, ?)")
        .run(assessment.assessmentId, 1, actorId, requestId, json, assessment.updatedAt);
      this.db.prepare("INSERT INTO idempotency_records VALUES (?, ?, ?, ?, ?)")
        .run(actorId, key, fingerprint, json, assessment.createdAt);
      return { replay: false, assessment };
    });
  }

  update({ assessment, expectedVersion, actorId, requestId }) {
    return this.#transaction(() => {
      const current = this.db.prepare("SELECT resource_version FROM assessments WHERE assessment_id = ?").get(assessment.assessmentId);
      if (!current) return { missing: true };
      if (current.resource_version !== expectedVersion) return { stale: true };
      const json = canonicalJson(assessment);
      const result = this.db.prepare(`UPDATE assessments SET resource_version = ?, assessment_json = ?, updated_at = ?
        WHERE assessment_id = ? AND resource_version = ?`)
        .run(assessment.resourceVersion, json, assessment.updatedAt, assessment.assessmentId, expectedVersion);
      if (result.changes !== 1) return { stale: true };
      this.db.prepare("INSERT INTO assessment_versions VALUES (?, ?, ?, ?, ?, ?)")
        .run(assessment.assessmentId, assessment.resourceVersion, actorId, requestId, json, assessment.updatedAt);
      return { assessment };
    });
  }

  readiness() {
    return this.db.prepare("PRAGMA quick_check").get().quick_check === "ok" &&
      this.db.prepare("SELECT COUNT(*) AS count FROM schema_migrations").get().count === DATABASE_SCHEMA_VERSION;
  }

  close() {
    this.db.close();
  }
}

module.exports = { DATABASE_SCHEMA_VERSION, SuicideRiskRepository, canonicalJson };
