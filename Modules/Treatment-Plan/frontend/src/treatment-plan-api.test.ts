import { describe, expect, it, vi } from "vitest";
import { finalizePlan, loadCsrfToken, loadReview, planIdFromPath, requestAssistantAdvisory, submitDraftEdits, supersedePlan, type FollowUpDelta } from "./treatment-plan-api";

const planId = "00000000-0000-4000-8000-000000000051";
const planView = {
  primaryPlan: {
    schemaVersion: "1.0.0", planId,
    runId: "00000000-0000-4000-8000-000000000052",
    encounterId: "00000000-0000-4000-8000-000000000053",
    createdAt: "2026-07-31T01:00:00Z",
    rationale: ["Source-backed rationale"],
  },
  plan: {
    content: {
      setting: "outpatient",
      pharmacotherapy: [{ medicationCode: "synthetic-a", codeSystem: "synthetic", dose: "2 mg", route: "oral", frequency: "daily" }],
      nextAppointment: { interval: "P7D", timezone: "America/Los_Angeles" },
    },
    safetyFindings: [],
  },
  edits: [], version: 0,
};
const delta: FollowUpDelta = {
  schemaVersion: "1.0.0",
  deltaId: "00000000-0000-4000-8000-000000000061",
  patientId: "00000000-0000-4000-8000-000000000062",
  priorEncounterId: planView.primaryPlan.encounterId,
  encounterId: "00000000-0000-4000-8000-000000000063",
  priorFinalPlanId: "00000000-0000-4000-8000-000000000064",
  recordedAt: "2026-07-31T02:00:00Z",
  changes: [{ domain: "severity", summary: "Severity changed.", sourceResourceId: "severity-2" }],
};

