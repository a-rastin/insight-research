CREATE TRIGGER finalized_plans_immutable_update
BEFORE UPDATE ON finalized_plans
BEGIN
    SELECT RAISE(ABORT, 'finalized plans are immutable');
END;

CREATE TRIGGER finalized_plans_immutable_delete
BEFORE DELETE ON finalized_plans
BEGIN
    SELECT RAISE(ABORT, 'finalized plans are immutable');
END;
