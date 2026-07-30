CREATE TABLE plan_supersessions (
  prior_plan_id TEXT PRIMARY KEY REFERENCES finalized_plans(plan_id),
  prior_final_plan_id TEXT NOT NULL UNIQUE,
  successor_plan_id TEXT NOT NULL UNIQUE REFERENCES primary_plans(plan_id),
  supersession_record_json TEXT NOT NULL
);

CREATE TRIGGER plan_supersessions_immutable_update
BEFORE UPDATE ON plan_supersessions
BEGIN
  SELECT RAISE(ABORT, 'plan supersession records are immutable');
END;

CREATE TRIGGER plan_supersessions_immutable_delete
BEFORE DELETE ON plan_supersessions
BEGIN
  SELECT RAISE(ABORT, 'plan supersession records are immutable');
END;
