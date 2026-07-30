# Severity Module

A standalone web app and Insight sub-module for PANSS (Positive and Negative Syndrome Scale) schizophrenia severity assessment. Psychiatrist-facing, API-first, research-grade.

Part of the **Insight** clinical decision support platform. Communicates with other modules exclusively through internal REST APIs. Runs independently on `localhost` or any VPS browser.

---

## Features

- **PANSS questionnaire** — 30 items grouped by subscale (Positive P1–P7, Negative N1–N7, General Psychopathology G1–G16), each scored 1 (Absent) to 7 (Extreme).
- **Real-time conclusion box** — live subtotal and total scores, severity classification (Absent → Extreme), predominant-symptom narrative, and clinician-control disclaimer.
- **Sticky totals panel** — progress bar, P/N/G subtotals, total score (monospaced numeric per design spec).
- **Two submit paths**
  - `Save Completed Evaluation` — enabled only when all 30 items are rated → PUT `{status:"completed", scores, items}`.
  - `Pass` — skips the assessment → PUT `{status:"passed"}`.
- **Dashboard button** — resets the workspace, clears URL params, returns to patient lookup.
- **Patient lookup** — via form or deep-link `?patient_code=<code>` query param (so the parent app can route in directly).
- **CORS open** for inter-module calls; serves `index.html` at `/` for standalone use.

---

## Stack

- **Backend** — Node.js + Express (single dependency). File-based JSON persistence in `data/assessments.json`.
- **Frontend** — Single-file `public/index.html`. Tailwind via CDN, vanilla JS (ES modules). Zero build step, zero bundler.
- **Design tokens** — matches `DESIGN.md`: teal `#0A9E8F` accent, Inter body, JetBrains Mono for codes/scores, 2px teal focus rings, clinician-control labels.

> **Ponytail note:** Deliberately minimal. SQLite, build tooling, and auth are intentionally deferred — add when concurrent writes, bundle size, or multi-user identity actually demand them. Each is a one-rung jump, not a rewrite.

---

## File layout

```
severity/
├── package.json           # single dep: express
├── server.js              # REST API + static server (GET/PUT + CORS)
├── test_api.js            # assert-based self-check (no test framework)
├── data/
│   └── assessments.json   # file persistence (created on first run)
└── public/
    └── index.html         # PANSS UI (single file, no bundler)
```

---

## API contract

All routes are prefixed `/api/severity/:patient_code`. JSON in/out. CORS open for parent-app integration.

PANSS v2 is canonical for UUID-based integration. Machine-readable artifacts live in
`contracts/`, and discovery is available at `GET /api/severity/v2/contract`.
V2 creates use `POST /api/severity/v2/assessments` with `Idempotency-Key` and
`X-Schema-Version: 2.0.0`; reads and ETag-protected updates use
`/api/severity/v2/assessments/{assessmentId}`. Completed scores are always
recomputed server-side from the exact 30-item set. Responses include explicit
`incomplete`, `passed`, or `completed` evaluation state and scoring versions.
Optional browser-projected totals are checked and rejected if malformed or
mismatched; they are never authoritative. `skipped` contains no ratings or scores
and never means absent, normal, or favorable. Existing patient-code routes remain
a v1 compatibility interface, retain their historical `passed` spelling, and use
the same evaluator.

### GET `/api/severity/:patient_code`

Retrieves an existing assessment or returns a fresh `pending` skeleton.

**Response 200**
```json
{
  "patient_code": "PAT-2940-X",
  "status": "pending | completed | passed",
  "scores": { "total": 0, "positive": 0, "negative": 0, "general": 0 },
  "items": { "P1": 4, "N1": 2, "G1": 1 }
}
```

| Field | Description |
|---|---|
| `patient_code` | Echoed path param. |
| `status` | `pending` (new/in-progress), `completed` (saved with scores), `passed` (skipped). |
| `scores` | Subtotals + total. Present when `completed`; zeros for `pending`. |
| `items` | Map of item code → 1–7 rating. Present when `completed`. |

**Errors** — `400` if `patient_code` is empty.

---

### PUT `/api/severity/:patient_code`

Saves either a completed assessment or a pass.

**Body — completed**
```json
{
  "status": "completed",
  "scores": { "total": 120, "positive": 28, "negative": 30, "general": 62 },
  "items": { "P1": 4, "P2": 3, "...": "...", "G16": 2 }
}
```

**Body — passed**
```json
{ "status": "passed" }
```

**Response 200**
```json
{
  "success": true,
  "data": {
    "patient_code": "PAT-2940-X",
    "status": "completed",
    "scores": { "...": "..." },
    "items": { "...": "..." },
    "updated_at": "2026-07-06T03:30:01.218Z"
  }
}
```

**Errors**
- `400` — missing `patient_code`, invalid `status` (must be `completed` or `passed`), an invalid/incomplete item set, or malformed/mismatched projected scores.
- `500` — file write failure.

---

## Run

### Standalone

```powershell
cd E:\severity
npm install
npm start
```

Open `http://localhost:3000`. Enter a patient code or deep-link: `http://localhost:3000/?patient_code=PAT-2940-X`.

### As a sub-module

Parent app calls `GET /api/severity/<code>` to load, `PUT /api/severity/<code>` to save. No other surface area. CORS is open so the parent app can hit it from a different origin/port.

### Run the self-check

```powershell
npm test
```

Runs `assert`-based v2 contract/scoring/idempotency/ETag checks and the v1
compatibility GET/PUT checks using isolated temporary persistence.

---

## UI walkthrough

1. **Lookup screen** — enter a patient code or pick from recent (stored in `localStorage`). Submit loads the workspace.
2. **Workspace (two-column desktop)**
   - **Left** — tabbed PANSS grid (P / N / G). Each item row shows code, name, short description, a 1–7 selector, and a live severity label (Absent → Extreme). `Reset Form` clears scores.
   - **Right (sticky)** — patient context, progress bar, P/N/G + total subtotals, real-time clinical interpretation, and action buttons.
3. **Actions**
   - `Save Completed Evaluation` — disabled until all 30 items rated.
   - `Pass` — sends `{status:"passed"}`, confirms, returns to lookup.
   - `Dashboard` — clears state and returns to lookup.

---

## Design compliance

This module follows `DESIGN.md`:

- **Colors** — white canvas, teal `#0A9E8F` primary, surface/border tokens, urgent/warning/normal/info status colors paired with icons + labels (never color alone).
- **Typography** — Inter body (15px / 1.6), JetBrains Mono for PANSS codes, scores, timestamps, patient codes.
- **Layout** — desktop-first, sticky right summary panel, restrained whitespace.
- **Clinician control** — every recommendation is followed by a psychiatrist action. Labels read `Decision-support recommendation. Psychiatrist final review required.` Never `App decision` / `AI prescription`.
- **Accessibility** — 2px solid teal focus rings with 2px offset, semantic table headers, keyboard-navigable score buttons, `prefers-reduced-motion` respected via Tailwind defaults.

---

## Intentionally deferred (ponytail ledger)

| Skip | Why | Add when |
|---|---|---|
| SQLite / Prisma | Single-user localhost, JSON file holds | Concurrent writes or audit-grade schema required |
| Vite / React / TS | Single-file HTML is readable, no bundle penalty | Component count grows or types start paying for themselves |
| JWT / session auth | Parent Insight app owns identity | Module is exposed beyond localhost or needs standalone login |

Each is a one-rung jump from current state — not a rewrite. The `ponytail:` comments in `server.js` mark the seams.
