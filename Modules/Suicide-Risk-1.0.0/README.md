# Suicide Risk Module

Independent Node.js 22.5+ service for encounter-scoped psychiatrist suicide-risk assertions. It owns its SQLite database and communicates through the versioned `/api/suicide-risk/v1` REST interface.

## Clinical boundary

No licensed C-SSRS question bank exists in the repository. This module therefore defines no instrument question, answer, score, threshold, or location-specific emergency instruction and never claims that C-SSRS was completed.

Writable states:

- `unknown` and `unavailable` from `contracts/clinical-ownership-v1.json`.
- `conflicting` from the INS-010 required-input uncertainty policy.
- `not-elevated` explicit psychiatrist assertion allowing routine planning (does not claim C-SSRS completion).
- `imminent-suicide-risk` and `substantial-suicide-risk-requiring-urgent-evaluation` from the INS-010 emergency trigger states.

Every state is an explicit authenticated psychiatrist assertion. Unknown, unavailable, and conflicting states block dependent processing. `not-elevated` allows routine Treatment Plan generation. Urgent states persistently stop routine planning with the exact general emergency guidance approved in INS-010. No state is overridable.

## Run

```sh
npm start
npm test
```

Configuration:

- `PORT`, default `8109`
- `SUICIDE_RISK_DB_PATH`, default `data/suicide-risk.db`
- `SUICIDE_RISK_AUTH_BASE_URL`, default `http://127.0.0.1:8101`
- `SUICIDE_RISK_AUTH_TIMEOUT_MS`, default `2000`
- `SUICIDE_RISK_CSRF_SECRET`, required in production and at least 32 characters
- `SUICIDE_RISK_ALLOWED_ORIGINS`, comma-separated exact origins

## REST API

- `GET /healthz`
- `GET /readyz`
- `GET /api/suicide-risk/v1/contract`
- `GET /api/suicide-risk/v1/contract/{document|schema|openapi}`
- `GET /api/suicide-risk/v1/csrf`
- `POST /api/suicide-risk/v1/assessments`
- `GET /api/suicide-risk/v1/assessments/{assessmentId}`
- `PUT /api/suicide-risk/v1/assessments/{assessmentId}`
- `GET /api/suicide-risk/v1/encounters/{encounterId}/assessments/latest`
- `GET /api/suicide-risk/v1/encounters/{encounterId}/snapshot`

Clinical routes require a current psychiatrist session verified through Authentication v2. Writes require a session-bound double-submit CSRF token. Creates require `Idempotency-Key`; updates require a strong `If-Match` ETag.

The snapshot route provides Treatment Plan with the exact assessment, owner, schema version, resource version, ETag, and SHA-256 content hash needed to preserve a versioned source snapshot.

## Embedded UI

```js
await window.InsightSuicideRisk.mount({
  root: document.querySelector("#suicide-risk-root"),
  context: { patientId, encounterId, actorId, assessmentId }
});
```

`assessmentId` is optional. Context comes only from the host and is never written to browser storage or navigation. The UI has no preselected assertion, keeps save failures visible, exposes urgent and blocked behavior with text rather than color alone, and supports native keyboard controls and reduced motion.

Database-at-rest encryption, backup/restore, retention policy, an approved C-SSRS source/license, and named clinical governance approval remain release gates.
