# TP-10 BN evidence mapping coverage

Mapping version: `1.0.0`
Fixture status: **approved research runtime**

The mapper consumes only normalized snapshot facts. It never derives a clinical
state from free text, scores, medication names, or missing data. A missing fact
is omitted from evidence and listed in runtime coverage. A present value outside
the table is also omitted and creates a typed `unsupported-evidence-state`
finding.

| Model ID | Evidence nodes | Normalized facts | Mapped states |
|---|---:|---|---:|
| `treatment-setting` | 5 | symptom severity; suicide risk; violence risk; self-care capacity; community support | 20 |
| `pharmacotherapy` | 4 | treatment resistance; medication adherence; prior antipsychotic response; metabolic risk | 12 |
| `involuntary-treatment-considerations` | 5 | suicide risk; violence risk; self-care capacity; decision-making capacity; accepts voluntary treatment | 18 |
| `clozapine-suicide-risk` | 4 | treatment resistance; suicide risk; prior suicide attempt; clozapine contraindication | 12 |

## Approval

- Approved by: insight-research-override
- Approved at: 2026-07-31T00:00:00Z
- Evidence: `treatment_plan/input_mapping.py`, `treatment_plan/bn_evaluation.py`
