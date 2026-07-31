# Dashboard Dataset Schema

Dashboard is a workspace router. It stores only Dashboard-owned session and workspace-event state. It does not store Authentication users, Authentication profile copies, clinical patient records, treatment data, admin oversight data, guideline data, Bayesian model data, backup payloads, or downstream module data.

## Tables

### dashboard_sessions

| Column | Type | Notes |
| --- | --- | --- |
| id | string, pk | Dashboard session id |
| user_id | string | Verified Authentication user id for session binding only |
| role | enum | Last verified role: `PSYCHIATRIST` or `ADMIN` |
| auth_session_id | string | Authentication session id used for re-validation |
| active | boolean | Signed-out sessions become inactive |
| created_at | datetime | Dashboard session creation time |
| disclaimer_accepted_at | datetime, nullable | Dashboard-local prototype notice state for this session |

### workspace_events

Optional audit trail for Dashboard shell events only.

| Column | Type | Notes |
| --- | --- | --- |
| id | int, pk | Local sequence |
| dashboard_session_id | string, fk | Dashboard session id |
| user_id | string | Verified Authentication user id for session binding only |
| role | enum | Verified role at event time |
| event_type | string | Dashboard shell event name |
| at | datetime | Event time |

## Explicit Non-Owners

Dashboard does not own or store these datasets:

| Dataset | Owner |
| --- | --- |
| Authentication users, profiles, passwords, MFA, roles | Authentication |
| Patient demographics, charts, treatment plans, follow-ups | Clinical/patient modules |
| Admin user management | Admin/user module |
| Logs, backup payloads, guideline revisions, Bayesian models | Their downstream modules |

## Workspace Strings

| Key | Value |
| --- | --- |
| dashboard.workspace.title | Workspace |
| dashboard.psychiatrist.button.add | Add New Patient |
| dashboard.psychiatrist.button.followUp | Patient Follow-up |
| dashboard.psychiatrist.button.list | List of Patients |
| dashboard.psychiatrist.button.setting | Setting |
| dashboard.admin.button.addUser | Add New User |
| dashboard.admin.button.logs | Logs |
| dashboard.admin.button.backup | Backup |
| dashboard.admin.button.listUsers | List of Users |

`Add New User` and `List of Users` are navigation metadata only. Their
gateway-relative routes target Authentication; no account field is added to a
Dashboard table.

## Module Destinations

Each workspace destination has one explicit state:

```json
{
  "id": "add-new-patient",
  "title": "Add New Patient",
  "state": "available",
  "reason": "Destination available.",
  "href": "/modules/add-new-patient"
}
```

`available` destinations include a gateway-relative route. `unavailable` and
`unauthorized` destinations include no route. Target modules own implementation
and data.
