import { describe, expect, it, vi } from "vitest";
import { loadReview, submitDraftEdits } from "./treatment-plan-api";

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

describe("Treatment Plan review API", () => {
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
});
