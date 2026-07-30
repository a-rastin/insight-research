DROP TRIGGER IF EXISTS finalized_plans_immutable_update;
DROP TRIGGER IF EXISTS finalized_plans_immutable_delete;
DROP TRIGGER IF EXISTS finalized_plans_immutable ON finalized_plans;
DROP FUNCTION IF EXISTS reject_finalized_plans_mutation();
