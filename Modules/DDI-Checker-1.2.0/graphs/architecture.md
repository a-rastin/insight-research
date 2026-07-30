# Knowledge-base revision identity

`scripts/ingest.mjs` creates a content-addressed revision ID. It deterministically orders source reports by portable relative path, hashes each relative path and exact file bytes, and includes the parser version, schema version, and normalization configuration. `generatedAt` remains provenance metadata and the absolute source directory is deliberately excluded, so identical clinical inputs reproduce the same revision across runs and locations.

# DDI-Checker 1.1.0 — Architecture & Data Flow

## 1. Module dependency & layering

```mermaid
graph TD
    subgraph Browser["Browser (index.html)"]
        Index["index.html"]
        AppJSSrc["src/app.js (UI controller)"]
        EngineJSSrc["src/ddi-engine.js (browser adapter + DDIEngine)"]
        ParserJSSrc["src/report-parser.js (environment-neutral parser)"]
        PersistenceJSSrc["src/kb-persistence.js (local revision rebase)"]
        ActiveKBJS["data/active-kb.js (window.DDI_ACTIVE_KB)"]
        Styles["src/styles.css"]
        LocalStorage[("localStorage/sessionStorage")]
    end

    subgraph NodeCLI["Node CLI (scripts/) "]
        Ingest["scripts/ingest.mjs"]
        Validate["scripts/validate-kb.mjs"]
    end

    subgraph Inputs["Source reports"]
        MedscapeTxt[("Medscape (.txt / .md) reports<br/>SOURCE_DIR")]
        RxNormSeed[("RXNORM_SEED map<br/>in ingest.mjs")]
    end

    subgraph Data["Generated KB"]
        ActiveKBJSON["data/active-kb.json"]
    end

    subgraph Tests["Tests (test/*.test.mjs)"]
        DdiTest["test/ddi-engine.test.mjs"]
        IngestTest["test/ingest.test.mjs"]
        UITest["test/ui-source.test.mjs"]
        PersistenceTest["test/kb-persistence.test.mjs"]
    end

    Index --> AppJSSrc
    Index --> ParserJSSrc
    Index --> EngineJSSrc
    Index --> PersistenceJSSrc
    Index --> ActiveKBJS
    Index --> Styles

    AppJSSrc -- "window.DDIEngine" --> EngineJSSrc
    AppJSSrc -- "loads bundled base" --> ActiveKBJS
    AppJSSrc -- "rebase / createRevision" --> PersistenceJSSrc
    AppJSSrc -- "persist meds, audit, reviews, local KB, session code" --> LocalStorage

    Ingest --> MedscapeTxt
    Ingest -- "normalized parse" --> ParserJSSrc
    EngineJSSrc -- "normalized parse" --> ParserJSSrc
    Ingest --> RxNormSeed
    Ingest -- "writeOutputs()" --> ActiveKBJSON
    Ingest -- "writeOutputs()" --> ActiveKBJS

    Validate -- "reads --arg path" --> ActiveKBJSON

    DdiTest -- "require(...)" --> EngineJSSrc
    IngestTest -- "import ... buildKnowledgeBase / parseReport / extractDoseSuggestions" --> Ingest
    UITest -- "reads files" --> Index
    UITest -- "reads files" --> AppJSSrc
    PersistenceTest -- "upgrade and conflict cases" --> PersistenceJSSrc
```

## 2. Runtime data-flow (the four layers described in the README)

```mermaid
graph TD
    Start([CLI: npm run ingest]) --> ReadFiles["scripts/ingest.mjs<br/>readTextFiles(SOURCE_DIR)"]
    ReadFiles --> Normalize["normalizeDrugName / slugify / drugIdFor"]
    Normalize --> Seed{"RXNORM_SEED<br/>hit?"}
    Seed -- yes --> RxnormId["rxnorm:<rxcui><br/>identityStatus=rxnorm_seeded"]
    Seed -- no --> PendingId["rxnorm-pending:<slug><br/>identityStatus=pending_rxnorm_review"]
    RxnormId --> ParseReport["CLI adapter: parseReport per file"]
    ParseReport --> SharedParser["report-parser.js<br/>normalized parse schema"]
    PendingId --> ParseReport
    ParseReport --> Infer["inferMechanism / inferRecommendation / inferMonitoring"]
    Infer --> AddDose["addDoseSuggestions<br/>(extractDoseSuggestions)"]
    AddDose --> BuildKb["buildKnowledgeBase<br/>drugs[] + interactions[] + reports[] + version"]
    BuildKb --> WriteOutputs["writeOutputs<br/>active-kb.json + active-kb.js"]
    WriteOutputs --> Done([KB generated as<br/>draft_parsed_pending_admin_review])

    OpenIndex([Open index.html]) --> LoadKb["app.js: load bundled KB + local revision"]
    LoadKb --> Rebase["kb-persistence.js: stable-ID rebase<br/>preserve reviews + surface conflicts"]
    Rebase --> AtomicPersist["atomic revision envelope write<br/>baseVersion + local changes"]
    AtomicPersist --> BuildIndex["engine.buildIndex(kb)<br/>byId / byName[] / identityCollisions / interactionsByPair / suggestions"]
    BuildIndex --> RenderHeader["renderDashboard: drugs, interactions, pending count"]
    RenderHeader --> CheckerView["Checker tab"]
    CheckerView --> AddMed["Add med -> suggestDrugs<br/>(datalist) + doseSuggestions"]
    AddMed --> Resolve{"resolveDrug<br/>resolved / ambiguous / unknown"}
    Resolve -- resolved --> Check["checkInteractions<br/>all resolved pairs"]
    Resolve -- ambiguous --> Candidates["Show candidate names + IDs<br/>no interaction pair generated"]
    Resolve -- unknown --> Unresolved["Show not found in active KB"]
    Check --> Alerts["alerts sorted by severity<br/>+ ambiguous + unresolved lists"]
    Alerts --> Actions["accept / dismiss / override<br/>recordAlertAction"]
    Actions --> OverrideGate{"override action?"}
    OverrideGate -- yes --> Rationale["required rationale dialog<br/>trimmed, 1-500 characters"]
    Rationale -- valid --> Audit["createAuditEntry validates again<br/>audit saved to localStorage"]
    Rationale -- cancel / invalid --> NoAudit["no audit entry created"]
    OverrideGate -- no --> Audit
    Alerts --> Export["exportResultsButton<br/>ddi-results-<session>.json"]
    LocalKbAction(["Admin tab actions:<br/>upload / edit / approve / reject / add / activate"]) --> Revision["activate local revision<br/>writes STORAGE_KEYS.localKb<br/>rebuilds index"]
```

