# BN Manager

BN Manager is the standalone FastAPI service for validating, discovering, governing, and evaluating the INSIGHT clinical Bayesian Networks. Contract v3 uses the supplied BIF 0.3 XML schema and accepts canonical manifest-owned registry models only.

The complete machine-readable v3 contract is published in `contracts/` as
`bn-manager-v3.contract.json`, `bn-manager-v3.schema.json`, and
`openapi-v3.json`.

## Canonical networks

The module owns exactly four versioned registry entries:

| Stable ID | Title | Registry file | Evaluation target |
|---|---|---|---|
| `bnm.pharmacotherapy` | Pharmacotherapy | `xml/BN-Pharmacotherapy.xml` | `management_recommendation` |
| `bnm.treatment-setting` | Treatment Setting | `xml/BN-Treatment-Setting.xml` | `management_recommendation` |
| `bnm.involuntary-treatment-considerations` | Involuntary Treatment Considerations | `xml/BN-Involuntary-Treatment-Considerations.xml` | `management_recommendation` |
| `bnm.clozapine-suicide-risk` | Clozapine in Suicide Risk | `xml/BN-Clozapine-in-Suicide-Risk.xml` | `Clinical_Action_Pattern` |

The canonical schema is `bn_manager_backend/model_registry/schemas/XSD.xml`. The API no longer accepts `.net` or `.xmlbif` model formats, and the legacy conversion route has been removed.

## Model pipeline

1. The module-owned registry resolves only relative paths under `bn_manager_backend/model_registry/`.
2. `compile_xmlbif()` parses XML with external entities and network access disabled.
3. Every API-loaded model is validated against `XSD.xml`.
4. The compiler maps `VARIABLE TYPE="nature"` nodes and `DEFINITION` tables into `ClinicalGraphModel`.
5. Semantic validation checks references, unique nodes/states, CPT dimensions, row sums, and requested target nodes.
6. Evaluation returns posterior probabilities for the selected chance target.

Two supplied networks use a single neutral probability row for selected conditional tables. The compiler broadcasts that row across every parent-state combination. This preserves the source XML and makes the compact qualitative CPTs dimensionally valid and evaluable. Full CPTs are never rewritten.

The Pharmacotherapy model is governed by mapping version `2.0.0`. Its source-to-node mapping and source/model hashes are recorded in `bn_manager_backend/model_registry/governance/pharmacotherapy-mapping-v2.json` and validated by the adjacent Draft 2020-12 schema. The model evaluates one explicitly identified candidate at a time; it does not support medication ranking, FGA-versus-SGA preference, or automatic selection. Deterministic contraindication, diagnosis, and uncertainty gates run before inference. Gate-clearing v3 requests return a candidate-bound posterior and exact active model version/hash, so a later governed CPT revision can produce patient-specific probabilities without changing the request vocabulary. The current candidate-priority and management CPTs remain uniform placeholders, so discovery and each result label them `qualitative-uncalibrated`; research runtime evaluation and recommendation use are approved, with calibrated CPT replacement still the upgrade path.

## Run

Requires Python 3.11 or newer.

```powershell
python server.py
```

The API starts at `http://127.0.0.1:8000`. The protected module UI is mounted at `/modules/bn-manager`.

Authentication defaults to `GET /api/auth/v2/session` and can be configured with:

```powershell
$env:BN_MANAGER_AUTH_SESSION_URL = "http://127.0.0.1:8000/api/auth/v2/session"
$env:BN_MANAGER_AUTH_TIMEOUT_SECONDS = "2.0"
$env:BN_MANAGER_CSRF_HEADER_NAME = "x-csrf-token"
```

## API

Read-only routes:

- `GET /api/health`
- `GET /api/ready`
- `GET /api/bn-manager/v1/contract`
- `GET /api/bn-manager/v1/models`
- `GET /api/bn-manager/v1/models/{stable_id}`
- `GET /api/bn-manager/v1/models/schema/xml-0.3`
- `GET /internal/dashboard/module-routes/bn-manager`
- `GET /modules/bn-manager`

Protected write routes:

- `POST /api/bn-manager/v3/evaluations`
- `POST /api/bn-manager/v1/dashboard/evaluate`
- `POST /api/bn-manager/v1/add-new-patient/evaluate`
- `POST /api/bn-manager/v1/follow-up/evaluate`
- `POST /api/bn-manager/v1/models/validate`

Write routes require a verified Authentication session, an allowed role, and the configured CSRF header.
The v3 evaluation route also requires `Idempotency-Key`; a retry with the same
actor, key, and payload returns the original evaluation UUID and timestamp,
while conflicting reuse returns `409`. Clinical evaluation accepts only a
registry `stable_id`. Caller-supplied XML is retained solely for the admin
validation route.

V3 discovery is available at `GET /api/bn-manager/v3/models` and
`GET /api/bn-manager/v3/models/{stable_id}`. It returns semantic version,
content hash, BIF/XSD identity, engine version, lifecycle and clinical-use
status, target, mapping version/hash, and calibration status without returning model text. Evaluation
returns accepted and ignored evidence, warnings, posterior, mapping version,
evaluation UUID, and UTC evaluation time.

Administrator-only registry routes are available under
`/api/bn-manager/v3/admin/models`. Inventory and detail responses include live
validation evidence, manifest source provenance and hashes, lifecycle history,
and activation blockers. Review, activation, retirement, and rollback writes
require CSRF and a 20-2,000 character rationale. Lifecycle state is stored in
the module registry at `governance.sqlite3`; set `BN_MANAGER_GOVERNANCE_DB` to
override that path. Current manifest entries are research-approved and allow runtime
use, so activation fails closed until the authoritative manifest records both
required approvals. No administration route accepts a caller path or model text.

### Validate a registry model

```json
{
  "model": {
    "model_id": "bnm.pharmacotherapy"
  }
}
```

### Evaluate a registry model

```json
{
  "model": {
    "model_id": "bnm.clozapine-suicide-risk"
  },
  "evidence": {
    "Schizophrenia_Suicide_Indication": "Met",
    "Clozapine_Contraindications": "Absent",
    "Monitoring_Adherence_Capacity": "Sufficient"
  }
}
```

Only an administrator calling `POST /api/bn-manager/v1/models/validate` may
provide `{"format": "XML", "text": "<BIF ...>"}`. Evaluation routes reject
caller model text and use registry `stable_id` values only.

## Python API

```python
from bn_manager_backend.model_registry import read_registry_model, read_registry_schema
from clinical_graph_models import compile_xmlbif, evaluate_posterior, validate_model

entry, text = read_registry_model("bnm.clozapine-suicide-risk")
model = compile_xmlbif(text, schema_text=read_registry_schema())
messages = validate_model(model, target_node_ids=[entry.target_node])
result = evaluate_posterior(
    model,
    entry.target_node,
    {"Schizophrenia_Suicide_Indication": "Met"},
)
```

## Test

```powershell
python -m unittest discover -s tests -v
```

The suite covers all four registry models, XSD enforcement, compact CPT broadcasting, semantic validation, API discovery/detail behavior, XML-only format rejection, target resolution, posterior evaluation, authentication, role guards, and CSRF protection.

## Architecture outputs

Graphify outputs live in `graphify-out/`:

- `graph.html`: interactive architecture graph
- `GRAPH_REPORT.md`: graph analysis report
- `graph.json`: machine-readable graph
