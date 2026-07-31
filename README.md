# INSIGHT

Psychiatrist-facing clinical decision support for schizophrenia care. Advisory
only — does not replace clinical judgment, diagnose autonomously, or prescribe.

Modules stay independently runnable. Cross-module traffic is versioned REST
only. Unified deploy is one Docker image with separate processes, ports, and
SQLite data directories; nginx gateway is the only public surface.

**Canonical app path:** this repository (`insight-research/`).

> **Status:** research-build. Not authorized for controlled clinical deployment.
> Treatment Plan review UI still uses synthetic data in places and is not fully
> wired to every backend route. DDI readiness may report
> `production-rest-seam-unavailable` until an approved active knowledge base is
> present. See `deploy/release-runbook.md` and `deploy/release-policy.json`.

---

## Prerequisites

| Tool | Version / notes |
| --- | --- |
| Docker Engine + Compose | Unified app path |
| Python | 3.11+ standalone modules; image uses 3.13 |
| Node.js | 22+ (Severity, Medical History, Suicide Risk, Treatment Plan UI) |
| `pip` / `npm` | Per-module deps when running standalone |
| `uv` (optional) | BN Manager tests in `deploy/module-tests.sh` |

Host OS: Linux (primary), Docker Desktop on Windows/macOS for local unified runs.

---

## Quick start (unified Docker)

Primary way to run the full app.

### 1. Clone and enter repo

```bash
cd /path/to/insight-research
```

### 2. Export required secrets

Generate strong values (do not commit them):

```bash
export AUTH_JWT_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(64))')"
export AUTH_ADMIN_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
export ADD_NEW_PATIENT_CSRF_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export DIAGNOSIS_CSRF_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export SEVERITY_CSRF_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export MEDICAL_HISTORY_CSRF_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export DDI_SERVICE_AUTH_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export SUICIDE_RISK_CSRF_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
```

Local HTTP (no TLS on the container port):

```bash
export AUTH_SECURE_COOKIE=false
export ADD_NEW_PATIENT_CSRF_SECURE=false
export DIAGNOSIS_CSRF_SECURE=false
```

Behind HTTPS set those `*_SECURE*` flags to `true` (Compose defaults to `true`).

Optional first-boot admin username (default `Admin`):

```bash
export AUTH_ADMIN_USERNAME=Admin
```

`AUTH_ADMIN_PASSWORD` seeds the admin **only on first database create**. Changing
it later does not rotate an existing admin row — use Auth admin APIs or a fresh
volume.

### 3. Build and start

```bash
docker compose -f deploy/compose.yaml up --build
```

Gateway: **http://localhost:8080/**

Stop:

```bash
docker compose -f deploy/compose.yaml down
```

Data lives in named Docker volumes (`authentication-data`, `dashboard-data`, …).
Remove volumes only if you intend to wipe local data:

```bash
docker compose -f deploy/compose.yaml down -v
```

### 4. Health checks

```bash
curl -sS http://localhost:8080/healthz   # liveness → {"status":"live","service":"gateway"}
curl -sS http://localhost:8080/readyz    # readiness (all required modules)
```

Liveness is dependency-free. Readiness fails closed if a required module or its
dependencies are not ready (paths and secrets are not leaked in responses).

### 5. Sign in

1. Open http://localhost:8080/ (Auth UI).
2. Log in with seeded admin: username `Admin` (or `AUTH_ADMIN_USERNAME`) and the
   `AUTH_ADMIN_PASSWORD` you set **at first volume init**.
3. Create psychiatrist accounts from Auth admin surfaces (via Dashboard admin
   workspace after login).
4. Psychiatrists accept the clinical disclaimer and complete any password-change
   gate before clinical modules unlock.

---

## Gateway map

Only port **8080** is published. Module processes bind `127.0.0.1` inside the
container.

| Path | Module | Internal port |
| --- | --- | --- |
| `/`, `/api/auth/` | Authentication | 8101 |
| `/dashboard/` | Dashboard | 8102 |
| `/modules/add-new-patient/`, `/api/patients`, `/api/add-new-patient/` | Add New Patient | 8103 |
| `/modules/diagnosis/`, `/api/diagnosis/` | Diagnosis | 8104 |
| `/modules/severity/`, `/api/severity/` | Severity | 8105 |
| `/modules/medical-history/`, `/api/medical-history/` | Medical History | 8106 |
| `/modules/ddi/`, `/api/ddi/` | DDI Checker | 8107 |
| `/modules/bn-manager`, `/api/bn-manager/v1`, `/api/bn-manager/v3` | BN Manager | 8108 |
| `/modules/suicide-risk/`, `/api/suicide-risk/` | Suicide Risk | 8109 |
| `/modules/treatment-plan`, `/api/treatment-plan/`, `/assets/` | Treatment Plan | 8110 |
| `/healthz`, `/readyz` | Gateway / readiness aggregator | 8080 / 8099 |

