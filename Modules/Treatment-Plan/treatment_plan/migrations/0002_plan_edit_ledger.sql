CREATE TABLE primary_plans (
    plan_id TEXT PRIMARY KEY NOT NULL,
    primary_plan_json TEXT NOT NULL
);

CREATE TABLE plan_edit_events (
    plan_id TEXT NOT NULL,
    sequence INTEGER NOT NULL CHECK (sequence > 0),
    edit_id TEXT NOT NULL UNIQUE,
    event_json TEXT NOT NULL,
    PRIMARY KEY (plan_id, sequence),
    FOREIGN KEY (plan_id) REFERENCES primary_plans(plan_id)
);

CREATE INDEX plan_edit_events_plan_sequence
    ON plan_edit_events(plan_id, sequence);
