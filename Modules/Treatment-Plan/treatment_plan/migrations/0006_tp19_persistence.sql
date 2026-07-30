CREATE TABLE recommendation_runs (
    run_id {{UUID}} PRIMARY KEY NOT NULL CHECK ({{UUID_CHECK:run_id}}),
    idempotency_key TEXT NOT NULL UNIQUE,
    input_hash TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'completed', 'failed')),
    created_at {{TIMESTAMP}} NOT NULL,
    completed_at {{TIMESTAMP}}
);

CREATE TABLE input_snapshots (
    snapshot_id {{UUID}} PRIMARY KEY NOT NULL CHECK ({{UUID_CHECK:snapshot_id}}),
    run_id {{UUID}} NOT NULL UNIQUE CHECK ({{UUID_CHECK:run_id}}),
    patient_token_hash TEXT NOT NULL,
    encounter_id {{UUID}} NOT NULL CHECK ({{UUID_CHECK:encounter_id}}),
    schema_version TEXT NOT NULL CHECK (length(schema_version) > 0),
    snapshot_envelope {{JSON}} CHECK (snapshot_envelope IS NULL OR {{JSON_CHECK:snapshot_envelope}}),
    captured_at {{TIMESTAMP}} NOT NULL,
    phi_expires_at {{TIMESTAMP}} NOT NULL,
    deleted_at {{TIMESTAMP}},
    FOREIGN KEY (run_id) REFERENCES recommendation_runs(run_id)
);

CREATE TABLE plans (
    plan_id {{UUID}} PRIMARY KEY NOT NULL CHECK ({{UUID_CHECK:plan_id}}),
    run_id {{UUID}} NOT NULL CHECK ({{UUID_CHECK:run_id}}),
    idempotency_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (status IN ('draft', 'final', 'superseded')),
    current_version INTEGER NOT NULL CHECK (current_version > 0),
    created_at {{TIMESTAMP}} NOT NULL,
    finalized_at {{TIMESTAMP}},
    phi_expires_at {{TIMESTAMP}} NOT NULL,
    deleted_at {{TIMESTAMP}},
    FOREIGN KEY (run_id) REFERENCES recommendation_runs(run_id),
    UNIQUE (plan_id, current_version)
);

CREATE TABLE plan_versions (
    version_id {{UUID}} PRIMARY KEY NOT NULL CHECK ({{UUID_CHECK:version_id}}),
    plan_id {{UUID}} NOT NULL CHECK ({{UUID_CHECK:plan_id}}),
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    schema_version TEXT NOT NULL CHECK (length(schema_version) > 0),
    content_hash TEXT NOT NULL,
    plan_envelope {{JSON}} CHECK (plan_envelope IS NULL OR {{JSON_CHECK:plan_envelope}}),
    created_at {{TIMESTAMP}} NOT NULL,
    FOREIGN KEY (plan_id) REFERENCES plans(plan_id),
    UNIQUE (plan_id, version_number),
    UNIQUE (plan_id, content_hash)
);

CREATE TABLE plan_items (
    item_id {{UUID}} PRIMARY KEY NOT NULL CHECK ({{UUID_CHECK:item_id}}),
    version_id {{UUID}} NOT NULL CHECK ({{UUID_CHECK:version_id}}),
    item_key TEXT NOT NULL,
    item_type TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    schema_version TEXT NOT NULL CHECK (length(schema_version) > 0),
    item_envelope {{JSON}} CHECK (item_envelope IS NULL OR {{JSON_CHECK:item_envelope}}),
    FOREIGN KEY (version_id) REFERENCES plan_versions(version_id),
    UNIQUE (version_id, item_key),
    UNIQUE (version_id, ordinal)
);

