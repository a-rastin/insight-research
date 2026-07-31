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
const followUpDelta = {
  schemaVersion: "1.0.0" as const,
  deltaId: "00000000-0000-4000-8000-000000000061",
  patientId: "00000000-0000-4000-8000-000000000062",
  priorEncounterId: planView.primaryPlan.encounterId,
  encounterId: "00000000-0000-4000-8000-000000000063",
  priorFinalPlanId: "00000000-0000-4000-8000-000000000064",
  recordedAt: "2026-07-31T02:00:00Z",
  changes: [{ domain: "severity" as const, summary: "Severity changed.", sourceResourceId: "severity-2" }],
};

describe("psychiatrist review screen", () => {
  beforeEach(() => {
    document.body.innerHTML = '<div id="root"></div>';
    window.history.replaceState({}, "", `/modules/treatment-plan/${planView.primaryPlan.planId}`);
    window.__INSIGHT_TREATMENT_PLAN__ = { followUpDelta };
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/auth/csrf") return new Response(JSON.stringify({ ok: true, csrf_token: "csrf-token" }), { status: 200, headers: { "Content-Type": "application/json" } });
      if (init?.method === "POST") return new Response(JSON.stringify({
        planView: {
          ...planView,
          primaryPlan: { ...planView.primaryPlan, planId: "00000000-0000-4000-8000-000000000065", encounterId: followUpDelta.encounterId },
        },
        supersession: { sectionComparisons: [
          { section: "setting", status: "unchanged", reason: "Fresh severity still supports outpatient care." },
          { section: "pharmacotherapy", status: "changed", reason: "Fresh severity supports a revised dose." },
          { section: "nextAppointment", status: "unchanged", reason: "Fresh evidence supports seven days." },
        ] },
      }), { status: 201, headers: { "Content-Type": "application/json", ETag: '"successor-etag"' } });
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

    await user.click(screen.getByRole("button", { name: "Create successor workflow" }));
    expect(await screen.findByText("Successor workflow created.")).toBeTruthy();
    expect(screen.getByText("Fresh severity supports a revised dose.")).toBeTruthy();
    expect(screen.getByText("Changed")).toBeTruthy();
    expect(screen.getAllByText("Unchanged")).toHaveLength(2);

    await user.type(screen.getByRole("textbox", { name: "Attestation" }), "I reviewed and attest to this exact plan.");
    await user.click(screen.getByRole("button", { name: "Finalize reviewed plan" }));
    expect(await screen.findByText("Final Treatment Plan created. This finalized record is immutable.")).toBeTruthy();
    const calls = vi.mocked(fetch).mock.calls;
    const finalization = calls.find(([url]) => String(url).endsWith("/finalize"));
    expect(finalization).toBeTruthy();
    const headers = new Headers(finalization?.[1]?.headers);
    expect(headers.get("If-Match")).toBe('"successor-etag"');
    expect(headers.get("X-CSRF-Token")).toBe("csrf-token");
    expect(headers.get("Idempotency-Key")).toMatch(/^finalize-/);
    expect(headers.get("X-Request-ID")).toMatch(/^[0-9a-f-]{36}$/);
  }, 10000);
});
