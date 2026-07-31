import { createReviewWorkspace, type ReviewCase, type ReviewWorkspace } from "./review-workspace";

export type ProvenanceEntry = { label: string; value: string };
export type LoadedReview = {
  workspace: ReviewWorkspace;
  etag: string | null;
  partialMessages: string[];
};

export type DraftEdit = {
  operation: "replace";
  path: string;
  after: string;
  reason?: string;
};

export type FollowUpDelta = {
  schemaVersion: "1.0.0";
  deltaId: string;
  patientId: string;
  priorEncounterId: string;
  encounterId: string;
  priorFinalPlanId: string;
  recordedAt: string;
  changes: Array<{
    domain: "diagnosis" | "severity" | "medical-history" | "medication" | "encounter";
    summary: string;
    sourceResourceId: string;
  }>;
};

export type SupersessionComparison = {
  section: "setting" | "pharmacotherapy" | "nextAppointment";
  status: "changed" | "unchanged";
  reason: string;
};

export type SupersededReview = LoadedReview & {
  successorPlanId: string;
  comparisons: SupersessionComparison[];
};

type FetchLike = typeof fetch;
type JsonObject = Record<string, unknown>;

function object(value: unknown, label: string): JsonObject {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${label} is not an object.`);
  }
  return value as JsonObject;
}

function array(value: unknown, label: string): unknown[] {
  if (!Array.isArray(value)) throw new Error(`${label} is not an array.`);
  return value;
}

function text(value: unknown, label: string): string {
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`${label} is missing.`);
  }
  return value;
}

function splitDose(value: string): { amount: string; unit: string } {
  const match = value.match(/^([0-9]+(?:\.[0-9]+)?)\s+(.+)$/);
  if (!match) throw new Error("The plan dose cannot be represented by the structured editor.");
  return { amount: match[1], unit: match[2] };
}

function splitInterval(value: string): { amount: string; unit: string } {
  const match = value.match(/^P([1-9][0-9]*)(D|W|M)$/);
  if (!match) throw new Error("The follow-up interval cannot be represented by the structured editor.");
  return { amount: match[1], unit: ({ D: "days", W: "weeks", M: "months" } as const)[match[2] as "D" | "W" | "M"] };
}

function title(value: string): string {
  return value.replace(/[-_]/g, " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function provenanceEntries(primary: JsonObject, record: unknown): ProvenanceEntry[] {
  const entries: ProvenanceEntry[] = [
    { label: "Plan schema", value: text(primary.schemaVersion, "primaryPlan.schemaVersion") },
    { label: "Recommendation run", value: text(primary.runId, "primaryPlan.runId") },
    { label: "Generated", value: text(primary.createdAt, "primaryPlan.createdAt") },
  ];
  if (record === undefined) return entries;
  const item = object(record, "provenance record");
  if (typeof item.recordedAt === "string") entries.push({ label: "Finalization recorded", value: item.recordedAt });
  if (typeof item.actorId === "string") entries.push({ label: "Finalized by actor", value: item.actorId });
  const sources = Array.isArray(item.sources) ? item.sources : [];
  sources.forEach((source, index) => {
    const value = object(source, `provenance source ${index + 1}`);
    const owner = typeof value.sourceModule === "string" ? value.sourceModule : "source";
    const version = typeof value.schemaVersion === "string" ? ` · schema ${value.schemaVersion}` : "";
    entries.push({ label: `Source ${index + 1}`, value: `${owner}${version}` });
  });
  return entries;
}

export function mapPlanView(payload: unknown, provenance: unknown[] | undefined): ReviewCase {
  const view = object(payload, "plan response");
  const primary = object(view.primaryPlan, "primaryPlan");
  const plan = object(view.plan, "plan");
  const content = object(plan.content, "plan.content");
  const medication = object(array(content.pharmacotherapy, "plan.content.pharmacotherapy")[0], "pharmacotherapy item");
  const appointment = object(content.nextAppointment, "plan.content.nextAppointment");
  const findings = array(plan.safetyFindings, "plan.safetyFindings").map((raw, index) => {
    const finding = object(raw, `safety finding ${index + 1}`);
    const severity = text(finding.severity, `safety finding ${index + 1} severity`);
    return {
      id: text(finding.findingId, `safety finding ${index + 1} id`),
      level: severity === "critical" ? "urgent" as const : severity === "info" || severity === "low" ? "info" as const : "warning" as const,
      title: text(finding.summary, `safety finding ${index + 1} summary`),
      detail: `${title(text(finding.category, `safety finding ${index + 1} category`))} · ${title(text(finding.status, `safety finding ${index + 1} status`))}`,
      category: text(finding.category, `safety finding ${index + 1} category`),
    };
  });
  const rationale = array(primary.rationale, "primaryPlan.rationale").map((value, index) => text(value, `rationale ${index + 1}`));

  return {
    patient: {
      displayId: `Plan ${text(primary.planId, "primaryPlan.planId")}`,
      ageBand: "Not included in the Treatment Plan response",
      encounterLabel: `Encounter ${text(primary.encounterId, "primaryPlan.encounterId")}`,
    },
    dataWarnings: findings
      .filter((finding) => finding.category === "data-quality")
      .map(({ id, title: warningTitle, detail }) => ({ id, title: warningTitle, detail })),
    recommendation: {
      setting: text(content.setting, "plan.content.setting"),
      medication: {
        code: text(medication.medicationCode, "medicationCode"),
        codeSystem: text(medication.codeSystem, "codeSystem"),
        dose: splitDose(text(medication.dose, "dose")),
        route: text(medication.route, "route"),
        frequency: text(medication.frequency, "frequency"),
      },
      followUp: splitInterval(text(appointment.interval, "nextAppointment.interval")),
    },
    rationale,
    alternatives: [],
    safetyFindings: findings.map(({ category: _category, ...finding }) => finding),
    provenance: provenanceEntries(primary, provenance?.[0]),
  };
}

async function responseError(response: Response): Promise<Error> {
  let detail = `Request failed with status ${response.status}.`;
  try {
    const body = object(await response.json(), "error response");
    if (typeof body.detail === "string") detail = body.detail;
  } catch {
    // The status remains useful when an upstream error is not JSON.
  }
  return new Error(detail);
}

export async function loadReview(planId: string, signal?: AbortSignal, fetcher: FetchLike = fetch): Promise<LoadedReview> {
  const planPath = `/api/treatment-plan/v1/plans/${encodeURIComponent(planId)}`;
  const [planResult, provenanceResult] = await Promise.allSettled([
    fetcher(planPath, { credentials: "include", signal }),
    fetcher(`${planPath}/provenance`, { credentials: "include", signal }),
  ]);
  if (planResult.status === "rejected") throw planResult.reason;
  if (!planResult.value.ok) throw await responseError(planResult.value);

  const partialMessages: string[] = [];
  const etag = planResult.value.headers.get("ETag");
  if (!etag) partialMessages.push("The server did not provide an ETag. Editing is disabled to prevent lost updates.");

  let provenance: unknown[] | undefined;
  if (provenanceResult.status === "fulfilled" && provenanceResult.value.ok) {
    const value = await provenanceResult.value.json();
    provenance = array(value, "provenance response");
    if (provenance.length === 0) partialMessages.push("Finalization provenance is not available for this draft plan.");
  } else {
    partialMessages.push("Finalization provenance could not be loaded. Plan content remains available for review.");
  }

  return {
    workspace: createReviewWorkspace(mapPlanView(await planResult.value.json(), provenance)),
    etag,
    partialMessages,
  };
}

export async function submitDraftEdits(
  planId: string,
  etag: string,
  csrfToken: string,
  edits: DraftEdit[],
  fetcher: FetchLike = fetch,
): Promise<LoadedReview> {
  let currentEtag = etag;
  let lastPayload: unknown;
  for (const edit of edits) {
    const response = await fetcher(`/api/treatment-plan/v1/plans/${encodeURIComponent(planId)}/draft`, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json", "If-Match": currentEtag, "X-CSRF-Token": csrfToken },
      body: JSON.stringify(edit),
    });
    if (!response.ok) throw await responseError(response);
    const nextEtag = response.headers.get("ETag");
    if (!nextEtag) throw new Error("The edit response did not include the required ETag.");
    currentEtag = nextEtag;
    lastPayload = await response.json();
  }
  if (lastPayload === undefined) throw new Error("No structured edits were supplied.");
  return {
    workspace: createReviewWorkspace(mapPlanView(lastPayload, undefined)),
    etag: currentEtag,
    partialMessages: ["Finalization provenance is not available for this draft plan."],
  };
}

export async function supersedePlan(
  planId: string,
  delta: FollowUpDelta,
  csrfToken: string,
  fetcher: FetchLike = fetch,
  requestId: string = crypto.randomUUID(),
): Promise<SupersededReview> {
  const response = await fetcher(`/api/treatment-plan/v1/plans/${encodeURIComponent(planId)}/supersede`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": `supersede-${delta.deltaId}`,
      "X-CSRF-Token": csrfToken,
      "X-Request-ID": requestId,
    },
    body: JSON.stringify(delta),
  });
  if (!response.ok) throw await responseError(response);
  const etag = response.headers.get("ETag");
  if (!etag) throw new Error("The supersession response did not include the successor ETag.");
  const payload = object(await response.json(), "supersession response");
  const supersession = object(payload.supersession, "supersession");
  const comparisons = array(supersession.sectionComparisons, "supersession.sectionComparisons").map((raw, index) => {
    const comparison = object(raw, `section comparison ${index + 1}`);
    const section = text(comparison.section, `section comparison ${index + 1} section`);
    const status = text(comparison.status, `section comparison ${index + 1} status`);
    if (!["setting", "pharmacotherapy", "nextAppointment"].includes(section)) {
      throw new Error(`Section comparison ${index + 1} has an unsupported section.`);
    }
    if (status !== "changed" && status !== "unchanged") {
      throw new Error(`Section comparison ${index + 1} has an unsupported status.`);
    }
    return {
      section: section as SupersessionComparison["section"],
      status: status as SupersessionComparison["status"],
      reason: text(comparison.reason, `section comparison ${index + 1} reason`),
    };
  });
  if (comparisons.length !== 3 || new Set(comparisons.map((item) => item.section)).size !== 3) {
    throw new Error("The supersession response must explain all three plan sections.");
  }
  const planView = object(payload.planView, "successor plan view");
  const primaryPlan = object(planView.primaryPlan, "successor primaryPlan");
  return {
    workspace: createReviewWorkspace(mapPlanView(planView, undefined)),
    etag,
    partialMessages: ["Finalization provenance is not available for this successor draft."],
    successorPlanId: text(primaryPlan.planId, "successor primaryPlan.planId"),
    comparisons,
  };
}