## Key relationships the diagrams capture

- **Three entry points** into the same domain logic: Node CLI ingestion (`ingest.mjs`), Node CLI validation (`validate-kb.mjs`), and the browser app (`index.html` + `app.js`). Only `ddi-engine.js` (UMD) and the JSON/JS KB exports are shared between Node and the browser.
- **Fail-closed identity resolution**: `byName` stores candidate arrays, deduplicated by drug ID. `resolveDrug` returns a discriminated `resolved` / `ambiguous` / `unknown` result. `checkInteractions` only pairs resolved identities; ambiguity is rendered with candidate names and IDs.
- The KB has **two physical forms**: `data/active-kb.json` (canonical, validated by `validate-kb.mjs`) and `data/active-kb.js` (browser-ready `window.DDI_ACTIVE_KB`). Browser uploads + admin approvals sidestep the CLI and write a local revision only into browser localStorage.
- `ddi-engine.js` exposes its public surface (`buildIndex`, `resolveDrug`, `suggestDrugs`, `checkInteractions`, `createAuditEntry`, `extractDoseSuggestions`, `parseReportText`) at the UMD tail — that's the only API `src/app.js` consumes via `window.DDIEngine`.
- **Ingest vs. upload parity**: `src/report-parser.js` owns environment-neutral parsing and returns a normalized schema. `ddi-engine.js::parseReportText` adds browser upload identity/review metadata; `scripts/ingest.mjs::parseReport` adds seeded RxNorm identity, filesystem provenance, and CLI review metadata. Filesystem traversal and cryptographic revision hashing remain outside the parser.
- **One-way write from CLI → browser KB**: ingestion regenerates `active-kb.js` and `active-kb.json`; the browser local-kb revision never flows back to disk (README calls this out as a production-side migration target).

Test coverage boundaries:
- `test/ddi-engine.test.mjs` → `src/ddi-engine.js`
- `test/ingest.test.mjs` → `scripts/ingest.mjs`
- `test/ui-source.test.mjs` → `index.html` + `src/app.js` (static source assertions only, no DOM run)

## Potential follow-ups worth a look

- `test/report-parser-parity.test.mjs` runs every malformed and representative report in `test/fixtures/reports/` through both adapters and asserts their normalized drugs, interactions, clinical fields, ordering, and excerpts are identical.
- Browser-only local KB revision (localStorage) and the CLI-generated `active-kb.js` both end up as "active" with different scopes — worth a doc note if reviewers ever edit via both paths.
- `validate-kb.mjs` only validates the JSON file, not the `.js` window export; if `active-kb.js` is regenerated from `active-kb.json` they always match via `writeOutputs`, but they're still two files that can drift if someone edits one by hand.
## Version-aware local KB persistence

`src/kb-persistence.js` keeps the generated bundle immutable and stores a compact local overlay. Startup rebases the overlay by stable IDs, imports bundled additions and corrections, honors bundled deletions, preserves matching review fields, records changed/removed conflicts, and atomically replaces the saved envelope. `test/kb-persistence.test.mjs` covers new, changed, removed, conflicting-edit, and legacy full-snapshot migrations.


## KB validation gate

scripts/validate-kb.mjs validates root shape before traversal, unique IDs, normalized name/alias ownership, review provenance, parser confidence, revision consistency, and duplicate/conflicting unordered pairs. The --clinical-active mode also requires active production metadata, at least one approved record, RxNorm-resolved identities, and non-low confidence for every approved record. test/validate-kb.test.mjs covers readable malformed-root and malformed-record diagnostics plus activation eligibility.

## Storage boundary

`src/storage-adapter.js` is the browser/in-memory adapter seam. `src/app.js` owns transactional UI behavior: it snapshots mutable state, creates a delta envelope through `src/kb-persistence.js`, writes once through the adapter, and publishes rebuilt indexes/UI success only after `{ ok: true }`. Failed writes preserve the prior durable and in-memory state and surface the persistent `#storageFailure` alert.
