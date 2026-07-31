"""SQLite adapter for the TP-15 append-only Plan Edit store seam."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Mapping

from .edit_ledger import (
    InvalidEdit,
    PlanAlreadyExists,
    PlanEditStore,
    PlanNotFound,
    PlanFinalized,
    PlanSuperseded,
    PreconditionFailed,
    StoredPlanEdits,
)


class SQLitePlanEditStore(PlanEditStore):
    def __init__(self, path: Path) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def create(self, plan_id: str, primary_plan: Mapping[str, Any]) -> None:
        payload = _dump(primary_plan)
        try:
            with closing(self._connect()) as connection:
                connection.execute(
                    "INSERT INTO primary_plans(plan_id, primary_plan_json) VALUES (?, ?)",
                    (plan_id, payload),
                )
                connection.commit()
        except sqlite3.IntegrityError as exc:
            raise PlanAlreadyExists(f"plan {plan_id!r} already exists") from exc

    def read(self, plan_id: str) -> StoredPlanEdits | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT primary_plan_json FROM primary_plans WHERE plan_id = ?", (plan_id,)
            ).fetchone()
            if row is None:
                return None
            event_rows = connection.execute(
                "SELECT event_json FROM plan_edit_events WHERE plan_id = ? ORDER BY sequence",
                (plan_id,),
            ).fetchall()
            final_row = connection.execute(
                "SELECT finalization_record_json FROM finalized_plans WHERE plan_id = ?", (plan_id,)
            ).fetchone()
        try:
            return StoredPlanEdits(
                json.loads(row[0]),
                tuple(json.loads(item[0]) for item in event_rows),
                json.loads(final_row[0]) if final_row else None,
            )
        except (TypeError, ValueError) as exc:
            raise InvalidEdit("stored Plan Edit JSON is invalid") from exc

    def append(self, plan_id: str, expected_sequence: int, event: Mapping[str, Any]) -> None:
        payload = _dump(event)
        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                exists = connection.execute(
                    "SELECT 1 FROM primary_plans WHERE plan_id = ?", (plan_id,)
                ).fetchone()
                if exists is None:
                    raise PlanNotFound(f"plan {plan_id!r} was not found")
                finalized = connection.execute(
                    "SELECT 1 FROM finalized_plans WHERE plan_id = ?", (plan_id,)
                ).fetchone()
                if finalized is not None:
                    raise PlanFinalized("the plan is already finalized")
                current = connection.execute(
                    "SELECT COUNT(*) FROM plan_edit_events WHERE plan_id = ?", (plan_id,)
                ).fetchone()[0]
                if current != expected_sequence:
                    raise PreconditionFailed("the plan changed after it was read")
                sequence = int(event.get("sequence", -1))
                if sequence != expected_sequence + 1:
                    raise InvalidEdit("Plan Edit sequence is not contiguous")
                connection.execute(
                    "INSERT INTO plan_edit_events(plan_id, sequence, edit_id, event_json) VALUES (?, ?, ?, ?)",
                    (plan_id, sequence, str(event.get("editId", "")), payload),
                )
                connection.commit()
            except (PlanNotFound, PlanFinalized, PreconditionFailed, InvalidEdit):
                connection.rollback()
                raise
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                raise PreconditionFailed("Plan Edit append conflicted with another writer") from exc

    def finalize(self, plan_id: str, expected_sequence: int, record: Mapping[str, Any]) -> None:
        payload = _dump(record)
        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                exists = connection.execute(
                    "SELECT 1 FROM primary_plans WHERE plan_id = ?", (plan_id,)
                ).fetchone()
                if exists is None:
                    raise PlanNotFound(f"plan {plan_id!r} was not found")
                if connection.execute(
                    "SELECT 1 FROM finalized_plans WHERE plan_id = ?", (plan_id,)
                ).fetchone() is not None:
                    raise PlanFinalized("the plan is already finalized")
                current = connection.execute(
                    "SELECT COUNT(*) FROM plan_edit_events WHERE plan_id = ?", (plan_id,)
                ).fetchone()[0]
                if current != expected_sequence:
                    raise PreconditionFailed("the plan changed after its safety check")
                connection.execute(
                    "INSERT INTO finalized_plans(plan_id, finalization_record_json) VALUES (?, ?)",
                    (plan_id, payload),
                )
                connection.commit()
            except (PlanNotFound, PlanFinalized, PreconditionFailed):
                connection.rollback()
                raise
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                raise PlanFinalized("the plan is already finalized") from exc

    def create_successor(
        self,
        prior_plan_id: str,
        successor_plan_id: str,
        primary_plan: Mapping[str, Any],
        record: Mapping[str, Any],
    ) -> None:
        plan_payload = _dump(primary_plan)
        record_payload = _dump(record)
        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                if connection.execute(
                    "SELECT 1 FROM primary_plans WHERE plan_id = ?", (prior_plan_id,)
                ).fetchone() is None:
                    raise PlanNotFound(f"plan {prior_plan_id!r} was not found")
                if connection.execute(
                    "SELECT 1 FROM finalized_plans WHERE plan_id = ?", (prior_plan_id,)
                ).fetchone() is None:
                    raise InvalidEdit("only a finalized plan can be superseded")
                if connection.execute(
                    "SELECT 1 FROM plan_supersessions WHERE prior_plan_id = ?", (prior_plan_id,)
                ).fetchone() is not None:
                    raise PlanSuperseded("the finalized plan already has a successor")
                connection.execute(
                    "INSERT INTO primary_plans(plan_id, primary_plan_json) VALUES (?, ?)",
                    (successor_plan_id, plan_payload),
                )
                connection.execute(
                    "INSERT INTO plan_supersessions(prior_plan_id, prior_final_plan_id, successor_plan_id, supersession_record_json) VALUES (?, ?, ?, ?)",
                    (
                        prior_plan_id,
                        str(record.get("priorFinalPlanId", "")),
                        successor_plan_id,
                        record_payload,
                    ),
                )
                connection.commit()
            except (PlanNotFound, PlanSuperseded, InvalidEdit):
                connection.rollback()
                raise
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                if connection.execute(
                    "SELECT 1 FROM plan_supersessions WHERE prior_plan_id = ?", (prior_plan_id,)
                ).fetchone() is not None:
                    raise PlanSuperseded("the finalized plan already has a successor") from exc
                raise PlanAlreadyExists(
                    f"plan {successor_plan_id!r} already exists or supersession identifiers conflict"
                ) from exc

    def read_supersession(self, prior_plan_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT supersession_record_json FROM plan_supersessions WHERE prior_plan_id = ?",
                (prior_plan_id,),
            ).fetchone()
        if row is None:
            return None
        try:
            return json.loads(row[0])
        except (TypeError, ValueError) as exc:
            raise InvalidEdit("stored supersession JSON is invalid") from exc

    def list_plan_ids_by_patient(self, patient_id: str) -> tuple[str, ...]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT plan_id, primary_plan_json FROM primary_plans ORDER BY rowid DESC"
            ).fetchall()
        try:
            return tuple(
                plan_id
                for plan_id, payload in rows
                if json.loads(payload).get("patientId") == patient_id
            )
        except (TypeError, ValueError) as exc:
            raise InvalidEdit("stored Primary Plan JSON is invalid") from exc


def _dump(value: Mapping[str, Any]) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise InvalidEdit("plan and edit values must be finite JSON values") from exc
