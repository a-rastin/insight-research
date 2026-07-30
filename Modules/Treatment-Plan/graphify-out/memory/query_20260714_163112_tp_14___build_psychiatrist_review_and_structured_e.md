---
type: "query"
date: "2026-07-14T16:31:12.480574+00:00"
question: "TP-14 — Build psychiatrist review and structured editing UI"
contributor: "graphify"
outcome: "useful"
source_nodes: ["PrimaryTreatmentPlan", "PlanRecommendation", "DdiCheckResult", "PlanEdit", "react"]
---

# Q: TP-14 — Build psychiatrist review and structured editing UI

## Answer

Expanded from the request via graph vocabulary: review, editing, structured, react, recommendation, primary, plan, ddi, safety, dose, provenance, version. The graph identified PrimaryTreatmentPlan and PlanRecommendation in treatment_plan/primary_plan.py, DdiCheckResult in treatment_plan/ddi_check.py, PlanEdit in the published treatment-plan schema, and the React frontend as the minimal implementation surface. TP-14 was implemented behind a small review-workspace interface that preserves recommended values, derives comparisons, retains urgent findings, and exposes structured fields without duplicating clinical policy.

## Outcome

- Signal: useful

## Source Nodes

- PrimaryTreatmentPlan
- PlanRecommendation
- DdiCheckResult
- PlanEdit
- react