CREATE TABLE plan_edits (
    edit_id {{UUID}} PRIMARY KEY NOT NULL CHECK ({{UUID_CHECK:edit_id}}),
    plan_id {{UUID}} NOT NULL CHECK ({{UUID_CHECK:plan_id}}),
    version_id {{UUID}} CHECK (version_id IS NULL OR {{UUID_CHECK:version_id}}),
    sequence INTEGER NOT NULL CHECK (sequence > 0),
    actor_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    schema_version TEXT NOT NULL CHECK (length(schema_version) > 0),
    edit_envelope {{JSON}} NOT NULL CHECK ({{JSON_CHECK:edit_envelope}}),
    created_at {{TIMESTAMP}} NOT NULL,
    FOREIGN KEY (plan_id) REFERENCES plans(plan_id),
    FOREIGN KEY (version_id) REFERENCES plan_versions(version_id),
    UNIQUE (plan_id, sequence)
);

CREATE TABLE safety_findings (
    finding_id {{UUID}} PRIMARY KEY NOT NULL CHECK ({{UUID_CHECK:finding_id}}),
    version_id {{UUID}} NOT NULL CHECK ({{UUID_CHECK:version_id}}),
    finding_key TEXT NOT NULL,
    severity TEXT NOT NULL,
    blocks_finalization {{BOOLEAN}} NOT NULL DEFAULT {{FALSE}},
    schema_version TEXT NOT NULL CHECK (length(schema_version) > 0),
    finding_envelope {{JSON}} CHECK (finding_envelope IS NULL OR {{JSON_CHECK:finding_envelope}}),
    FOREIGN KEY (version_id) REFERENCES plan_versions(version_id),
    UNIQUE (version_id, finding_key)
);

CREATE TABLE evidence_links (
    evidence_link_id {{UUID}} PRIMARY KEY NOT NULL CHECK ({{UUID_CHECK:evidence_link_id}}),
    plan_item_id {{UUID}} CHECK (plan_item_id IS NULL OR {{UUID_CHECK:plan_item_id}}),
    safety_finding_id {{UUID}} CHECK (safety_finding_id IS NULL OR {{UUID_CHECK:safety_finding_id}}),
    evidence_kind TEXT NOT NULL,
    evidence_reference TEXT,
    schema_version TEXT NOT NULL CHECK (length(schema_version) > 0),
    evidence_envelope {{JSON}} CHECK (evidence_envelope IS NULL OR {{JSON_CHECK:evidence_envelope}}),
    FOREIGN KEY (plan_item_id) REFERENCES plan_items(item_id),
    FOREIGN KEY (safety_finding_id) REFERENCES safety_findings(finding_id),
    CHECK ((plan_item_id IS NOT NULL AND safety_finding_id IS NULL) OR
           (plan_item_id IS NULL AND safety_finding_id IS NOT NULL)),
    UNIQUE (plan_item_id, evidence_kind, evidence_reference),
    UNIQUE (safety_finding_id, evidence_kind, evidence_reference)
);

CREATE TABLE clinical_provenance (
    provenance_id {{UUID}} PRIMARY KEY NOT NULL CHECK ({{UUID_CHECK:provenance_id}}),
    version_id {{UUID}} NOT NULL CHECK ({{UUID_CHECK:version_id}}),
    audit_event_id {{UUID}} NOT NULL UNIQUE CHECK ({{UUID_CHECK:audit_event_id}}),
    source_module TEXT NOT NULL,
    source_record_id TEXT NOT NULL,
    source_version TEXT NOT NULL,
    schema_version TEXT NOT NULL CHECK (length(schema_version) > 0),
    provenance_envelope {{JSON}} NOT NULL CHECK ({{JSON_CHECK:provenance_envelope}}),
    observed_at {{TIMESTAMP}} NOT NULL,
    audit_retain_until {{TIMESTAMP}} NOT NULL,
    FOREIGN KEY (version_id) REFERENCES plan_versions(version_id),
    UNIQUE (version_id, source_module, source_record_id, source_version)
);

CREATE INDEX input_snapshots_phi_expiry ON input_snapshots(phi_expires_at, deleted_at);
CREATE INDEX plans_phi_expiry ON plans(phi_expires_at, deleted_at);
CREATE INDEX plan_versions_plan ON plan_versions(plan_id, version_number);
CREATE INDEX plan_edits_plan_sequence ON plan_edits(plan_id, sequence);
CREATE INDEX clinical_provenance_retention ON clinical_provenance(audit_retain_until);
