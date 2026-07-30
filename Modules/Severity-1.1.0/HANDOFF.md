# HANDOFF — `severity` module

> Read this first. Everything you need to use, modify, or extend this module is below. If a section doesn't answer your question, the source file named in that section will.

## INS-027 Severity UI integration

The standalone alias lookup described in the historical sections below has been
removed. `public/severity-ui.js` now exposes bounded `mount` and `unmount`
lifecycle functions through both ES module exports and `window.InsightSeverity`.
The host supplies canonical `patientId`, `encounterId`, and an optional existing
`assessmentId`; invalid or absent context fails visibly without a clinical
request. The UI uses only gateway-relative v2 requests with cookie credentials,
CSRF, idempotent creates, and ETag updates. It renders persisted server evaluation
and scores, never stores clinical context in browser storage or URLs, and aborts
requests and removes listeners on unmount. Passed/skipped and completed states
are textually distinct. Errors are semantic urgent alerts and remain visible
until a subsequent server action succeeds. The 30 native score controls preserve
keyboard operation, 44px targets, visible focus, and reduced-motion behavior.

`test_ui.js` covers lifecycle/privacy/accessibility source contracts and drives
the UI API client through real HTTP completion, pass, load, and validation-error
paths. Treat all patient-code UI, browser-storage, browser scoring, URL mutation,
and auto-hiding notification descriptions later in this file as historical only.

## INS-026 persistence and security replacement

The legacy JSON architecture described later in this historical handoff has been
superseded. `server.js` now uses `SeverityRepository` in `repository.js` over a
module-owned SQLite database with two ordered transactional migrations, WAL,
busy-timeout handling, strong ETag updates, actor-scoped idempotency, and an
append-only attributed assessment-version ledger.

At startup, existing v1 and v2 JSON sources are parsed before import. Corrupt JSON
aborts startup and cannot appear as an empty store. Canonical v2 records are
imported once by source hash; records lacking valid assessment, Patient, or
Encounter UUIDs are retained in `legacy_quarantine`. A changed source after import
also fails closed.

All v2 assessment reads and writes revalidate Authentication through
`GET /api/auth/v2/session`, validate the v2 response and expiry, and require the
`psychiatrist` role. Writes require a signed `severity_csrf` double-submit token.
There is no authentication bypass, and production startup rejects the
development CSRF default. Credentialed CORS is restricted to exact configured
origins. `/healthz` is dependency-free; `/readyz` verifies SQLite integrity,
migration state, and Authentication reachability.

The patient-code v1 routes return
`410 SEVERITY_LEGACY_IDENTITY_UNMAPPED`; they cannot safely write a canonical
assessment. The standalone UI now uses the UUID-context v2 consumer described
above. Treat the JSON persistence, open-CORS, no-auth, and v1 route details in the
historical sections below as pre-INS-026 background only.

---

## 1. What this module is

A **standalone web app and Insight sub-module** for PANSS (Positive and Negative Syndrome Scale) schizophrenia severity assessment. Psychiatrist-facing, API-first.

- **Two roles at once:**
  1. **Standalone app** — open `http://localhost:3000`, type a patient code, run the 30-item PANSS questionnaire.
  2. **Insight sub-module** — a parent app talks to it over REST. No other integration surface. CORS is open so the parent can call it cross-origin/port.
- **Domain:** clinical decision support. PANSS = 30 items, each rated 1 (Absent) → 7 (Extreme). Subscales: Positive P1–P7 (7 items), Negative N1–N7 (7 items), General Psychopathology G1–G16 (16 items). Total raw range 30–210.
- **Design contract:** follows a sibling `DESIGN.md` (not committed here) — teal `#0A9E8F` accent, Inter body, JetBrains Mono for codes/scores, 2px teal focus rings, "clinician-control" wording (`Decision-support recommendation. Psychiatrist final review required.` — never "AI prescription").

The whole module is **deliberately minimal** (a project-wide philosophy called "ponytail" — see §10). SQLite, build tooling, and auth exist as documented deferrals, not gaps.

---

## 2. Repo layout (only 4 source files matter)

