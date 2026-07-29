# ADR-0003: Follow-up and Suicide-risk Ownership

- Status: Accepted
- Date: 2026-07-29
- Decision owners: Task-level product, clinical, and architecture approval; accountable names unresolved
- Scope: INS-004

## Context

INSIGHT requires one writer for Encounter, Follow-up Delta, and structured
suicide-risk assessment data. Existing context assigns Encounter identity to Add
New Patient but does not establish whether Follow-up is a service or who owns the
other records. No approved C-SSRS source/licensing contract is available, so the
instrument's questions and scoring cannot be defined.

This decision follows the [architecture invariants](../architecture.md) and the
[INS-004 specification](../feature-specs/04-decide-ownership.md). Normative
machine-readable ownership and examples live in
[clinical-ownership-v1.json](../../contracts/clinical-ownership-v1.json) and are
checked by [test_clinical_ownership.py](../../tests/test_clinical_ownership.py).

## Decision

Follow-up is an orchestration flow, not a standalone owner. It creates no
authoritative clinical record itself and receives no separate persistence or
service boundary.

Add New Patient remains sole writer for Patient, Encounter, intake snapshot, and
Follow-up Delta records. A follow-up creates a new Encounter UUID. Its Follow-up
Delta references that encounter and the preceding encounter; it does not mutate
the preceding record. Assessment modules remain sole writers for their own new
encounter-scoped assessments. Treatment Plan remains sole writer for plan
supersession records.

A dedicated Suicide Risk module is sole writer for structured C-SSRS assessment
records. This ownership designation does not approve or implement an instrument.
Until an approved source/licensing contract is supplied, the module has no
questions or scoring rules and cannot produce a risk score. Missing risk is
represented explicitly as `unknown` or `unavailable`; required risk-dependent
processing is blocked and must not infer a negative, normal, or low-risk result
from model summaries or absence of data.

## Alternatives

| Alternative | Reason rejected |
| --- | --- |
| Standalone Follow-up owner | Duplicates Encounter and assessment ownership and creates a second clinical writer. |
| Medical History owns C-SSRS | Mixes a separately governed structured instrument into general history submissions. |
| Treatment Plan owns Follow-up Delta or risk | Violates its snapshot/orchestration boundary and makes copied inputs authoritative. |
| Infer score or questions from summaries | No approved source/licensing contract; inference would create unsupported clinical content. |

## Consequences

- Add New Patient must eventually publish versioned Encounter and Follow-up Delta
  REST contracts before runtime integration.
- Suicide Risk needs an independently approved module/API/schema work packet and
  approved C-SSRS source/licensing contract before instrument implementation.
- Current workflows must expose missing risk and remain blocked wherever risk is
  required.
- Accountable governance-owner names remain unresolved; clinical release stays
  blocked.

## Verification

Run `python3 -B -m unittest tests/test_clinical_ownership.py`. Tests reject zero
or duplicate writers, verify flow ownership, require fail-closed risk governance,
and cover initial, follow-up, unknown-risk, unavailable-assessment, and
supersession examples.

## Rollback

Supersede this ADR and ownership contract together. Any ownership transfer must
define export/import contracts, preserve canonical UUIDs and provenance, validate
migration, and coordinate provider and consumer interfaces. Never introduce a
temporary second writer.
