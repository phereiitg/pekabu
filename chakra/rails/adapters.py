"""Rail adapters.

Each adapter turns an abstract world event into a record on one rail, and the
discipline is that it may only populate fields that rail genuinely carries.
This is where the "we know how payments work" claim is either earned or lost.

Card authorisations follow ISO 8583 field semantics: DE2 PAN (tokenised here),
DE4 amount, DE18 MCC, DE22 POS entry mode, DE41 terminal, DE42 merchant,
DE39 response code, plus the CNP enrichment fields (AVS, CVV2, 3DS ECI).

UPI carries a different and much smaller set: payer and payee VPA, device
binding, amount, and for collect requests the request identifier. There is no
AVS, no CVV2, no ECI, and critically no chargeback.
"""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Optional
import random

from chakra.schema.enums import (Rail, POSEntryMode, AVSResult, CVV2Result,
                          ThreeDSECI, ResponseCode)
from chakra.schema.transaction import Transaction


# ---------------------------------------------------------------------------
def _response(rng: random.Random, amount: Decimal, decline_rate: float
              ) -> ResponseCode:
    """Not everything approves. A stream that is 100% approved is an
    immediate tell, and decline mix is also what P4 velocity-rule trigger
    rates are measured against."""
    if rng.random() > decline_rate:
        return ResponseCode.APPROVED
    return rng.choices(
        [ResponseCode.INSUFFICIENT_FUNDS, ResponseCode.DO_NOT_HONOR,
         ResponseCode.EXCEEDS_LIMIT, ResponseCode.EXPIRED_CARD,
         ResponseCode.SCA_REQUIRED],
        weights=[0.46, 0.24, 0.14, 0.09, 0.07])[0]


# ---------------------------------------------------------------------------
def card_auth(txn_id: str, ts: datetime, amount: Decimal, *,
              token_pan: str, merchant_id: str, mcc: str, acquirer_id: str,
              rng: random.Random,
              present: bool = False,
              agent_id: Optional[str] = None,
              mandate_id: Optional[str] = None,
              agent_token_id: Optional[str] = None,
              terminal_id: Optional[str] = None,
              country: str = "IN",
              decline_rate: float = 0.062) -> Transaction:
    if present:
        rail = Rail.CARD_PRESENT
        entry = (POSEntryMode.CONTACTLESS if rng.random() < 0.55
                 else POSEntryMode.CHIP)
        avs, cvv, eci = (AVSResult.NOT_REQUESTED, CVV2Result.NOT_PRESENT,
                         ThreeDSECI.NOT_APPLICABLE)
    elif agent_id:
        rail = Rail.CNP_AGENTIC
        entry = POSEntryMode.TOKEN
        # the agentic token is itself the authentication artifact, so 3DS is
        # not stepped up — which is precisely why agentic fraud carries no
        # authentication anomaly
        avs = AVSResult.FULL_MATCH
        cvv = CVV2Result.NOT_PRESENT
        eci = ThreeDSECI.AUTHENTICATED
    else:
        rail = Rail.CNP_HUMAN
        entry = POSEntryMode.ECOMMERCE
        avs = rng.choices(
            [AVSResult.FULL_MATCH, AVSResult.ZIP_ONLY, AVSResult.ADDRESS_ONLY,
             AVSResult.NO_MATCH, AVSResult.UNAVAILABLE],
            weights=[0.78, 0.08, 0.05, 0.04, 0.05])[0]
        cvv = rng.choices(
            [CVV2Result.MATCH, CVV2Result.NO_MATCH, CVV2Result.NOT_PROCESSED],
            weights=[0.94, 0.03, 0.03])[0]
        eci = rng.choices(
            [ThreeDSECI.AUTHENTICATED, ThreeDSECI.ATTEMPTED,
             ThreeDSECI.NOT_AUTHENTICATED],
            weights=[0.71, 0.16, 0.13])[0]

    return Transaction(
        txn_id=txn_id, ts=ts, rail=rail, amount=amount,
        token_pan=token_pan, mcc=mcc, merchant_id=merchant_id,
        acquirer_id=acquirer_id,
        terminal_id=terminal_id if present else None,
        pos_entry_mode=entry, country=country,
        avs_result=avs, cvv2_result=cvv, threeds_eci=eci,
        response_code=_response(rng, amount, decline_rate),
        agent_id=agent_id, mandate_id=mandate_id,
        agent_token_id=agent_token_id)


# ---------------------------------------------------------------------------
def upi_push(txn_id: str, ts: datetime, amount: Decimal, *,
             payer_vpa: str, payee_vpa: str, device_binding_id: str,
             rng: random.Random,
             mcc: Optional[str] = None, merchant_id: Optional[str] = None,
             acquirer_id: Optional[str] = None,
             decline_rate: float = 0.041) -> Transaction:
    """Payer initiates and authenticates with device binding plus PIN.

    Note what is absent: no AVS, no CVV2, no ECI, no chargeback. The payer
    authorised it, so every control passed. That is why most UPI fraud is
    authorised-but-unintended rather than a system breach, and why detection
    has to happen before authorisation rather than after.
    """
    return Transaction(
        txn_id=txn_id, ts=ts, rail=Rail.UPI_PUSH, amount=amount,
        payer_vpa=payer_vpa, payee_vpa=payee_vpa,
        device_binding_id=device_binding_id,
        mcc=mcc, merchant_id=merchant_id, acquirer_id=acquirer_id,
        pos_entry_mode=POSEntryMode.NOT_APPLIC,
        response_code=_response(rng, amount, decline_rate))


def upi_collect(txn_id: str, ts: datetime, amount: Decimal, *,
                payer_vpa: str, payee_vpa: str, device_binding_id: str,
                collect_request_id: str, rng: random.Random,
                mcc: Optional[str] = None, merchant_id: Optional[str] = None,
                acquirer_id: Optional[str] = None,
                decline_rate: float = 0.24) -> Transaction:
    """The payee requests, the payer approves.

    A debit dressed as a credit — the attack primitive behind UPI-006. Decline
    rate is far higher than push because most collect requests are simply
    ignored, and that asymmetry is itself a detectable signal.
    """
    return Transaction(
        txn_id=txn_id, ts=ts, rail=Rail.UPI_COLLECT, amount=amount,
        payer_vpa=payer_vpa, payee_vpa=payee_vpa,
        device_binding_id=device_binding_id,
        collect_request_id=collect_request_id,
        mcc=mcc, merchant_id=merchant_id, acquirer_id=acquirer_id,
        pos_entry_mode=POSEntryMode.NOT_APPLIC,
        response_code=_response(rng, amount, decline_rate))