```
severity/
├── package.json           # single dep: express. "type":"module". npm start -> node server.js
├── server.js              # the entire backend: REST API + static server + CORS (149 lines)
├── test_api.js            # assert-based self-check, no test framework (91 lines)
├── data/
│   └── assessments.json   # file persistence, created on first run, starts as {}
└── public/
    └── index.html         # the entire frontend: PANSS UI, single file, no bundler (830 lines)
```

- `README.md` — user-facing overview; mirrors most of this but lighter.
- `package-lock.json`, `node_modules/` — standard.
- Everything else in `node_modules/` is transitive Express deps. **Do not touch.**

---

## 3. Stack & runtime

| Layer | Tech | Notes |
|---|---|---|
| Backend | Node.js + Express 4 | **Single dependency.** ESM (`"type":"module"`). |
| Persistence | JSON file at `data/assessments.json` | Flat object keyed by `patient_code`. No schema, no migrations, no locks. |
| Frontend | One HTML file | Tailwind via CDN (`cdn.tailwindcss.com`), Google Fonts (Inter + JetBrains Mono), vanilla JS. **Zero build step.** |
| Test | `node test_api.js` | Native `assert` + native `fetch`. No test runner, no fixtures. |

**Run:**
```powershell
npm install      # one-time
npm start        # node server.js -> http://localhost:3000
```

**Self-check:**
```powershell
node test_api.js   # starts server on PORT=4567, asserts GET/PUT flows, exits 0/1
```

**Port:** `process.env.PORT || 3000`. The test file forces `4567` so it doesn't collide with a running dev server.

---

## 4. Backend — `server.js` (149 lines, the whole thing)

Read it end-to-end before editing. It is small on purpose.

### 4.1 Boot sequence
1. Resolve `__dirname` via `fileURLToPath(import.meta.url)` (ESM has no `__dirname`).
2. Define `DATA_DIR` and `DATA_FILE` (= `<repo>/data/assessments.json`).
3. **Create `data/` dir and an empty `{}` file if missing** — so first run never crashes on read.
4. Wire middleware in this order (order matters):
   - `express.json()` — body parser
   - `express.static(public/)` — serves `index.html` at `/`
   - **CORS middleware** (manual `setHeader`, not the `cors` package) — `*` origin, methods `GET, PUT, OPTIONS`, headers `Content-Type`. Short-circuits `OPTIONS` to `200`.

### 4.2 Helpers
- `readAssessments()` — `fs.readFileSync` → `JSON.parse`. On any error, logs and returns `{}` (treats DB as empty rather than crashing the request). **This is deliberate but means a corrupted file silently wipes the view** — see §8.
- `writeAssessments(data)` — `fs.writeFileSync` pretty-printed. Returns `true`/`false`; caller turns `false` into a `500`.

> **No locking.**`fs.writeFileSync` is synchronous and atomic-ish for small files but there is **no concurrent-write protection**. Single-user localhost assumption. This is the #1 seam to upgrade if the module moves to multi-user (see §9).

### 4.3 Routes — only two exist

All routes are prefixed `/api/severity/:patient_code`. JSON in/out. There is **no list endpoint, no delete, no patch.**

#### `GET /api/severity/:patient_code`  (`server.js:60`)
- `400` if `patient_code` empty/whitespace.
- Looks up `assessments[patient_code]`.
- **If found → returns the stored object as-is.**
- **If not found → returns a fresh `pending` skeleton:**
  ```json
  {
    "patient_code": "<code>",
    "status": "pending",
    "items": {},
    "scores": { "total": 0, "positive": 0, "negative": 0, "general": 0 }
  }
  ```
  This is how the frontend bootstraps a new assessment. There is no "create" call — GET *is* the create-if-absent.

#### `PUT /api/severity/:patient_code`  (`server.js:88`)
Validates, then **overwrites** `assessments[patient_code]` (no merge, no history).
- `400` if `patient_code` empty.
- `400` if `status` missing or not in `["completed", "passed"]`.
- **If `status === "passed"`** → stores `{ patient_code, status:"passed", updated_at }`. No scores, no items.
- **If `status === "completed"`** → requires the exact 30 PANSS item codes,
  integer ratings from 1–7, and all four projected totals. The shared pure
  evaluator recomputes P/N/G/total and rejects malformed or mismatched projections.
