import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { structuredEdits, updateReviewField, type ReviewField, type ReviewWorkspace } from "./review-workspace";
import {
  loadReview,
  requestAssistantAdvisory,
  submitDraftEdits,
  supersedePlan,
  type FollowUpDelta,
  type SupersessionComparison,
} from "./treatment-plan-api";
import "./styles.css";

declare global {
  interface Window {
    __INSIGHT_TREATMENT_PLAN__?: { planId?: string; csrfToken?: string; followUpDelta?: FollowUpDelta };
  }
}

type LoadState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; workspace: ReviewWorkspace; etag: string | null; partialMessages: string[] };

type AssistantState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ready"; label: string; advisory: string }
  | { kind: "unavailable"; message: string };

function configuredContext() {
  const root = document.getElementById("root");
  return {
    planId: window.__INSIGHT_TREATMENT_PLAN__?.planId ?? root?.dataset.planId ?? "",
    csrfToken: window.__INSIGHT_TREATMENT_PLAN__?.csrfToken ?? document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content ?? "",
    followUpDelta: window.__INSIGHT_TREATMENT_PLAN__?.followUpDelta,
  };
}

function ComparisonField({ workspace, field, label, children }: { workspace: ReviewWorkspace; field: ReviewField; label: string; children: React.ReactNode }) {
  const comparison = workspace.comparisons[field];
  return <div className={`comparison-field${comparison.changed ? " is-changed" : ""}`}>
    <div className="field-heading"><label htmlFor={field}>{label}</label>{comparison.changed && <span className="changed-badge"><span aria-hidden="true">↺</span> Edited</span>}</div>
    {children}
    <p className="recommended-value"><span>Recommended</span><span className="old-value" aria-label={`Recommended value: ${comparison.recommended}`}>{comparison.recommended}</span></p>
  </div>;
}

function LoadingScreen() {
  return <main className="workspace-shell" aria-busy="true" aria-live="polite">
    <p className="eyebrow">Authenticated plan read</p><h1>Loading treatment plan</h1>
    <div className="loading-grid" aria-hidden="true"><span /><span /><span /></div>
  </main>;
}

function ErrorScreen({ message, retry }: { message: string; retry: () => void }) {
  return <main className="workspace-shell"><section className="state-card error-state" role="alert">
    <p className="status-kicker">Plan unavailable</p><h1>Treatment plan could not be loaded</h1><p>{message}</p>
    <button className="primary-button" type="button" onClick={retry}>Retry authenticated read</button>
  </section></main>;
}

