"""DSM-5-TR schizophrenia criteria evaluation for decision support."""
from __future__ import annotations

from dataclasses import dataclass, field

CRITERIA: list[dict] = [
    {"id": "A1", "group": "Criterion A - Characteristic symptoms", "text": "Delusions (fixed false beliefs resistant to evidence).", "core": True},
    {"id": "A2", "group": "Criterion A - Characteristic symptoms", "text": "Hallucinations (perceptual experiences without external stimulus).", "core": True},
    {"id": "A3", "group": "Criterion A - Characteristic symptoms", "text": "Disorganized thinking / speech (frequent derailment or incoherence).", "core": True},
    {"id": "A4", "group": "Criterion A - Characteristic symptoms", "text": "Grossly disorganized or catatonic behaviour.", "core": False},
    {"id": "A5", "group": "Criterion A - Characteristic symptoms", "text": "Negative symptoms: diminished emotional expression, avolition, alogia, anhedonia, asociality.", "core": False},
    {"id": "A6", "group": "Criterion A - Characteristic symptoms", "text": "Symptoms present for a significant portion of 1 month (or less if successfully treated).", "core": False, "duration": True},
    {"id": "B1", "group": "Criterion B - Functioning", "text": "Disturbance manifests in reduced level of functioning in work, interpersonal relations, or self-care.", "core": False, "guard": "B"},
    {"id": "C1", "group": "Criterion C - Schizoaffective exclusion", "text": "No major mood episodes occur concurrently with active-phase symptoms (mood episodes, if present, are present for a minority of the total duration).", "core": False, "guard": "C"},
    {"id": "D1", "group": "Criterion D - Substance / medical exclusion", "text": "Disturbure is not attributable to substance effects or another medical condition.", "core": False, "guard": "D"},
]
GUARD_LABEL = {"B": "Criterion B unmet", "C": "Schizoaffective not excluded", "D": "Substance/medical not excluded"}


@dataclass
class Evaluation:
    met: bool
    checked_ids: list[str] = field(default_factory=list)
    a_count: int = 0
    core_count: int = 0
    failures: list[str] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "met": self.met,
            "a_count": self.a_count,
            "core_count": self.core_count,
            "failures": self.failures,
            "reason": self.reason,
            "checked": list(self.checked_ids),
        }


def get_criteria() -> list[dict]:
    return [criterion.copy() for criterion in CRITERIA]


def meta_contract() -> dict:
    return {
        "symptom_ids": [item["id"] for item in CRITERIA if item["group"].startswith("Criterion A") and not item.get("duration")],
        "core_ids": [item["id"] for item in CRITERIA if item.get("core")],
        "duration_id": next(item["id"] for item in CRITERIA if item.get("duration")),
        "guard_ids": [item["id"] for item in CRITERIA if item.get("guard")],
        "symptom_threshold": 2,
        "core_threshold": 1,
    }


def _classify(criterion_id: str) -> dict | None:
    return next((item for item in CRITERIA if item["id"] == criterion_id), None)


def evaluate(checked_ids: list[str]) -> Evaluation:
    checked = set(checked_ids)
    symptom_ids = [item["id"] for item in CRITERIA if item["group"].startswith("Criterion A") and not item.get("duration")]
    core_ids = [item["id"] for item in CRITERIA if item.get("core")]
    duration_id = next(item["id"] for item in CRITERIA if item.get("duration"))
    guard_ids = {item["guard"]: item["id"] for item in CRITERIA if item.get("guard")}
    a_count = len([item for item in symptom_ids if item in checked])
    core_count = len([item for item in core_ids if item in checked])
    failures: list[str] = []
    if a_count < 2:
        failures.append(f"Criterion A: only {a_count} of required >=2 characteristic symptoms")
    if a_count >= 1 and core_count < 1:
        failures.append("Criterion A: at least 1 symptom must be from the core triad (A1-A3)")
    if a_count >= 1 and duration_id not in checked:
        failures.append("Criterion A: duration not established (1-month)")
    for guard, item_id in guard_ids.items():
        if item_id not in checked:
            failures.append(GUARD_LABEL[guard])
    met = not failures
    reason = "DSM-5-TR schizophrenia criteria met." if met else "Criteria not met: " + "; ".join(failures)
    return Evaluation(met, sorted(checked), a_count, core_count, failures, reason)


def _demo():
    import pathlib
    import sys
    import unittest

    here = pathlib.Path(__file__).resolve().parents[1]
    if str(here.parent) not in sys.path:
        sys.path.insert(0, str(here.parent))
    suite = unittest.TestLoader().loadTestsFromName("test_unittest.TestCriteriaRules")
    if not unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful():
        raise SystemExit(1)
    print("OK: criteria engine self-check passed")


if __name__ == "__main__":
    _demo()
