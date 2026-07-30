import unittest

from treatment_plan.bn_evaluation import (
    BnEvaluationBundle,
    BnModel,
    MappingCoverage,
    ModelEvaluation,
)
from treatment_plan.primary_plan import (
    EvidenceKind,
    PrimaryPlanSynthesizer,
    SourceFact,
    SynthesisBlocked,
)
from treatment_plan.safety_policy import (
    ProbabilisticRecommendation,
    SafetyFacts,
    SafetyPolicy,
)


HASH = "sha256:" + "a" * 64


def evaluation(model, posterior):
    return ModelEvaluation(
        f"evaluation-{model.value}", model, "2026.07.1", HASH,
        (("Evidence", "Synthetic"),), tuple(posterior), "2026-07-14T12:00:00Z",
    )


def bundle(setting=(("outpatient", .7), ("inpatient", .3)), meds=(("candidate-a", .8), ("candidate-b", .2))):
    evaluations = (
        evaluation(BnModel.TREATMENT_SETTING, setting),
        evaluation(BnModel.PHARMACOTHERAPY, meds),
        evaluation(BnModel.INVOLUNTARY_TREATMENT, (("voluntary", 1.0),)),
        evaluation(BnModel.CLOZAPINE_SUICIDE_RISK, (("not-indicated", 1.0),)),
    )
    coverage = tuple(MappingCoverage(model, 1, 1, (), ()) for model in BnModel)
    return BnEvaluationBundle("snapshot-12", "1.0.0", evaluations, coverage, ())


def facts():
    return (
        SourceFact("fact-severity", "severity", "severity-1", "1.0.0", HASH, "/severity", BnModel.TREATMENT_SETTING),
        SourceFact("fact-history", "medical-history", "history-1", "1.0.0", HASH, "/medicalHistory", BnModel.PHARMACOTHERAPY),
    )


class TP12PrimaryPlanTests(unittest.TestCase):
    def test_synthesizes_all_domains_alternatives_limitations_and_provenance(self):
        safety = SafetyPolicy().apply(
            (
                ProbabilisticRecommendation("candidate-a", .8),
                ProbabilisticRecommendation("candidate-b", .2),
            ),
            SafetyFacts(),
        )
        plan = PrimaryPlanSynthesizer().synthesize(
            bundle(), safety, facts(), timezone="America/Los_Angeles"
        )

        self.assertEqual(plan.treatment_setting.value, {"setting": "outpatient"})
        self.assertEqual(plan.pharmacotherapy.value["medicationCode"], "synthetic-candidate-a")
        self.assertEqual(plan.next_appointment.value["interval"], "P14D")
        self.assertEqual(len(plan.alternatives), 2)
        self.assertGreaterEqual(len(plan.limitations), 2)
        for recommendation in plan.recommendations:
            kinds = {link.kind for link in recommendation.evidence_links}
            self.assertIn(EvidenceKind.SOURCE_FACT, kinds)
            self.assertIn(EvidenceKind.MODEL_EVALUATION, kinds)
            self.assertIn(EvidenceKind.POLICY_RULE, kinds)

    def test_same_input_and_versions_produce_identical_semantics(self):
        safety = SafetyPolicy().apply(
            (
                ProbabilisticRecommendation("candidate-b", .2),
                ProbabilisticRecommendation("candidate-a", .8),
            ), SafetyFacts(),
        )
        synthesizer = PrimaryPlanSynthesizer()
        first = synthesizer.synthesize(bundle(), safety, tuple(reversed(facts())), timezone="America/Los_Angeles")
        second = synthesizer.synthesize(bundle(), safety, facts(), timezone="America/Los_Angeles")
        self.assertEqual(first, second)
        self.assertEqual(first.semantic_hash, second.semantic_hash)

    def test_safety_disposition_dominates_probability_and_is_explained(self):
        safety = SafetyPolicy().apply(
            (
                ProbabilisticRecommendation("candidate-a", .8, substances=("allergen",)),
                ProbabilisticRecommendation("candidate-b", .2),
            ), SafetyFacts(allergies=("allergen",)),
        )
        plan = PrimaryPlanSynthesizer().synthesize(
            bundle(), safety, facts(), timezone="America/Los_Angeles"
        )
        self.assertEqual(plan.pharmacotherapy.value["medicationCode"], "synthetic-candidate-b")
        limitation = next(item for item in plan.limitations if item.code == "excluded-candidate-a")
        self.assertTrue(any("candidate-allergy" in link.reference for link in limitation.evidence_links))

    def test_unmapped_candidates_incomplete_models_and_emergency_fail_closed(self):
        normal = SafetyPolicy().apply(
            (ProbabilisticRecommendation("candidate-a", 1.0),), SafetyFacts()
        )
        with self.assertRaisesRegex(SynthesisBlocked, "outside the synthesis policy"):
            PrimaryPlanSynthesizer().synthesize(
                bundle(meds=(("unconstrained-drug-and-dose", 1.0),)), normal, facts(),
                timezone="America/Los_Angeles",
            )

        incomplete = BnEvaluationBundle("snapshot-12", "1.0.0", (), (), ())
        with self.assertRaisesRegex(SynthesisBlocked, "complete"):
            PrimaryPlanSynthesizer().synthesize(
                incomplete, normal, facts(), timezone="America/Los_Angeles"
            )

        emergency = SafetyPolicy().apply(
            (ProbabilisticRecommendation("candidate-a", 1.0),),
            SafetyFacts(suicide_risk="imminent"),
        )
        with self.assertRaisesRegex(SynthesisBlocked, "emergency escalation"):
            PrimaryPlanSynthesizer().synthesize(
                bundle(meds=(("candidate-a", 1.0),)), emergency, facts(),
                timezone="America/Los_Angeles",
            )


if __name__ == "__main__":
    unittest.main()

