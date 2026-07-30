# Graph Report - DDI-Checker-1.2.0  (2026-07-13)

## Corpus Check
- 48 files · ~5,555,558 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 240 nodes · 371 edges · 36 communities (16 shown, 20 thin omitted)
- Extraction: 94% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 20 edges (avg confidence: 0.7)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e25ecd73`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- UI & Audit Actions
- Ingestion Pipeline
- DDI Engine
- Shared Report Parser
- Package Metadata
- Architecture & Safety
- Browser Interface
- KB Persistence
- KB Validation
- Clinical Safety Docs
- DDI Engine Tests
- UI Source Tests
- Revision Identity
- Compact Report Fixture
- Long-form Report Fixture
- Malformed Report Fixture
- Architecture Analysis Tool
- Tour Analysis Tool
- Active Knowledge Base
- Canonical Active KB JSON
- Audit Override Rationale Invariant
- Browser Application
- DDI Engine
- Environment-Neutral Report Parser
- Fail-Closed Identity Resolution
- Ingestion CLI
- Version-Aware KB Persistence
- Validation CLI
- Clinical Alert Safety
- DailyMed
- Local KB Revision Rebase
- openFDA Drug Labeling API
- Reproducible KB Identity
- NLM RxNorm API
- Shared Report Parser

## God Nodes (most connected - your core abstractions)
1. `validateKnowledgeBase()` - 12 edges
2. `buildIndex()` - 10 edges
3. `parseReport()` - 10 edges
4. `persistKb()` - 9 edges
5. `checkInteractions()` - 9 edges
6. `Drug-Drug Interaction Checker` - 9 edges
7. `readJson()` - 8 edges
8. `checkNow()` - 8 edges
9. `renderReviewList()` - 8 edges
10. `uploadReports()` - 8 edges

## Surprising Connections (you probably didn't know these)
- `buildIndex()` --indirect_call--> `label()`  [INFERRED]
  src/ddi-engine.js → scripts/validate-kb.mjs
- `assignMedicationInstanceIds()` --indirect_call--> `fingerprint()`  [INFERRED]
  src/ddi-engine.js → scripts/validate-kb.mjs
- `checkInteractions()` --indirect_call--> `record()`  [INFERRED]
  src/ddi-engine.js → test/kb-persistence.test.mjs
- `checkNow()` --indirect_call--> `kb()`  [INFERRED]
  src/app.js → test/kb-persistence.test.mjs
- `saveReview()` --indirect_call--> `kb()`  [INFERRED]
  src/app.js → test/kb-persistence.test.mjs

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Three Domain Logic Entry Points** — graphs_architecture_browser_app, graphs_architecture_ingestion_cli, graphs_architecture_validation_cli [EXTRACTED 1.00]
- **Primary Module Views** — index_checker_view, index_admin_review_workspace, index_audit_log_view [EXTRACTED 1.00]

## Communities (36 total, 20 thin omitted)

### Community 0 - "UI & Audit Actions"
Cohesion: 0.12
Nodes (38): activateRevision(), addDrugToKb(), addInteraction(), checkNow(), clearStorageFailure(), currentResultsExport(), escapeHtml(), exportAudit() (+30 more)

### Community 1 - "Ingestion Pipeline"
Cohesion: 0.11
Nodes (25): addDoseSuggestions(), buildKnowledgeBase(), cleanLine(), compareRelativePaths(), createInteraction(), createRevisionId(), __dirname, drugIdFor() (+17 more)

### Community 2 - "DDI Engine"
Cohesion: 0.15
Nodes (24): addDoseSuggestions(), addIdentityCandidate(), assignMedicationInstanceIds(), buildIndex(), checkInteractions(), cleanReportLine(), createEmptyIndex(), createParsedInteraction() (+16 more)

### Community 3 - "Shared Report Parser"
Cohesion: 0.19
Nodes (14): CONFIDENCE, fingerprint(), here, label(), object(), pair(), REQUIRED, runCli() (+6 more)

### Community 4 - "Package Metadata"
Cohesion: 0.12
Nodes (16): description, keywords, license, name, private, scripts, ingest, test (+8 more)

### Community 6 - "Browser Interface"
Cohesion: 0.20
Nodes (10): Active KB Script, Admin Review Workspace, Application Controller Script, Audit Log View, Checker View, DDI Engine Script, Drug-Drug Interaction Checker UI, KB Persistence Script (+2 more)

### Community 7 - "KB Persistence"
Cohesion: 0.31
Nodes (16): cleanLine(), collectSections(), extractDoseSuggestions(), extractListDrugs(), inferMechanism(), inferMonitoring(), inferRecommendation(), isNoiseLine() (+8 more)

### Community 8 - "KB Validation"
Cohesion: 0.18
Nodes (10): Browser storage failure behavior, Drug-Drug Interaction Checker, Knowledge-base validation, Local KB upgrades and conflicts, Medication Identity Resolution, Module Shape, Production Notes, Run (+2 more)

### Community 9 - "Clinical Safety Docs"
Cohesion: 0.20
Nodes (9): 1. Module dependency & layering, 2. Runtime data-flow (the four layers described in the README), DDI-Checker 1.1.0 — Architecture & Data Flow, KB validation gate, Key relationships the diagrams capture, Knowledge-base revision identity, Potential follow-ups worth a look, Storage boundary (+1 more)

### Community 10 - "DDI Engine Tests"
Cohesion: 0.36
Nodes (7): createRevision(), rebase(), reviewChanges(), revisionFromLegacy(), persistence, record(), require

### Community 11 - "UI Source Tests"
Cohesion: 0.32
Nodes (4): browserStorageAdapter(), memoryStorageAdapter(), { browserStorageAdapter, memoryStorageAdapter }, require

### Community 13 - "Compact Report Fixture"
Cohesion: 0.67
Nodes (3): Sedative CNS Depressants, Lefamulin, Quetiapine

### Community 14 - "Long-form Report Fixture"
Cohesion: 0.67
Nodes (3): Amitriptyline, Fluoxetine, Pimozide

### Community 15 - "Malformed Report Fixture"
Cohesion: 0.67
Nodes (3): Invalid Drug Heading Candidate, Mysterydrug, Validdrug

### Community 16 - "Architecture Analysis Tool"
Cohesion: 0.50
Nodes (3): __dirname, __filename, projectRoot

## Ambiguous Edges - Review These
- `Mysterydrug` → `Invalid Drug Heading Candidate`  [AMBIGUOUS]
  test/fixtures/reports/malformed.txt · relation: conceptually_related_to

## Knowledge Gaps
- **87 isolated node(s):** `fs`, `fs`, `path`, `name`, `version` (+82 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **20 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `Mysterydrug` and `Invalid Drug Heading Candidate`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `checkInteractions()` connect `DDI Engine` to `DDI Engine Tests`?**
  _High betweenness centrality (0.170) - this node is a cross-community bridge._
- **Why does `record()` connect `DDI Engine Tests` to `DDI Engine`?**
  _High betweenness centrality (0.168) - this node is a cross-community bridge._
- **Why does `kb()` connect `UI & Audit Actions` to `DDI Engine Tests`?**
  _High betweenness centrality (0.150) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `checkInteractions()` (e.g. with `toMedication()` and `record()`) actually correct?**
  _`checkInteractions()` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `fs`, `fs`, `path` to the rest of the system?**
  _87 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `UI & Audit Actions` be split into smaller, more focused modules?**
  _Cohesion score 0.11846689895470383 - nodes in this community are weakly interconnected._