- V1 `pending`, `passed`, and `completed` records expose `incomplete`, `passed`,
  and `completed` evaluation state plus scale/rule version metadata.
- `writeAssessments` → `200 { success: true, data: <stored> }` or `500 { error: "Failed to write to database" }`.
- `updated_at` is `new Date().toISOString()` — server-generated, not client-trusted.

#### Catch-all  (`server.js:134`)
```js
app.get("*", (req, res, next) => {
  if (req.path.startsWith("/api/")) return next();  // let unknown /api/* 404
  res.sendFile(path.join(__dirname, "public", "index.html"));
});
```
This is **only a GET catch-all** — note `app.get`, not `app.use`. It exists so the standalone SPA can support client-side routing / deep links. Unknown `/api/*` falls through to Express's default 404.

> ⚠ **There is no DELETE route.** To wipe a patient's record, edit `data/assessments.json` by hand. Do not add one unless the parent app genuinely needs it (see §9).

### 4.4 Where to make changes
- **New route?** Add it between the GET and the catch-all, or the catch-all will swallow it. Remember it's `app.get("*", ...)` so any HTTP method other than GET bypasses the catch-all automatically; for new GET routes, define them *above* line 134.
- **New field on a stored assessment?** Update both the GET skeleton (line 73) and the PUT write branch (line 102 or 117), plus the frontend consumer. There is no schema file — the schema *is* the inline object literals.
- **Validation lives inline in the route**, not in a middleware. Don't extract a validator unless you have 3+ routes.

---

## 5. Frontend — `public/index.html` (830 lines, single file)

No framework, no build. Open the file directly; everything happens in one `<script>` block at the bottom.

### 5.1 Page structure (top → bottom of body)
1. `<header>` — Insight brand, `v1.0.0-alpha` tag, active patient badge (hidden until a patient loads), hard-coded "Welcome Dr. Amiral" greeting.
2. `#notification` — toast container, hidden by default, populated by `showNotification()`.
3. `<main>` with **two mutually exclusive views** toggled via `hidden` class:
   - `#view-lookup` — patient code entry form + recent-assessments list.
   - `#view-assessment` — the actual PANSS workspace (two-column on desktop).
4. The workspace:
   - **Left column** — sticky tab bar (P / N / G) + `#items-container` where rows are injected by `renderForm()`.
   - **Right column (sticky on desktop)** — "Evaluation Context" card, progress + score totals card, real-time "Clinical Interpretation" card, and the action buttons (`Save Completed Evaluation`, `Pass`, `Dashboard`).
5. `<script>` — all logic. ~520 lines. No external JS files.

### 5.2 Constants
- `PANSS_ITEMS` (line 308) — array of 30 `{ code, scale, name, desc }` objects. **Source of truth for the questionnaire.** Order is P then N then G. If you need to add/rename an item, edit here *and* the badges / maxes are derived from `.scale` counts, so they self-update.
- `SCORE_DESCRIPTIONS` (line 346) — map `1..7` → label (`Absent`, `Minimal`, `Mild`, `Moderate`, `Moderate Severe`, `Severe`, `Extreme`). Used for tooltips and the per-row indicator.

### 5.3 State (module-scope `let`s, line 357)
- `currentPatientCode` — null until a patient loads.
- `currentTab` — `"P" | "N" | "G"`, defaults `"P"`.
- `answers` — `{ "P1": 4, "N1": 2, ... }`. **Flattened across all 30 items**, not per-tab.

There is **no state library.** Re-render is full (`renderForm()`) on every score click. It's cheap at 30 rows; do not optimize unless profiling says otherwise.

### 5.4 Key functions

