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
 FactRule("ddi",Dependency.DDI,True,86400), FactRule("bn",Dependency.BN,True,86400),
 FactRule("suicide-risk",Dependency.SEVERITY,False,86400)))
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
            elif value is not None and rule.freshness_seconds is not None and self._stale(value.get("observedAt"),now,rule.freshness_seconds):
                blocker=Blocker.SOFT if rule.dependency is Dependency.MEDICAL_HISTORY else Blocker.HARD
                findings.append(self._f("stale-fact",blocker,rule.name,"fact exceeds the pathway freshness window"))
        for error in context.findings:
            if error.code is not ContextErrorCode.STALE:
                findings.append(self._f(f"source-{error.code.value}",Blocker.HARD,error.dependency.value,error.detail))
        diagnosis=context.inputs.get(Dependency.DIAGNOSIS,{}).get("diagnosis",{})
        code=str(diagnosis.get("code",""))
        if code and not code.startswith(policy.diagnosis_prefixes): findings.append(self._f("unsupported-diagnosis",Blocker.HARD,"diagnosis","diagnosis is outside the selected pathway"))
        severity=context.inputs.get(Dependency.SEVERITY,{})
        if str(severity.get("status","complete")).lower() in {"pending","preliminary","in-progress"}: findings.append(self._f("severity-pending",Blocker.HARD,"severity","severity assessment is not final"))
        meds=context.inputs.get(Dependency.PATIENT,{}).get("currentMedications",[])
        if any(str(x.get("status",x.get("resolutionStatus","resolved"))).lower() in {"unresolved","unknown","pending"} for x in meds if isinstance(x,Mapping)): findings.append(self._f("medication-unresolved",Blocker.HARD,"patient-and-medications","current medication reconciliation is unresolved"))
        raw=severity.get("severity",{}).get("suicideRisk"); values=raw if isinstance(raw,list) else [raw]
        signals={str(x).strip().lower() for x in values if x is not None}
        if len(signals)>1: findings.append(self._f("suicide-risk-contradiction",Blocker.SAFETY,"suicide-risk","contradictory suicide-risk evidence requires explicit safety review"))
        elif signals & {"high","imminent","positive"}: findings.append(self._f("high-suicide-risk",Blocker.SAFETY,"suicide-risk","high-risk evidence requires explicit safety review"))
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
    def _f(code,blocker,fact,detail):return EligibilityFinding(code,blocker,fact,detail)
