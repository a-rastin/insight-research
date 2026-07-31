import { describe, expect, it } from "vitest";
import {
  createReviewWorkspace,
  updateReviewField,
  type ReviewCase,
} from "./review-workspace";

const reviewCase: ReviewCase = {
  patient: {
    displayId: "Synthetic patient PT-2048",
    ageBand: "Adult",
    encounterLabel: "Medication review · 14 Jul 2026",
  },
  dataWarnings: [],
  recommendation: {
    setting: "Outpatient",
    medication: {
      code: "RXCUI-0001",
      codeSystem: "rxnorm",
      dose: { amount: "2", unit: "mg" },
      route: "Oral",
      frequency: "Once daily",
    },
    followUp: { amount: "7", unit: "days" },
  },
  rationale: [],
  alternatives: [],
  safetyFindings: [
    { id: "risk-1", level: "urgent", title: "Immediate safety review", detail: "Escalation remains required." },
  ],
  provenance: [{ label: "Plan schema", value: "1.0.0" }],
};

describe("psychiatrist review workspace", () => {
  it("keeps the recommendation and urgent findings visible after a structured dose edit", () => {
    const initial = createReviewWorkspace(reviewCase);
    const edited = updateReviewField(initial, "medication.dose.amount", "4");

    expect(edited.recommended.medication.dose).toEqual({ amount: "2", unit: "mg" });
    expect(edited.draft.medication.dose).toEqual({ amount: "4", unit: "mg" });
    expect(edited.comparisons["medication.dose.amount"]).toEqual({
      recommended: "2",
      edited: "4",
      changed: true,
    });
    expect(edited.urgentFindings).toHaveLength(1);
  });
});
