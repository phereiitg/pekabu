"""The wire record.

Design rule: a field appears here only if the network node can actually
observe it on that rail. No customer name, no item-level basket, no browser
fingerprint, no IP. That absence is why velocity and graph features carry
nearly all the signal, and it is also what the fidelity work says synthetic
generators destroy.

Ground truth is NOT on this record. Labels live in labels.py and arrive late.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict, fields
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict

from .enums import (Rail, POSEntryMode, AVSResult, CVV2Result,
                    ThreeDSECI, ResponseCode)


@dataclass(slots=True)
class Transaction:
    # --- identity of the event -------------------------------------------
    txn_id: str
    ts: datetime                 # second resolution; see TICK_SECONDS
    rail: Rail

    # --- money -----------------------------------------------------------
    amount: Decimal
    currency: str = "INR"

    # --- the instrument --------------------------------------------------
    token_pan: Optional[str] = None      # network token, never a real PAN
    payer_vpa: Optional[str] = None      # UPI rails only
    payee_vpa: Optional[str] = None      # UPI rails only

    # --- the acceptance side ---------------------------------------------
    mcc: Optional[str] = None
    merchant_id: Optional[str] = None
    acquirer_id: Optional[str] = None
    terminal_id: Optional[str] = None

    # --- how it was presented --------------------------------------------
    pos_entry_mode: POSEntryMode = POSEntryMode.NOT_APPLIC
    country: str = "IN"

    # --- verification results (results, not the underlying data) ---------
    avs_result: AVSResult = AVSResult.NOT_REQUESTED
    cvv2_result: CVV2Result = CVV2Result.NOT_PRESENT
    threeds_eci: ThreeDSECI = ThreeDSECI.NOT_APPLICABLE

    # --- outcome ---------------------------------------------------------
    response_code: ResponseCode = ResponseCode.APPROVED

    # --- agentic rail only -----------------------------------------------
    agent_id: Optional[str] = None
    mandate_id: Optional[str] = None
    agent_token_id: Optional[str] = None

    # --- UPI only --------------------------------------------------------
    device_binding_id: Optional[str] = None   # real UPI primitive
    collect_request_id: Optional[str] = None  # R5 only

    def graph_keys(self) -> Dict[str, str]:
        """Rail-dependent linkage keys for the graph head.

        There is deliberately no universal `device_id`. At the network node a
        card authorisation carries no device fingerprint — that lives with the
        merchant. UPI genuinely carries device binding, so it appears there
        and only there. Pretending otherwise is the commonest hackathon tell.
        """
        k: Dict[str, str] = {}
        if self.rail in (Rail.CARD_PRESENT, Rail.CNP_HUMAN,
                         Rail.CNP_AGENTIC, Rail.TOKEN_RECURRING):
            if self.token_pan:   k["token"] = self.token_pan
            if self.merchant_id: k["merchant"] = self.merchant_id
            if self.acquirer_id: k["acquirer"] = self.acquirer_id
            if self.terminal_id: k["terminal"] = self.terminal_id
            if self.agent_id:    k["agent"] = self.agent_id
        elif self.rail in (Rail.UPI_PUSH, Rail.UPI_COLLECT):
            if self.payer_vpa:         k["payer_vpa"] = self.payer_vpa
            if self.payee_vpa:         k["payee_vpa"] = self.payee_vpa
            if self.device_binding_id: k["device"] = self.device_binding_id
        elif self.rail is Rail.WALLET_PPI:
            if self.token_pan:   k["instrument"] = self.token_pan
            if self.merchant_id: k["merchant"] = self.merchant_id
        return k

    def entity_id(self) -> str:
        """The stable payer-side handle used to group events for P1 and P2.

        Note for the write-up: our simulator knows this exactly. IEEE-CIS does
        not — there the partition must be reconstructed from
        card1 + addr1 + (date - D1), which is a heuristic. So the real-data
        noise floor is itself an estimate. That belongs in F16.
        """
        return self.token_pan or self.payer_vpa or "unknown"

    def to_row(self) -> dict:
        d = asdict(self)
        d["ts"] = self.ts.isoformat()
        d["amount"] = str(self.amount)
        for f in fields(self):
            v = d.get(f.name)
            if hasattr(v, "value"):
                d[f.name] = v.value
        return d

    @staticmethod
    def csv_header() -> list[str]:
        return [f.name for f in fields(Transaction)]


TICK_SECONDS = 60
"""One tick is one minute of world time. Events are placed at a random second
offset inside the tick, so inter-event times have real second-level jitter.
Without that, P1 lag-1 autocorrelation is an artifact of the tick grid rather
than of behaviour."""
