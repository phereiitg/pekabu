"""Mandates and intent capsules.

Modelled on three sources that independently converge on the same idea:
  - OWASP ASI01 mitigation 5, the "intent capsule": bind the declared goal,
    constraints and context to each execution cycle in a signed envelope.
  - OWASP ASI02 mitigation 4, the "Intent Gate": a pre-execution policy point
    that validates intent and arguments and audits on drift.
  - OWASP ASI03 mitigation 5: bind tokens to a signed intent covering subject,
    audience, purpose and session; reject use where bound intent and request
    disagree.

All three are written as *enforcement* controls. We implement the same object
as a *detection* signal, which is the distinction our novelty claim rests on:
enforcement fails closed on a rule violation, detection scores a continuous
divergence and lets the cost function decide.

Nothing here is a shipped public standard. That goes in F16.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Dict
import hashlib


@dataclass(slots=True)
class IntentCapsule:
    """What the human actually asked for, captured at delegation time."""
    capsule_id: str
    stated_intent: str                    # free text, as the user expressed it
    intent_embedding: Optional[List[float]] = None   # filled by Head C soft half
    category_hint: Optional[str] = None   # coarse MCC family the user implied
    issued_at: Optional[datetime] = None

    def digest(self) -> str:
        return hashlib.sha256(self.stated_intent.encode()).hexdigest()[:16]


@dataclass(slots=True)
class Mandate:
    """A scoped, time-bound authorisation delegated to one agent.

    Scope mirrors Agent Pay's agentic-token model: spend ceiling, merchant
    category constraint, expiry, cryptographically bound to a specific agent.
    """
    mandate_id: str
    agent_id: str
    payer_id: str
    capsule: IntentCapsule

    ceiling: Decimal
    allowed_mccs: List[str] = field(default_factory=list)
    expiry: Optional[datetime] = None
    beneficiary_hint: Optional[str] = None

    is_open: bool = False       # open mandates permit repeated execution
    max_executions: int = 1
    executions: int = 0
    spent: Decimal = Decimal("0")

    signature: Optional[str] = None
    revoked: bool = False

    # -- hard checks. These are plain code and they fail closed. ----------
    def scope_violations(self, amount: Decimal, mcc: str,
                         beneficiary: str, now: datetime) -> List[str]:
        v: List[str] = []
        if self.revoked:
            v.append("revoked")
        if self.expiry and now > self.expiry:
            v.append("expired")
        if self.spent + amount > self.ceiling:
            v.append("ceiling_exceeded")
        if self.allowed_mccs and mcc not in self.allowed_mccs:
            v.append("mcc_out_of_scope")
        if self.executions >= self.max_executions and not self.is_open:
            v.append("execution_count_exceeded")
        if self.beneficiary_hint and beneficiary != self.beneficiary_hint:
            v.append("beneficiary_mismatch")
        return v

    def record(self, amount: Decimal) -> None:
        self.spent += amount
        self.executions += 1


@dataclass(slots=True)
class Execution:
    """What the agent actually did. The pair (Mandate, Execution) is the
    entire input to Head C.

    Scoring both halves matters. The hard checks catch AGT-001, 002, 008 and
    009. They do NOT catch DRV-013, where the purchase is inside every stated
    bound and merely wrong — that is what the soft half is for, and it is also
    the attack aimed at our own detector.
    """
    execution_id: str
    mandate_id: str
    agent_id: str
    ts: datetime
    amount: Decimal
    mcc: str
    merchant_id: str
    beneficiary: str
    item_description: str = ""            # what the agent believes it bought
    item_embedding: Optional[List[float]] = None

    def divergence_features(self, mandate: Mandate) -> Dict[str, float]:
        """Feature dict for Head C. Hard signals only — the semantic term is
        added by the detector, which owns the embedding model."""
        viol = mandate.scope_violations(self.amount, self.mcc,
                                        self.beneficiary, self.ts)
        ceiling_use = (float(mandate.spent + self.amount) /
                       float(mandate.ceiling)) if mandate.ceiling else 0.0
        return {
            "violation_count":     float(len(viol)),
            "ceiling_utilisation": ceiling_use,
            "mcc_in_scope":        0.0 if "mcc_out_of_scope" in viol else 1.0,
            "beneficiary_match":   0.0 if "beneficiary_mismatch" in viol else 1.0,
            "expired":             1.0 if "expired" in viol else 0.0,
            "execution_index":     float(mandate.executions),
            "is_open_mandate":     1.0 if mandate.is_open else 0.0,
            "seconds_since_issue": (
                (self.ts - mandate.capsule.issued_at).total_seconds()
                if mandate.capsule.issued_at else 0.0),
        }