| Function | Line | Job |
|---|---|---|
| `DOMContentLoaded` listener | 362 | Wires lookup form submit, loads recent list, checks `?patient_code=` / `?code=` URL param for deep-link. |
| `fetchRecentAssessments()` | 384 | Reads `localStorage["panss_recent_patients"]` (last 5). **Not** an API call — there's no list endpoint. Purely client-side memory. |
| `saveToRecentList(code)` | 415 | Pushes code to front of `localStorage` list, de-dupe, cap 5. |
| `loadPatient(code)` | 428 | `GET /api/severity/<code>`. Sets `currentPatientCode`, updates URL via `history.pushState` (no reload), seed `answers` from `data.items` if status was `completed`, swaps views, updates header badge + status badge, then `renderForm()` + `updateRealtimeCalculations()`. |
| `renderForm()` | 481 | Filters `PANSS_ITEMS` by `currentTab`, builds one row per item. Each row: code + name + desc on the left; a 1–7 button group + a textual severity indicator on the right. **Rebuilds the entire list on each call.** |
| `switchTab(scale)` | 550 | Sets `currentTab`, retoggles tab button classes, re-renders. |
| `selectScore(itemCode, score)` | 567 | Mutates `answers`, re-renders, recalculates. |
| `clearAssessmentForm()` | 576 | `confirm()`-guarded wipe of `answers` + re-render. Called by the "Reset Form" link. |
| `updateRealtimeCalculations()` | 585 | **The brains.** See 5.5. |
| `submitAssessment(statusType)` | 713 | `PUT /api/severity/<code>` with either `{status:"passed"}` or `{status:"completed", scores, items}`. On success: toast + `setTimeout(backToDashboard, 1500)`. |
| `backToDashboard()` | 772 | Resets state, strips URL params via `pushState`, swaps views back to lookup. |
| `showNotification(title, message, type)` | 795 | Toast. `type` ∈ `normal|warning|urgent`. Auto-hides after 4 s. |

### 5.5 `updateRealtimeCalculations()` — read this twice

This is the single function that derives everything visible in the right panel. Called after every score click and after `loadPatient`.

1. **Counts and sums per scale** by iterating `PANSS_ITEMS` and looking up `answers[item.code]`.
2. **Tab badges** — `${counts.X}/${maxes.X}`. Styled: all-done → green (`normal`), partial → amber (`warning`), none → grey.
3. **Progress** — `totalRatedCount / 30`, rounded. Updates `#progress-text` and `#progress-bar` width.
4. **Score summary** — `score-p/n/g-text` shows the sum, or `"-"` if nothing rated on that scale. `score-total-text` = grand total or `"-"`.
5. **Submit gate** — `#btn-submit` (`Save Completed Evaluation`) is enabled **iff** `totalRatedCount === 30`. `Pass` is always enabled.
6. **Clinical interpretation text** — three branches:
   - `totalRatedCount === 0` → "PENDING", placeholder copy.
   - `< 30` → "INCOMPLETE", running totals in copy.
   - `=== 30` → full interpretation:
     - **Severity bucket** by `grandTotal`: `≤30` Absent/Normal, `31–58` Mild (this is the `let severity = "Mild"` default), `59–75` Moderate, `76–95` Marked/Severe, `≥96` Extreme. **Bands are hardcoded** — change here to retune.
     - **Predominant subscale** by ratio: `sums.P/49`, `sums.N/49`, `sums.G/112` (where 49 = 7×7 and 112 = 16×7, the max possible per subscale). Whichever ratio is highest drives the narrative sentence.
     - Composes an HTML string with patient code, total, severity label, predominant narrative, and the italic disclaimer line.

> ⚠ **Severity bands are a clinical convention, not a law.** They live inline in this function. If a clinician asks to retune thresholds, this is the only place to edit. Do NOT silently change these — they have clinical meaning.

### 5.6 Where to make changes
- **Add a PANSS item?** Push to `PANSS_ITEMS`. Badges/maxes derive from `.scale`, so a new P8 / N8 / G17 just works. If you change the *count* of a subscale, update `maxes` inline in `updateRealtimeCalculations` (line 588) and the `30` literals in progress (line 619, 635, 652, 663) — there is no shared `TOTAL_ITEMS` constant; that's a known ponytail deferral.
- **Change severity bands?** §5.5 step 6. Keep the clinical disclaimer text intact.
- **New UI section?** It's one HTML file. Find an adjacent card, copy its structure, wire it in `updateRealtimeCalculations()` or a new function. Tailwind classes are inline; the custom palette is in the `tailwind.config` block in `<head>` (line 16).
- **Don't** add React/Vue/a bundler unless component count genuinely demands it. The single-file design is the point — see §9.