export function App() {
  const context = configuredContext();
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [statusMessage, setStatusMessage] = useState("Draft review in progress.");
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [activePlanId, setActivePlanId] = useState(context.planId);
  const [superseding, setSuperseding] = useState(false);
  const [supersessionComparisons, setSupersessionComparisons] = useState<SupersessionComparison[]>([]);
  const [assistantPrompt, setAssistantPrompt] = useState("");
  const [assistantState, setAssistantState] = useState<AssistantState>({ kind: "idle" });

  useEffect(() => {
    const controller = new AbortController();
    if (!context.planId) {
      setState({ kind: "error", message: "The host did not provide a Treatment Plan UUID." });
      return () => controller.abort();
    }
    setState({ kind: "loading" });
    loadReview(context.planId, controller.signal).then(
      (loaded) => setState({ kind: "ready", ...loaded }),
      (error: unknown) => {
        if (!controller.signal.aborted) setState({ kind: "error", message: error instanceof Error ? error.message : "The authenticated plan read failed." });
      },
    );
    return () => controller.abort();
  }, [attempt, context.planId]);

  if (state.kind === "loading") return <LoadingScreen />;
  if (state.kind === "error") return <ErrorScreen message={state.message} retry={() => setAttempt((value) => value + 1)} />;

  const workspace = state.workspace;
  const modifiedCount = Object.values(workspace.comparisons).filter((comparison) => comparison.changed).length;
  const urgentFinding = workspace.urgentFindings[0];
  const edit = (field: ReviewField, value: string) => {
    setState((current) => current.kind === "ready" ? { ...current, workspace: updateReviewField(current.workspace, field, value) } : current);
    setStatusMessage("Unsaved structured edits. Safety findings remain open.");
  };
  const reset = () => {
    setState((current) => current.kind === "ready" ? { ...current, workspace: { ...current.workspace, draft: current.workspace.recommended, comparisons: Object.fromEntries(Object.entries(current.workspace.comparisons).map(([field, comparison]) => [field, { ...comparison, edited: comparison.recommended, changed: false }])) as ReviewWorkspace["comparisons"] } } : current);
    setReason("");
    setStatusMessage("All fields restored to the server recommendation.");
  };
  const save = async () => {
    if (!state.etag || !context.csrfToken) return;
    setSaving(true);
    setStatusMessage("Saving structured edits with concurrency protection.");
    try {
      const updated = await submitDraftEdits(activePlanId, state.etag, context.csrfToken, structuredEdits(workspace, reason));
      setState({ kind: "ready", ...updated });
      setReason("");
      setStatusMessage("Structured edits saved. The server returned a new ETag.");
    } catch (error) {
      setStatusMessage(error instanceof Error ? `Edits were not saved: ${error.message}` : "Edits were not saved.");
    } finally {
      setSaving(false);
    }
  };
  const supersede = async () => {
    if (!context.followUpDelta || !context.csrfToken) return;
    setSuperseding(true);
    setStatusMessage("Gathering fresh follow-up snapshots and revalidating each plan section.");
    try {
      const successor = await supersedePlan(activePlanId, context.followUpDelta, context.csrfToken);
      setActivePlanId(successor.successorPlanId);
      setSupersessionComparisons(successor.comparisons);
      setState({ kind: "ready", workspace: successor.workspace, etag: successor.etag, partialMessages: successor.partialMessages });
      setStatusMessage("Successor workflow created. The prior Final Plan remains unchanged.");
    } catch (error) {
      setStatusMessage(error instanceof Error ? `Successor was not created: ${error.message}` : "Successor was not created.");
    } finally {
      setSuperseding(false);
    }
  };
  const editingBlocked = !state.etag || !context.csrfToken;
  const requestAdvisory = async () => {
    if (!assistantPrompt.trim()) return;
    setAssistantState({ kind: "loading" });
    try {
      const result = await requestAssistantAdvisory(activePlanId, assistantPrompt);
      setAssistantState({ kind: "ready", ...result });
    } catch (error) {
      setAssistantState({
        kind: "unavailable",
        message: error instanceof Error ? error.message : "Assistant provider is unavailable.",
      });
    }
  };

  return <>
    <a className="skip-link" href="#review-form">Skip to structured plan editor</a>
    <header className="app-header">
      <div className="brand-lockup"><img src="./insight-logo.png" alt="INSIGHT" /><span>Treatment Plan</span></div>
      <div className="header-meta"><span className="environment-badge"><span aria-hidden="true">ℹ</span> Research candidate</span><span>Psychiatrist review</span></div>
    </header>

    {urgentFinding && <div className="urgent-banner" role="alert" aria-labelledby="urgent-title">
      <div className="status-icon" aria-hidden="true">!</div>
      <div><p className="status-kicker">Urgent · action not recorded</p><h1 id="urgent-title">{urgentFinding.title}</h1><p>{urgentFinding.detail}</p></div>
      <a href="#safety-findings">Review safety findings</a>
    </div>}

    <main className="workspace-shell">
      {state.partialMessages.length > 0 && <section className="partial-state" role="status" aria-labelledby="partial-title"><p className="status-kicker">Partial plan context</p><h2 id="partial-title">Some review context is unavailable</h2><ul>{state.partialMessages.map((message) => <li key={message}>{message}</li>)}</ul></section>}
      {editingBlocked && <section className="partial-state" role="alert"><strong>Editing unavailable.</strong> {!state.etag ? "A current ETag is required. " : ""}{!context.csrfToken ? "The host must provide a CSRF token." : ""}</section>}
      <section className="patient-strip" aria-labelledby="patient-context-title">
        <div><p className="eyebrow">Plan context</p><h2 id="patient-context-title">{workspace.patient.displayId}</h2></div>
        <dl><div><dt>Age band</dt><dd>{workspace.patient.ageBand}</dd></div><div><dt>Encounter</dt><dd>{workspace.patient.encounterLabel}</dd></div><div><dt>Draft status</dt><dd><span className="status-text"><span aria-hidden="true">●</span> Editing</span></dd></div></dl>
      </section>

      {context.followUpDelta && <section className="follow-up-card" aria-labelledby="follow-up-title">
        <div><p className="eyebrow">Follow-up supersession</p><h2 id="follow-up-title">Create a new plan without altering the prior Final Plan</h2><p>The server validates the fresh Follow-up Delta, gathers current owner snapshots, and revalidates every supported plan section.</p></div>
        {supersessionComparisons.length === 0 ? <button className="primary-button" type="button" onClick={supersede} disabled={superseding || !context.csrfToken}>{superseding ? "Creating successor" : "Create successor workflow"}</button> : <div className="supersession-result" role="status" aria-live="polite"><p><strong>Successor workflow created.</strong> Prior finalized content was preserved.</p><dl>{supersessionComparisons.map((comparison) => <div key={comparison.section}><dt>{comparison.section === "nextAppointment" ? "Next appointment" : comparison.section}</dt><dd><span className={`comparison-status ${comparison.status}`}>{comparison.status === "changed" ? "Changed" : "Unchanged"}</span><span>{comparison.reason}</span></dd></div>)}</dl></div>}
      </section>}

      <div className="content-grid">
        <aside aria-label="Review context">
          <section className="context-card warning-card" aria-labelledby="input-warnings-title"><div className="section-title-row"><span className="section-icon warning-icon" aria-hidden="true">!</span><div><p className="eyebrow">Input quality</p><h2 id="input-warnings-title">{workspace.dataWarnings.length ? "Needs attention" : "No data-quality finding supplied"}</h2></div></div>{workspace.dataWarnings.length > 0 && <ul className="finding-list">{workspace.dataWarnings.map((warning) => <li key={warning.id}><strong>{warning.title}</strong><span>{warning.detail}</span></li>)}</ul>}</section>
          <section className="context-card" aria-labelledby="rationale-title"><p className="eyebrow">Explainability</p><h2 id="rationale-title">Why this plan</h2>{workspace.rationale.length ? <ol className="rationale-list">{workspace.rationale.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ol> : <p>No rationale was included in the plan response.</p>}</section>
          <section className="context-card" aria-labelledby="versions-title"><p className="eyebrow">Provenance</p><h2 id="versions-title">Recorded sources and versions</h2><dl className="version-list">{workspace.provenance.map((entry) => <div key={`${entry.label}-${entry.value}`}><dt>{entry.label}</dt><dd>{entry.value}</dd></div>)}</dl></section>
        </aside>

        <div className="review-column">
          <form id="review-form" className="editor-card" onSubmit={(event) => event.preventDefault()}>
            <div className="editor-header"><div><p className="eyebrow">Structured editor</p><h2>Recommended plan</h2><p>Edited values are labelled and remain paired with the immutable recommendation.</p></div><div className="edit-count" aria-live="polite"><strong>{modifiedCount}</strong><span>fields edited</span></div></div>
            <fieldset><legend>Treatment setting</legend><ComparisonField workspace={workspace} field="setting" label="Care setting"><select id="setting" value={workspace.draft.setting} onChange={(event) => edit("setting", event.target.value)} disabled={editingBlocked}><option value="outpatient">Outpatient</option><option value="inpatient">Inpatient</option><option value="emergency">Emergency</option></select></ComparisonField></fieldset>
            <fieldset><legend>Pharmacotherapy</legend><ComparisonField workspace={workspace} field="medication.code" label={`Medication code (${workspace.draft.medication.codeSystem})`}><input id="medication.code" value={workspace.draft.medication.code} onChange={(event) => edit("medication.code", event.target.value)} autoComplete="off" disabled={editingBlocked} /></ComparisonField><div className="dose-group" role="group" aria-labelledby="dose-label"><span id="dose-label" className="group-label">Dose</span><div className="two-column-fields"><ComparisonField workspace={workspace} field="medication.dose.amount" label="Amount"><input id="medication.dose.amount" type="number" inputMode="decimal" min="0" step="0.5" value={workspace.draft.medication.dose.amount} onChange={(event) => edit("medication.dose.amount", event.target.value)} disabled={editingBlocked} /></ComparisonField><ComparisonField workspace={workspace} field="medication.dose.unit" label="Unit"><input id="medication.dose.unit" value={workspace.draft.medication.dose.unit} onChange={(event) => edit("medication.dose.unit", event.target.value)} disabled={editingBlocked} /></ComparisonField></div></div><div className="two-column-fields"><ComparisonField workspace={workspace} field="medication.route" label="Route"><input id="medication.route" value={workspace.draft.medication.route} onChange={(event) => edit("medication.route", event.target.value)} disabled={editingBlocked} /></ComparisonField><ComparisonField workspace={workspace} field="medication.frequency" label="Frequency"><input id="medication.frequency" value={workspace.draft.medication.frequency} onChange={(event) => edit("medication.frequency", event.target.value)} disabled={editingBlocked} /></ComparisonField></div></fieldset>
            <fieldset><legend>Next appointment</legend><div className="two-column-fields"><ComparisonField workspace={workspace} field="followUp.amount" label="Interval"><input id="followUp.amount" type="number" inputMode="numeric" min="1" step="1" value={workspace.draft.followUp.amount} onChange={(event) => edit("followUp.amount", event.target.value)} disabled={editingBlocked} /></ComparisonField><ComparisonField workspace={workspace} field="followUp.unit" label="Unit"><select id="followUp.unit" value={workspace.draft.followUp.unit} onChange={(event) => edit("followUp.unit", event.target.value)} disabled={editingBlocked}><option value="days">Days</option><option value="weeks">Weeks</option><option value="months">Months</option></select></ComparisonField></div></fieldset>
            <fieldset><legend>Edit rationale</legend><label htmlFor="edit-reason">Clinical rationale when required by policy</label><textarea id="edit-reason" value={reason} onChange={(event) => setReason(event.target.value)} disabled={editingBlocked} maxLength={2000} /><p className="field-help">The server determines whether a rationale is mandatory and preserves it in the append-only edit ledger.</p></fieldset>
            <div className="editor-actions"><p className="sr-status" role="status" aria-live="polite">{statusMessage}</p><button className="secondary-button" type="button" onClick={reset} disabled={modifiedCount === 0 || saving}>Reset changes</button><button className="primary-button" type="button" onClick={save} disabled={modifiedCount === 0 || saving || editingBlocked}>{saving ? "Saving edits" : "Save structured edits"}</button></div>
          </form>

          <section className="support-card" aria-labelledby="alternatives-title"><p className="eyebrow">Clinical options</p><h2 id="alternatives-title">Alternatives considered</h2><p>The current plan-read contract does not include alternatives. No alternatives have been inferred by the browser.</p></section>
          <section id="safety-findings" className="support-card" aria-labelledby="safety-title"><p className="eyebrow">Safety review</p><h2 id="safety-title">Open findings</h2>{workspace.safetyFindings.length ? <div className="safety-list">{workspace.safetyFindings.map((finding) => <article className={`safety-item ${finding.level}`} key={finding.id}><span className="section-icon" aria-hidden="true">{finding.level === "urgent" ? "!" : finding.level === "warning" ? "△" : "i"}</span><div><p className="status-kicker">{finding.level === "urgent" ? "Urgent" : finding.level === "warning" ? "Warning" : "Information"} · Open</p><h3>{finding.title}</h3><p>{finding.detail}</p></div></article>)}</div> : <p>No safety findings were included in the current plan response.</p>}</section>
        </div>

        <section className="assistant-rail" aria-labelledby="assistant-title">
          <div className="assistant-heading"><p className="eyebrow">Read-only assistant</p><h2 id="assistant-title">Plan review support</h2><span className="info-badge"><span aria-hidden="true">i</span> Advisory</span></div>
          <p>Ask about the current plan. The server sends only an identifier-omitted, scrubbed page projection. No assistant action can change this plan.</p>
          <label htmlFor="assistant-prompt">Question for the assistant</label>
          <textarea id="assistant-prompt" value={assistantPrompt} onChange={(event) => setAssistantPrompt(event.target.value)} maxLength={1000} placeholder="For example: Summarize the open safety considerations." />
          <button className="primary-button" type="button" onClick={requestAdvisory} disabled={!assistantPrompt.trim() || assistantState.kind === "loading"}>{assistantState.kind === "loading" ? "Requesting advisory" : "Request advisory"}</button>
          <p className="assistant-retention">Prompts and responses are not stored. Do not enter patient identifiers.</p>
          {assistantState.kind === "idle" && <div className="assistant-state" role="status"><strong>Ready for an optional question.</strong><span>Clinical review remains available without the assistant.</span></div>}
          {assistantState.kind === "loading" && <div className="assistant-state" role="status" aria-live="polite"><strong>Preparing scrubbed context.</strong><span>The clinical workspace remains available.</span></div>}
          {assistantState.kind === "ready" && <article className="assistant-response" aria-label="Assistant advisory"><p className="status-kicker">{assistantState.label}</p><p>{assistantState.advisory}</p></article>}
          {assistantState.kind === "unavailable" && <div className="assistant-state assistant-unavailable" role="status"><strong>Assistant unavailable.</strong><span>{assistantState.message} Clinical workflows remain available.</span></div>}
        </section>
      </div>
    </main>
  </>;
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>);
