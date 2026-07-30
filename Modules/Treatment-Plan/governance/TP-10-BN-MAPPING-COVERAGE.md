# TP-10 BN evidence mapping coverage

Mapping version: `1.0.0`
Fixture status: **synthetic candidate; BN-owner and clinical-owner approval pending**

The mapper consumes only normalized snapshot facts. It never derives a clinical state from free text, scores, medication names, or missing data. A missing fact is omitted from evidence and listed in runtime coverage. A present value outside the table is also omitted and creates a typed `unsupported-evidence-state` finding.

| Model ID | Evidence nodes | Normalized facts | Mapped states |
|---|---:|---|---:|
| `treatment-setting` | 5 | symptom severity; suicide risk; violence risk; self-care capacity; community support | 20 |
| `pharmacotherapy` | 4 | treatment resistance; medication adherence; prior antipsychotic response; metabolic risk | 12 |
| `involuntary-treatment-considerations` | 5 | suicide risk; violence risk; self-care capacity; decision-making capacity; accepts voluntary treatment | 18 |
| `clozapine-suicide-risk` | 4 | treatment resistance; suicide risk; prior suicide attempt; clozapine contraindication | 12 |

Runtime `MappingCoverage` reports `expected`, `mapped`, `missing_facts`, `unsupported_facts`, and `ratio` for each model. The synthetic full-coverage fixture maps 18/18 model evidence nodes; shared normalized facts intentionally map independently into each stable model vocabulary.

## Verification and approval gate

- Automated mapping, omission, response-validation, REST-adapter, and persistence checks: `tests/test_tp10_bn_evaluation.py`.
- Synthetic full-coverage candidate: `tests/fixtures/tp10_bn_golden.json`.
- Required controlled evidence before acceptance: BN owner approval of model IDs/node/state spellings and clinical owner approval that each normalized fact maps without changing meaning.

No approval names, dates, or evidence references were present when TP-10 was implemented. This artifact therefore records coverage but does not claim clinical validation or release readiness.
