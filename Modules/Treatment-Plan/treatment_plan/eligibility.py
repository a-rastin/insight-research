"""Table-driven data-quality and generation eligibility policy (TP-09)."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping
from .clinical_context import ClinicalContext, ContextErrorCode, Dependency
from .observability import current_observability

class Eligibility(str, Enum):
    ELIGIBLE="eligible"; BLOCKED="blocked"; SAFETY_PATHWAY="safety-pathway"
class Blocker(str, Enum):
    HARD="hard"; SOFT="soft"; SAFETY="safety"
@dataclass(frozen=True)
class FactRule:
    name: str; dependency: Dependency; required: bool; freshness_seconds: int|None
@dataclass(frozen=True)
class PathwayPolicy:
    pathway_id: str; diagnosis_prefixes: tuple[str,...]; facts: tuple[FactRule,...]; scope_approved: bool=False
@dataclass(frozen=True)
class EligibilityFinding:
    code: str; blocker: Blocker; fact: str; detail: str
@dataclass(frozen=True)
class EligibilityDecision:
    pathway_id: str; eligibility: Eligibility; findings: tuple[EligibilityFinding,...]
    @property
    def generation_allowed(self): return self.eligibility is Eligibility.ELIGIBLE

SCHIZOPHRENIA_RESEARCH_V1=PathwayPolicy("schizophrenia-research-v1",("F20",),(
 FactRule("patient-and-medications",Dependency.PATIENT,True,86400),
 FactRule("diagnosis",Dependency.DIAGNOSIS,True,86400),
 FactRule("severity",Dependency.SEVERITY,True,86400),
 FactRule("medical-history",Dependency.MEDICAL_HISTORY,True,2592000),
 FactRule("suicide-risk",Dependency.SUICIDE_RISK,True,86400)))
PATHWAY_POLICIES={SCHIZOPHRENIA_RESEARCH_V1.pathway_id:SCHIZOPHRENIA_RESEARCH_V1}

class GenerationEligibilityPolicy:
    """Return eligibility and reasons through one deterministic interface."""
    def __init__(self,policies:Mapping[str,PathwayPolicy]=PATHWAY_POLICIES): self._policies=dict(policies)
    def evaluate(self,context:ClinicalContext,pathway_id:str,*,now:datetime|None=None)->EligibilityDecision:
        if pathway_id not in self._policies: raise ValueError(f"unsupported pathway: {pathway_id}")
        policy=self._policies[pathway_id]; now=now or datetime.now(timezone.utc); findings=[]
        if not policy.scope_approved: findings.append(self._f("scope-unapproved",Blocker.HARD,"scope","DG-01, DG-03, and DG-07 are not approved"))
        for rule in policy.facts:
            if rule.name=="suicide-risk": continue
            value=context.inputs.get(rule.dependency)
            if value is None and rule.required:
                findings.append(self._f("required-fact-missing",Blocker.HARD,rule.name,"required authoritative fact is unavailable"))
            elif value is not None and rule.freshness_seconds is not None and self._stale(self._observed_at(rule.dependency,value),now,rule.freshness_seconds):
                blocker=Blocker.SOFT if rule.dependency is Dependency.MEDICAL_HISTORY else Blocker.HARD
                findings.append(self._f("stale-fact",blocker,rule.name,"fact exceeds the pathway freshness window"))
        for error in context.findings:
            if error.code is not ContextErrorCode.STALE:
                findings.append(self._f(f"source-{error.code.value}",Blocker.HARD,error.dependency.value,error.detail))
        diagnosis=context.inputs.get(Dependency.DIAGNOSIS,{})
        if diagnosis and (diagnosis.get("status") != "decided" or not diagnosis.get("clinicianDecision")):
            findings.append(self._f("diagnosis-not-confirmed",Blocker.HARD,"diagnosis","psychiatrist diagnosis decision is required"))
        severity=context.inputs.get(Dependency.SEVERITY,{})
        if severity and severity.get("status") != "completed": findings.append(self._f("severity-incomplete",Blocker.HARD,"severity","completed PANSS assessment is required"))
        meds=context.inputs.get(Dependency.MEDICAL_HISTORY,{}).get("medications",[])
        if any(item.get("normalizedIdentity",{}).get("state") != "matched" for item in meds if isinstance(item,Mapping)): findings.append(self._f("medication-unresolved",Blocker.HARD,"medical-history","medication reconciliation is unresolved"))
        risk=context.inputs.get(Dependency.SUICIDE_RISK,{}).get("assessment",{}).get("riskState")
        if risk in {"imminent-suicide-risk","substantial-suicide-risk-requiring-urgent-evaluation"}: findings.append(self._f("urgent-suicide-risk",Blocker.SAFETY,"suicide-risk","urgent risk requires the emergency safety pathway"))
        elif risk in {"unknown","unavailable","conflicting"}: findings.append(self._f("suicide-risk-unresolved",Blocker.HARD,"suicide-risk","suicide-risk state is unresolved"))
        result=Eligibility.SAFETY_PATHWAY if any(x.blocker is Blocker.SAFETY for x in findings) else Eligibility.BLOCKED if any(x.blocker is Blocker.HARD for x in findings) else Eligibility.ELIGIBLE
        unique={(x.code,x.fact):x for x in findings}
        observer=current_observability()
        observer.metric("tp_generation_total",labels={"kind":"eligibility","outcome":result.value,"policy_version":policy.pathway_id})
        missing=sum(1 for finding in unique.values() if finding.code=="required-fact-missing")
        if missing: observer.metric("tp_missing_input_total",missing,labels={"kind":"eligibility","module":"policy"})
        return EligibilityDecision(pathway_id,result,tuple(unique.values()))
    @staticmethod
    def _stale(value:Any,now:datetime,window:int)->bool:
        if not value:return False
        try:return (now-datetime.fromisoformat(str(value).replace("Z","+00:00"))).total_seconds()>window
        except (ValueError,TypeError):return True
    @staticmethod
    def _observed_at(dependency:Dependency,value:Mapping[str,Any])->Any:
        if dependency is Dependency.PATIENT:return value.get("provenance",{}).get("updatedAt")
        if dependency is Dependency.SEVERITY:return value.get("provenance",{}).get("updatedAt")
        if dependency is Dependency.SUICIDE_RISK:return value.get("assessment",{}).get("updatedAt")
        return value.get("updatedAt")
    @staticmethod
    def _f(code,blocker,fact,detail):return EligibilityFinding(code,blocker,fact,detail)
