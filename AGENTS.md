# INSIGHT Application Building Context

Before implementing, reviewing, refactoring, or making any architectural,
clinical, security, data, API, deployment, or UI decision, read these files in
order:

1. `context/project-overview.md` — product definition, intended users,
   clinical purpose, features, scope, exclusions, and release status
2. `context/architecture.md` — module boundaries, ownership, REST contracts,
   storage model, identity model, deployment topology, and invariants
3. `context/ui-context.md` — visual system, typography, layout, interaction,
   accessibility, and component conventions
4. `context/code-standards.md` — implementation, validation, testing,
   security, documentation, and naming rules
5. `context/ai-workflow-rules.md` — development workflow, task scoping,
   evidence requirements, verification, and delivery rules
6. `context/progress-tracker.md` — current phase, completed work, known gaps,
   unresolved decisions, blockers, and next steps

Then read the relevant module-local `README`, handoff, API contract, schema, and
tests before changing that module. Do not rely on a filename, prompt, generated
artifact, prototype, or historical plan as the current source of truth when a
normative context or contract document exists.

## Source Precedence and Ambiguity

Use this precedence order:

1. Explicit requirements in the current task
2. Normative files under `context/`
3. Versioned API, schema, ownership, and governance contracts
4. Module-local implementation handoffs and tests
5. General READMEs and design notes
6. Historical prompts, prototypes, generated diagrams, migration notes, and
   duplicated model packages

## Non-Negotiable Product and Clinical Rules

- INSIGHT is a psychiatrist-facing clinical decision support system for
  schizophrenia care. It provides advisory, explainable support; it does not
  replace clinical judgment or issue autonomous diagnoses, prescriptions, or
  signed clinical orders.
- Preserve psychiatrist authority. Computed criteria, scores, probabilities,
  priorities, and recommendations must remain distinct from the clinician's
  recorded decision, edits, approval, and attestation.
- Never silently convert missing, unknown, stale, conflicting, or invalid data
  into a negative or favorable clinical finding. Surface the uncertainty and
  fail closed where safety or eligibility requires it.
- Model use requires versioning, schema validation, evidence mapping,
  reproducibility, provenance, clinical review, and the applicable release
  approvals.

## Architecture and Data Boundaries

- Keep every module independently runnable and testable. A unified Docker image
  may supervise multiple module processes, but it must not collapse them into
  one codebase, process, database, or shared persistence layer.
- All cross-module communication uses versioned internal REST APIs. Never use
  cross-module SQL, shared tables, foreign keys across module databases, direct
  filesystem access, implementation imports, or another module's private data
  directory.
- Every persisted entity has one owning module. The owner defines its canonical
  identifier, schema, validation, lifecycle, persistence, and authoritative
  REST representation.
- Use canonical `patientId` and `encounterId` UUIDs for cross-module identity.
  A patient code is a stable human-facing lookup alias, not the canonical
  identity and not a substitute for an encounter.
- Every persisted or exchanged dataset must have a versioned schema. Preserve
  exact source identifiers, schema versions, timestamps, knowledge/model
  versions, and provenance needed to reproduce a recommendation.
- Treatment Plan owns normalized input snapshots, recommendation runs, plan
  edits, final plans, findings, and supersession records—not upstream patient,
  encounter, assessment, medication, or model source records.
- A Primary Treatment Plan is an explainable system-generated draft. A Final
  Treatment Plan is created only after attributable psychiatrist review and
  server-side safety revalidation. Final plans are immutable; later plans
  supersede them instead of modifying or deleting them.

## Security, Privacy, and Audit Rules

- Do not place PHI/PII, credentials, API keys, tokens, signatures, or protected
  evidence in source control, URLs, browser storage, logs, generated fixtures, 
  screenshots, or unprotected exports.
- Other modules must verify identity through the central Authentication REST
  contract. They must not decode JWTs as authorization, read the Authentication
  database, trust request-body identity, or persist browser tokens in
  `localStorage`.
- Require authentication and role authorization on protected routes. Require
  CSRF protection on state-changing browser requests. Development bypasses and
  mock identities must be explicit, environment-gated, disabled in production,
  and covered by tests.
- Keep security audit history separate from clinical provenance. Both must be
  attributable, append-only where required, and free of unnecessary plaintext
  patient data.
- Scrub patient identifiers before an LLM call, and never send patient names 
or allow the assistant to modify clinical records directly.

## Implementation and Verification Rules

- Make the smallest coherent change that satisfies the task. Do not merge
  modules, broaden scope, replace established seams, or pay down unrelated
  deferred work without explicit approval.
- Preserve public contracts and documented invariants. A contract, identifier,
  schema, clinical rule, role, route, state name, or model-node change requires
  coordinated versioning, migration, tests, and documentation.
- Validate clinical calculations and safety rules server-side; do not trust
  client-computed totals, recommendations, eligibility, or finalization state.
- Keep liveness and readiness distinct. Readiness checks must fail safely,
  avoid leaking paths or secrets, and follow the module's documented dependency
  policy.
- Preserve standalone execution and the unified deployment path. Only the
  gateway is publicly exposed; internal module ports remain private. SQLite
  databases remain module-local, with PostgreSQL as a controlled upgrade path.
- Follow `context/ui-context.md` for all interface work. Clinical state must
  never be communicated by color alone; preserve keyboard support, semantic
  labels, sufficient contrast, minimum target sizes, and reduced-motion
  behavior.
- Run the affected module's tests plus relevant contract, integration,
  migration, security, accessibility, and clinical-safety checks. Do not claim
  success for checks that were not run or could not be completed.

## Documentation and Progress

- Update `context/progress-tracker.md` after every meaningful implementation
  change, including verification performed, unresolved risks, blockers, and the
  next concrete step.
- If implementation changes architecture, scope, ownership, a public interface,
  clinical behavior, security policy, UI conventions, or coding standards, update
  the relevant context or contract document before continuing.
- Do not fabricate missing data or silently reinterpret requirements. Record
  uncertainty explicitly and ask for clarification when it affects correctness,
  clinical safety, privacy, or system boundaries.

## Sessions preamble

- Use these 2 skills in every session: 
  \caveman & 
  \ponytail
- Every work packet is a separate commit and must follow this exact loop:
  1. Run git status --short in the affected nested repository and record pre-existing changes.
  2. Read only the named module interface, its adapter, and relevant tests.
  3. Implement only the packet; do not opportunistically refactor adjacent code.
  4. Run the focused tests, the module’s full suite, and applicable common-contract checks.
  5. Git commit changes with informative comments.

Do not make any change to the files in the "root/research/Modules" folder. Copy that file to the "root/research/insight-research/Modules" and make your changes there.
