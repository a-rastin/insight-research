# Drug-Drug Interaction Checker

Standalone clinical decision support module for a versioned interaction knowledge base, deterministic pairwise checking, admin review, and audit capture.

## Published v1 contract

The production REST boundary is published under `contracts/`:

- `ddi-v1.contract.json` defines medication resolution, immutable knowledge
  revision lifecycle and rollback, clinical checks, findings, append-only
  clinical audit, override rules, roles, hashes, idempotency, and typed errors.
- `ddi-v1.schema.json` provides Draft 2020-12 schemas.
- `openapi-v1.json` publishes `POST /api/ddi/v1/checks`, aligned with the
  Treatment Plan medication-set request and response seam.

-
-
-

## Production REST seam

`deploy/ddi-static-server.mjs` preserves the standalone UI and implements the
published `POST /api/ddi/v1/checks` contract. The route requires a valid
Treatment Plan HMAC service assertion and a current authorized psychiatrist
session from Authentication. It validates exact request/schema and idempotency
headers, recomputes the canonical medication-set hash, runs the shared engine
server-side, and returns active knowledge identity and content-hash metadata.

`/readyz` returns `200` only when service authentication is configured,
Authentication is reachable, and `DDI_REGISTRY_ROOT/active-kb.json` passes
clinical-active validation with a UUID `knowledgeBaseId` and semantic `version`.
The bundled draft remains correctly not ready and is not promoted by deployment.

## Run

Open `index.html` in a browser, or serve the folder with any static server.

```powershell
cd "PATH"
npm test
npm run ingest
node scripts/validate-kb.mjs
```

`npm run ingest` reads `.txt` and `.md` reports from PATH

```text
C:\Users\User
```

Use another source folder with:

```powershell
node scripts/ingest.mjs "C:\path\to\reports"
```

## Module Shape

- Ingestion layer: parses source reports into structured records, keeps evidence excerpts and source paths, and creates `rxnorm:` identifiers where the seeded map knows the RxCUI.
- Shared report parser: `src/report-parser.js` is dependency-free and owns report cleanup, heading validation, list splitting, severity sections, dose extraction, excerpts, and inferred clinical fields. Browser upload and CLI ingestion adapt its normalized output with environment-specific identity, provenance, review status, filesystem traversal, and hashing.
- Reproducible KB identity: ingestion sorts reports by relative path and computes `version` from each relative path and exact file bytes plus the parser version, schema version, and normalization configuration. Absolute source paths and `generatedAt` metadata do not affect identity.
- Curated database: writes `data/active-kb.json` and browser-ready `data/active-kb.js` with `DrugInteraction` records.
- Runtime checker: resolves medication names, generates all medication pairs, performs deterministic lookup, and returns structured alerts sorted by severity.
- Medication-instance invariant: `checkInteractions` retains every input row as a distinct instance, including exact duplicate rows. It assigns a stable `instanceId` from normalized name/dose/route/frequency plus an occurrence suffix. Alerts are deduplicated only by interaction record and unordered medication-instance pair, so dose-, route-, formulation-, and schedule-specific rows remain represented in `patientMedications`. Alert `id` identifies that pair-specific occurrence; `interactionId` identifies the underlying knowledge-base record.
- Clinician UI: shows severity-coded alerts, recommendations, evidence, and accepted/dismissed/overridden actions.
- Admin workflow: preview parsed records, upload TXT reports, edit fields, approve/reject, add new interactions, and activate a local Interaction Knowledge Base Revision.
- Clinical alert safety: only interactions with `reviewStatus: "approved"` enter the clinical index. Rejected, pending, uploaded-pending, and missing-status records remain reviewable but cannot generate alerts. Use `{ adminPreview: true }` only for non-clinical testing.
- Activation is blocked when zero approved interactions are available.
- Audit: stores alert actions, override rationales, and KB version in browser local storage for standalone testing. Overrides require a nonblank clinical rationale (maximum 500 characters); canceling the rationale dialog or failing validation creates no audit entry. The same invariant is enforced by the shared engine.

## Medication Identity Resolution