---

## 6. Data model

`data/assessments.json` is a flat JSON object, `<patient_code> → assessment`:

```json
{
  "PAT-2940-X": {
    "patient_code": "PAT-2940-X",
    "status": "completed",
    "scores": { "total": 120, "positive": 28, "negative": 30, "general": 62 },
    "items":   { "P1": 4, "P2": 3, "...": "...", "G16": 2 },
    "updated_at": "2026-07-06T03:30:01.218Z"
  },
  "PAT-OTHER": {
    "patient_code": "PAT-OTHER",
    "status": "passed",
    "updated_at": "2026-07-06T03:31:00.000Z"
  }
}
```

- **Keys** are patient codes as-typed-by-the-caller. The frontend uppercases (`code.trim().toUpperCase()`) before sending/storing; the backend does **not** normalize. If a parent app calls the API directly with `pat-2940-x` (lowercase), it will create a *different* record from the frontend's `PAT-2940-X`. Either normalize in the parent, or add a `.toUpperCase()` in the backend routes — currently a latent footgun.
- **No history / no versions.** PUT is overwrite. Prior state is gone.
- **No expiry, no cleanup.** The file grows monotonically.
- `updated_at` is server-set on PUT; GET for a pending skeleton has no `updated_at`.

---

## 7. API contract (cheat sheet)

| Method | Path | Body | Success | Errors |
|---|---|---|---|---|
| GET | `/api/severity/:patient_code` | — | `200` stored record **or** `200` pending skeleton | `400` empty code |
| PUT | `/api/severity/:patient_code` | `{status:"passed"}` | `200 {success:true, data:{...}}` | `400` empty code / bad status / bad scores / bad items; `500` write fail |
| PUT | `/api/severity/:patient_code` | `{status:"completed", scores:{total,positive,negative,general}, items:{P1:1..7, ...}}` | same | same |
| GET | any non-`/api/*` | — | serves `index.html` (SPA fallback) | — |
| OPTIONS | any | — | `200` (CORS preflight) | — |

**No list, no delete, no patch, no auth.** CORS is `*`.

---

## 8. Known sharp edges & footguns

These are intentional minimalism, not bugs — but they will bite if you forget.

1. **No backend case normalization.** `pat-2940-x` and `PAT-2940-X` are different records. Frontend uppercases; direct API callers may not.
2. **`readAssessments()` swallows corruption.** A malformed `assessments.json` returns `{}` silently — looks like an empty DB, doesn't error. If records "disappear", check the file contents first.
3. **No concurrency lock.** Two PUTs racing → last writer wins, no conflict signal. Single-user-localhost assumption.
4. **PANSS evaluation is server-authoritative.** `panss.js` validates the exact
   item set and score range, recomputes all totals, and rejects mismatched browser
   projections. Both v2 writes and the legacy PUT adapter use this evaluator.
6. **`app.get("*")` catch-all** is GET-only. A `POST /foo` will 404 cleanly; a `GET /api/unknown` will pass to `next()` and Express returns its default 404 (HTML, not JSON). Don't expect JSON 404s for unknown `/api/*` GETs.
7. **`fetchRecentAssessments` is local-only.** The "Recent Assessments" list on the lookup screen is per-browser `localStorage`, not a server query. Two different machines see different "recent" lists.
8. **Hardcoded `30` literals** appear in the frontend in several places instead of a derived constant. If you change the item count, grep `30` in `index.html`.
9. **"Welcome Dr. Amiral"** and `v1.0.0-alpha` are hardcoded strings, not config.
10. **`node_modules/` is committed in this repo** (per `git ls-files`). Not normal for a real project. Don't add to it; don't prune it in a PR without asking — it may be intentional for the standalone deployment story.

---

## 9. Intentionally deferred (the "ponytail ledger")

