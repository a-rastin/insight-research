CREATE TABLE finalized_plans (
    plan_id TEXT PRIMARY KEY NOT NULL,
    finalization_record_json TEXT NOT NULL,
    FOREIGN KEY (plan_id) REFERENCES primary_plans(plan_id)
);