Browser code must use gateway-relative URLs, not hard-coded localhost module ports.

---

## Environment reference (unified compose)

Required by `deploy/compose.yaml`:

| Variable | Purpose |
| --- | --- |
| `AUTH_JWT_SECRET` | HS256 signing secret for Auth sessions |
| `AUTH_ADMIN_PASSWORD` | Seed admin password (first DB only) |
| `ADD_NEW_PATIENT_CSRF_SECRET` | CSRF secret (≥32 chars recommended) |
| `DIAGNOSIS_CSRF_SECRET` | CSRF secret |
| `SEVERITY_CSRF_SECRET` | CSRF secret |
| `MEDICAL_HISTORY_CSRF_SECRET` | CSRF secret |
| `DDI_SERVICE_AUTH_SECRET` | HMAC secret for Treatment Plan → DDI service auth |
| `SUICIDE_RISK_CSRF_SECRET` | CSRF secret |

Common optional / defaults:

| Variable | Default / note |
| --- | --- |
| `AUTH_SECURE_COOKIE` | `true` in compose; set `false` for plain HTTP local |
| `ADD_NEW_PATIENT_CSRF_SECURE` | `true` |
| `DIAGNOSIS_CSRF_SECURE` | `true` |
| `AUTH_ADMIN_USERNAME` | `Admin` (module default if unset) |
| `NODE_ENV` / `TP_ENV` | `production` in compose |

Entrypoint also wires Treatment Plan internal URLs to loopback Auth/DDI and runs
the Treatment Plan migration gate before supervisord starts.

Full Auth knobs: `Modules/Auth/.env.example`.

Runtime topology source of truth: `deploy/runtime-policy.json`,
`deploy/supervisord.conf`, `Dockerfile`.

---

## Standalone module runs

Each module can run alone for development. Defaults below are module-local ports
(not the unified 81xx map). Point auth-related env at a running Auth instance
when testing integration.

### Authentication

```bash
cd Modules/Auth
python3 -m pip install -r requirements.txt
# optional: cp .env.example .env
python3 main.py
# http://localhost:8000/  (AUTH_PORT overrides port)
```

### Dashboard

```bash
cd Modules/Dashboard-1.2.0
python3 -m pip install -r requirements.txt
python3 -m uvicorn dashboard_backend.main:app --host 127.0.0.1 --port 4173
# http://localhost:4173/dashboard/
```

Without `AUTH_SESSION_URL` / `AUTH_BASE_URL`, Dashboard serves a mock session for
standalone UI work. Set `DASHBOARD_MOCK_AUTH=0` when using real Auth.

### Add New Patient

```bash
cd Modules/Add-New-Patient-1.1.0
python3 -m pip install -r requirements.txt
uvicorn add_new_patient_backend.main:app --port 4173
# or: uvicorn server:app --port 4173
```

### Diagnosis

```bash
cd Modules/Diagnosis-1.2.0
python3 -m pip install -r requirements.txt
python3 -m diagnosis
# http://localhost:8000
```

### Severity (Node)

```bash
cd Modules/Severity-1.1.0
npm install
npm start
# PORT default from server; set SEVERITY_DB_PATH, SEVERITY_AUTH_BASE_URL, SEVERITY_CSRF_SECRET
```

### Medical History (Node ≥22.5)

```bash
cd Modules/Medical-History-1.0.0
npm start
# default http://127.0.0.1:4173
# MEDICAL_HISTORY_DB_PATH, MEDICAL_HISTORY_AUTH_BASE_URL, MEDICAL_HISTORY_CSRF_SECRET
```

### DDI Checker

Standalone UI: open `Modules/DDI-Checker-1.2.0/index.html` or serve the folder
statically. Production REST seam in the unified image is
`deploy/ddi-static-server.mjs` (HMAC + Auth session).

```bash
cd Modules/DDI-Checker-1.2.0
npm test
```

### BN Manager