Per the project's ponytail philosophy, these are *deliberate* simplifications with a named trigger to add them. Each is meant to be a one-rung jump, not a rewrite. Matched to source seams:

| Skip | Why it's fine today | Add when | Where the seam is |
|---|---|---|---|
| SQLite / Prisma / migrations | Single-user localhost; JSON holds | Concurrent writes, audit-grade schema, querying across patients | `readAssessments`/`writeAssessments` in `server.js:38-57` |
| DELETE route | Not needed by any caller | Parent app needs to retract a record | add `app.delete("/api/severity/:patient_code", …)` above the catch-all in `server.js:134` |
| Auth (JWT/session) | Parent Insight app owns identity | Module exposed beyond localhost or needs standalone login | middleware slot before CORS in `server.js:22` |
| React/Vue/Vite/TS | Single-file HTML is readable, no bundle penalty | Component count grows; types start paying for themselves | all of `public/index.html` |
| `TOTAL_ITEMS` constant | 30 is small and obvious | A subscale item count changes and the literals drift | literals in `updateRealtimeCalculations` `index.html:588,619,635,652,663` |
| List endpoint (`GET /api/severity`) | Frontend uses `localStorage` recents | Parent app needs to enumerate saved assessments | add route before the catch-all |
| Build/CSS pipeline | Tailwind CDN is fine for one page | Second page, or offline-only deployment | `<script src="cdn.tailwindcss.com">` in `index.html:14` |

**To upgrade any of these:** make the smallest change that holds, leave a `ponytail:` comment naming what was skipped and the trigger to revisit, and don't refactor surrounding code in the same change.

---

## 10. The "ponytail" philosophy (context, not legal)

This module was built under a project-wide discipline called **ponytail** — ship the smallest thing that works, defer everything speculative, and **mark every deferral** with a `ponytail:` comment so it's traceable instead of rotting. The rules you'll see applied throughout:

- Stdlib / native platform first, then the smallest diff that holds.
- No abstraction with one implementation, no factory for one product, no config for a value that never changes.
- Deletion > addition. Boring > clever.
- Never simplify away: input validation at trust boundaries, error handling that prevents data loss, security, accessibility basics.
- Every non-trivial piece of logic leaves **one runnable check** behind (`test_api.js` is that check here — no test framework on purpose).

When you extend this module, **match the style**: read the file fully, find the smallest change that holds, leave a `ponytail:` comment if you cut a corner, and don't add a dependency. README §"Intentionally deferred" mirrors this ledger — keep the two in sync if you change the deferral set.

---

## 11. How to verify your change

1. `node test_api.js` — must print `SUCCESS: All integration tests passed successfully!` and exit 0. This exercises GET-new → PUT-passed → GET-verify-passed → PUT-completed → GET-verify-completed against a throwaway server on port 4567.
2. `npm start` and open `http://localhost:3000`:
   - Enter `TEST-FOO`, rate all 30 items, hit **Save Completed Evaluation** → toast → returns to lookup.
   - Re-enter `TEST-FOO` → status badge should say **Completed**, all 30 scores pre-filled.
   - Enter `TEST-BAR`, hit **Pass** → toast → returns to lookup. Re-enter `TEST-BAR` → badge **Passed / Skipped**.
   - Deep-link test: `http://localhost:3000/?patient_code=TEST-FOO` should land straight in the workspace.
3. Inspect `data/assessments.json` — should contain your test records with `updated_at` timestamps.

The self-check does **not** clean up `data/assessments.json` (it uses a real `TEST-PATIENT-99` key). If you need a pristine DB, delete the file — server recreates `{}` on next boot.

---

## 12. If you only read three things

1. **`server.js`** — the entire backend, 149 lines. Read it all.
2. **`updateRealtimeCalculations()` in `public/index.html:585`** — the clinical logic (severity bands, predominant-symptom narrative, submit gate). Read twice.
3. **§9 ledger above** — before adding *anything*, check whether it's already on the deferred list and what the trigger is. Don't pay down deferrals speculatively; don't add new ones silently.

The shortest correct change is the right change.