Medication lookup is fail-closed and returns one of three outcomes:

- `resolved`: exactly one normalized canonical name or alias maps to a drug identity.
- `ambiguous`: the label maps to multiple drug IDs. Interaction checking skips that medication and returns candidate names and IDs for explicit user selection.
- `unknown`: the label maps to no active knowledge-base identity and is returned in `unresolved`.

Canonical names and aliases are normalized case-insensitively. Repeated canonical/alias labels on the same drug ID are deduplicated. The index exposes `identityCollisions`, and CLI ingestion rejects a generated knowledge base when one normalized label belongs to multiple IDs.

`resolveDrug` is the identity seam. A future RxNorm-backed adapter can populate stable drug IDs before index construction; tests can use a small in-memory knowledge base at the same seam without network access.

## Upload New Drug TXT

Open `index.html`, choose `Admin`, then use `Upload TXT report`.

The browser parses Medscape-style `.txt` or `.md` reports, inserts new drugs, dose suggestions, report metadata, and interaction records into the local knowledge base, then saves the revision in local storage. Uploaded records enter `uploaded_pending_review`; approve or edit them before activating a local revision.

Parser parity is regression-tested with the shared malformed and representative fixture corpus in `test/fixtures/reports/`. Every fixture runs through both browser and CLI adapters, and `test/report-parser-parity.test.mjs` compares their normalized drug, interaction, identity-independent clinical-field, and excerpt outputs.

## Local KB upgrades and conflicts

Browser storage contains a versioned local-revision envelope, not a copy of the bundled KB. The envelope records `baseVersion`, local-only drugs/interactions/reports, stable-ID interaction review overrides, and unresolved rebase conflicts. On every startup, `src/kb-persistence.js` starts from the current `window.DDI_ACTIVE_KB`, adds local-only records, and reapplies review fields only to bundled interaction IDs that still exist.

A new bundled version therefore contributes new records, corrections, and deletions immediately. If a locally reviewed interaction changed upstream, the current bundled content is used and the local review fields are preserved, while a `bundled_record_changed` conflict is shown in the dashboard. If it disappeared upstream, it is not resurrected and a `bundled_record_removed` conflict is retained for review. The rebased envelope is committed with one `localStorage.setItem` operation. Legacy full-KB snapshots are migrated automatically; only explicitly local `ddi-local-*` and `ddi-upload-*` interactions survive as local records.

## Session Results Export

Each browser tab session gets a code like `DDI-260705-ABC123`. The checker dashboard shows this code and exports current medications, interaction results, KB version, and session audit entries as `ddi-results-<session-code>.json`.

## Production Notes

The generated KB is marked `draft_parsed_pending_admin_review`. RxNorm identifiers with `rxnorm-pending:` require normalization review before production use.

Public maintenance sources referenced by the KB metadata:

- NLM RxNorm API: https://lhncbc.nlm.nih.gov/RxNav/APIs/RxNormAPIs.html
- DailyMed: https://dailymed.nlm.nih.gov/dailymed/
- openFDA drug labeling API: https://open.fda.gov/apis/drug/label/

## Knowledge-base validation

Run npm run validate for root/schema shape, unique IDs, unambiguous canonical names and aliases, allowed review states and reviewer provenance, parser confidence, KB revision consistency, and duplicate or conflicting unordered interaction pairs. Pass another KB path as the first argument when needed. npm run validate:clinical adds the activation gate: active production metadata, an activation timestamp, at least one approved interaction, and RxNorm-resolved identities with non-low parser confidence for every approved record.

### Browser storage failure behavior

All browser persistence now passes through `src/storage-adapter.js`. Its browser adapter returns `{ ok: true }` or a classified failure (`quota_exceeded`, `storage_unavailable`, or `corrupt_json`); the in-memory adapter supports deterministic tests. KB persistence stores only the local revision envelope described above, never the 24,124-record bundled KB. Review, activation, upload, manual-entry, and medication mutations commit only after a successful write and otherwise roll back their in-memory changes. A persistent alert remains visible after a failed or corrupt storage operation, and the UI does not report save or activation success.