describe("Treatment Plan review API", () => {
  it("accepts only a canonical path Plan UUID and never query launch context", () => {
    expect(planIdFromPath(`/modules/treatment-plan/${planId}`)).toBe(planId);
    expect(planIdFromPath("/modules/treatment-plan")).toBe("");
    expect(planIdFromPath(`/modules/treatment-plan?planId=${planId}`)).toBe("");
  });

  it("obtains CSRF only from Authentication's supported bootstrap contract", async () => {
    const fetcher = vi.fn(async () => new Response(JSON.stringify({ ok: true, csrf_token: "signed-token" }), { status: 200, headers: { "Content-Type": "application/json" } }));
    expect(await loadCsrfToken(fetcher as typeof fetch)).toBe("signed-token");
    expect(fetcher).toHaveBeenCalledWith("/api/auth/csrf", { credentials: "include" });
  });

  it("loads a credentialed plan and reports unavailable provenance as partial", async () => {
    const fetcher = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => String(input).endsWith("/provenance")
      ? new Response("service unavailable", { status: 503 })
      : new Response(JSON.stringify(planView), { status: 200, headers: { "Content-Type": "application/json", ETag: '"etag-0"' } }));

    const result = await loadReview(planId, undefined, fetcher as typeof fetch);

    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(fetcher.mock.calls[0][1]).toMatchObject({ credentials: "include" });
    expect(result.workspace.draft.medication.dose).toEqual({ amount: "2", unit: "mg" });
    expect(result.partialMessages[0]).toContain("could not be loaded");
  });

  it("carries the latest ETag through sequential structured edits", async () => {
    const seen: string[] = [];
    let sequence = 0;
    const fetcher = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      seen.push(new Headers(init?.headers).get("If-Match") ?? "");
      sequence += 1;
      return new Response(JSON.stringify(planView), { status: 200, headers: { "Content-Type": "application/json", ETag: `"etag-${sequence}"` } });
    });

    const result = await submitDraftEdits(planId, '"etag-0"', "csrf-token", [
      { operation: "replace", path: "/content/setting", after: "inpatient" },
      { operation: "replace", path: "/content/nextAppointment/interval", after: "P2D" },
    ], fetcher as typeof fetch);

    expect(seen).toEqual(['"etag-0"', '"etag-1"']);
    expect(new Headers(fetcher.mock.calls[0][1]?.headers).get("X-CSRF-Token")).toBe("csrf-token");
    expect(result.etag).toBe('"etag-2"');
  });

  it("posts the fresh Follow-up Delta and maps all server-derived section reasons", async () => {
    const successorView = {
      ...planView,
      primaryPlan: { ...planView.primaryPlan, planId: "00000000-0000-4000-8000-000000000065", encounterId: delta.encounterId },
    };
    const sectionComparisons = [
      { section: "setting", status: "unchanged", reason: "Fresh severity still supports outpatient care." },
      { section: "pharmacotherapy", status: "changed", reason: "Fresh severity supports a revised dose." },
      { section: "nextAppointment", status: "unchanged", reason: "Fresh evidence supports seven days." },
    ];
    const fetcher = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => new Response(
      JSON.stringify({ planView: successorView, supersession: { sectionComparisons } }),
      { status: 201, headers: { "Content-Type": "application/json", ETag: '"successor-etag"' } },
    ));

    const result = await supersedePlan(
      planId,
      delta,
      "csrf-token",
      fetcher as typeof fetch,
      "00000000-0000-4000-8000-000000000066",
    );

    const init = fetcher.mock.calls[0][1];
    expect(init).toMatchObject({ method: "POST", credentials: "include", body: JSON.stringify(delta) });
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("csrf-token");
    expect(new Headers(init?.headers).get("Idempotency-Key")).toBe(`supersede-${delta.deltaId}`);
    expect(result.successorPlanId).toBe(successorView.primaryPlan.planId);
    expect(result.comparisons).toEqual(sectionComparisons);
  });

  it("requests a credentialed read-only assistant advisory without mutation headers", async () => {
    const fetcher = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => new Response(JSON.stringify({
      schemaVersion: "1.0.0",
      status: "available",
      label: "Advisory assistant. Psychiatrist review required.",
      advisory: "Review the open safety findings before making a clinical decision.",
    }), { status: 200, headers: { "Content-Type": "application/json" } }));

    const result = await requestAssistantAdvisory(planId, "Summarize safety.", fetcher as typeof fetch);

    const init = fetcher.mock.calls[0][1];
    expect(fetcher.mock.calls[0][0]).toBe("/api/treatment-plan/v1/assistant/advisory");
    expect(init).toMatchObject({ method: "POST", credentials: "include" });
    expect(new Headers(init?.headers).has("X-CSRF-Token")).toBe(false);
    expect(init?.body).toBe(JSON.stringify({ planId, prompt: "Summarize safety." }));
    expect(result.advisory).toContain("clinical decision");
  });

  it("finalizes with ETag, CSRF, idempotency, request ID, and attestation", async () => {
    const fetcher = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => new Response(JSON.stringify({ status: "finalized" }), { status: 201, headers: { "Content-Type": "application/json" } }));
    await finalizePlan(planId, '"etag-0"', "signed-token", " I attest to this reviewed plan. ", "finalize-key-00000001", fetcher as typeof fetch, "00000000-0000-4000-8000-000000000073");
    const [url, init] = fetcher.mock.calls[0];
    const headers = new Headers(init?.headers);
    expect(url).toBe(`/api/treatment-plan/v1/plans/${planId}/finalize`);
    expect(init).toMatchObject({ method: "POST", credentials: "include", body: JSON.stringify({ attestation: "I attest to this reviewed plan." }) });
    expect(headers.get("If-Match")).toBe('"etag-0"');
    expect(headers.get("X-CSRF-Token")).toBe("signed-token");
    expect(headers.get("Idempotency-Key")).toBe("finalize-key-00000001");
    expect(headers.get("X-Request-ID")).toBe("00000000-0000-4000-8000-000000000073");
  });
});