```bash
cd Modules/BN-Manager-v.1.1.0/BN-Manager-v.1.1.0
python3 server.py
# http://127.0.0.1:8000  — UI at /modules/bn-manager
```

### Suicide Risk (Node ≥22.5)

```bash
cd Modules/Suicide-Risk-1.0.0
npm start
# default PORT=8109
# SUICIDE_RISK_DB_PATH, SUICIDE_RISK_AUTH_BASE_URL, SUICIDE_RISK_CSRF_SECRET
```

### Treatment Plan

```bash
cd Modules/Treatment-Plan
python3 -m pip install -r requirements.txt
python3 -m treatment_plan.deployment migration-gate
python3 -m treatment_plan.deployment serve
# TP_HOST / TP_PORT (default 8000), TP_DATABASE_PATH, TP_AUTHENTICATION_SESSION_URL, TP_DDI_*
```

Frontend (dev):

```bash
cd Modules/Treatment-Plan/frontend
npm install
npm run dev
```

Module-local docs and contracts live under each module’s `README.md`, `docs/`,
`contracts/`, and handoff files.

---

## Tests

### All module suites (from repo root)

```bash
./deploy/module-tests.sh
```

### Root contract / integration tests

```bash
python3 -B -m unittest discover -s tests -v
```

### Single module examples

```bash
cd Modules/Auth && python3 -B -m unittest discover -s tests -v
cd Modules/Severity-1.1.0 && npm test
cd Modules/Treatment-Plan && python3 -B -m unittest discover -s tests -v
cd Modules/Treatment-Plan/frontend && npm test && npm run typecheck && npm run build
```

Use `python3 -B` so runs do not drop `__pycache__` into the tree.

---

## Production / VPS (research-build)

Not a clinical go-live path. Summary only — full procedure:
[`deploy/release-runbook.md`](deploy/release-runbook.md).

1. Build and push a registry image; pin by **digest** (`repo@sha256:…`).
2. Terminate TLS on **host nginx** with `deploy/nginx-tls.conf.template`
   (certs outside git, e.g. `/etc/insight/tls/`).
3. Bind container gateway to `127.0.0.1:8080` only
   (`deploy/compose.release.yaml`).
4. Set release secrets: `INSIGHT_IMAGE`, backup dir/key, E2E fixtures, rollback
   inventory, etc.
5. Run `deploy/release.sh` — module gates, pull, migrate, TLS health/ready, E2E,
   backup/restore, restart. Any failed or skipped required gate blocks publish.

Rollback: `deploy/operations.py rollback` (no down-migrations; only digests that
can read current schemas).

---

## Architecture snapshot

| Layer | Choice |
| --- | --- |
| Public edge | Host nginx + TLS (VPS); container nginx gateway on 8080 |
| Process supervisor | supervisord inside image (`deploy/supervisord.conf`) |
| Python services | FastAPI + Uvicorn (Auth, Dashboard, Patient, Diagnosis, BN Manager, Treatment Plan) |
| Node services | Express / Node servers (Severity, Medical History, Suicide Risk); DDI static+REST seam |
| Treatment Plan UI | React + Vite (built into image) |
| Persistence | Module-owned SQLite under `/var/lib/insight/<module>` (PostgreSQL is a controlled upgrade path) |
| Identity | Canonical `patientId` / `encounterId` UUIDs; Auth session cookie + CSRF on writes |

Normative context (read before changing behavior):

1. `context/project-overview.md`
2. `context/architecture.md`
3. `context/ui-context.md`
4. `context/code-standards.md`
5. `context/ai-workflow-rules.md`
6. `context/progress-tracker.md`

Agent workflow notes: `AGENTS.md`.

---

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Compose exits on start | All required env vars set (`:?set …` errors name the missing one) |
| `/readyz` 503 | `docker compose -f deploy/compose.yaml logs` — which module failed; DDI needs configured service auth + valid active KB under registry |
| Cannot log in after secret change | Admin password only seeds on empty Auth DB; wipe `authentication-data` volume or use admin password-change flow |
| Cookie / CSRF failures on HTTP | `AUTH_SECURE_COOKIE=false` and module `*_CSRF_SECURE=false` for local plain HTTP |
| Port 8080 in use | Stop other listeners or change host port mapping in compose |
| Standalone module auth failures | Start Auth first; set each module’s `*_AUTH_*` URL to that instance; disable mock/bypass flags |

---

## License

MIT — see [`LICENSE`](LICENSE).
