// @vitest-environment jsdom
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const planView = {
  primaryPlan: {
    schemaVersion: "1.0.0",
    planId: "00000000-0000-4000-8000-000000000051",
    runId: "00000000-0000-4000-8000-000000000052",
    encounterId: "00000000-0000-4000-8000-000000000053",
    createdAt: "2026-07-31T01:00:00Z",
    rationale: ["Outpatient care retained after deterministic safety review."],
  },
  plan: {
    content: {
      setting: "outpatient",
      pharmacotherapy: [{ medicationCode: "synthetic-a", codeSystem: "synthetic", dose: "2 mg", route: "oral", frequency: "daily" }],
      nextAppointment: { interval: "P7D", timezone: "America/Los_Angeles" },
    },
    safetyFindings: [{ findingId: "risk-1", category: "urgent-risk", severity: "critical", status: "open", summary: "Urgent suicide-risk review required" }],
  },
  edits: [],
  version: 0,
};

describe("psychiatrist review screen", () => {
  beforeEach(() => {
    document.body.innerHTML = '<div id="root"></div>';
    window.__INSIGHT_TREATMENT_PLAN__ = { planId: planView.primaryPlan.planId, csrfToken: "csrf-token" };
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/provenance")) return new Response("[]", { status: 200, headers: { "Content-Type": "application/json" } });
      return new Response(JSON.stringify(planView), { status: 200, headers: { "Content-Type": "application/json", ETag: '"etag-0"' } });
    }));
  });

  it("loads the authenticated plan and keeps urgent findings visible during a structured edit", async () => {
    await import("./main");

    const alert = await screen.findByRole("alert", { name: "Urgent suicide-risk review required" });
    expect(alert.textContent).toContain("action not recorded");
    expect(screen.getByText("Finalization provenance is not available for this draft plan.")).toBeTruthy();

    const dose = screen.getByRole("group", { name: "Dose" });
    const amount = within(dose).getByRole("spinbutton", { name: "Amount" });
    const user = userEvent.setup();
    await user.clear(amount);
    await user.type(amount, "4");

    expect(screen.getByText("Edited")).toBeTruthy();
    expect(screen.getByLabelText("Recommended value: 2")).toBeTruthy();
    expect(screen.getByRole("alert", { name: "Urgent suicide-risk review required" }).textContent).toContain("Urgent suicide-risk review required");
  });
});
