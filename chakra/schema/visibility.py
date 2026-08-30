"""Node visibility, made executable.

F15 in the figure spec is a table saying which fields our node can see. A table
is a promise. This module is the enforcement: any feature builder that reaches
for a field outside our declared position raises at construction time, so the
model physically cannot be trained on data that would not exist in production.

The failure this prevents is the commonest tell in hackathon fraud models — a
classifier using merchant-side device fingerprints alongside issuer-side
balance history, data that never coexists at any single node.
"""
from __future__ import annotations
from typing import Dict, Set, Iterable


NODE_FIELDS: Dict[str, Set[str]] = {
    # ---- what WE are ----------------------------------------------------
    "network": {
        "txn_id", "ts", "rail", "amount", "currency",
        "token_pan", "payer_vpa", "payee_vpa",
        "mcc", "merchant_id", "acquirer_id", "terminal_id",
        "pos_entry_mode", "country",
        "avs_result", "cvv2_result", "threeds_eci", "response_code",
        "agent_id", "mandate_id", "agent_token_id",
        "device_binding_id", "collect_request_id",
    },
    # ---- the other seats, for the comparison table ----------------------
    "issuer": {
        "txn_id", "ts", "rail", "amount", "currency", "token_pan",
        "mcc", "merchant_id", "acquirer_id", "pos_entry_mode", "country",
        "threeds_eci", "response_code",
        "account_balance", "credit_limit", "customer_tenure",
        "customer_age", "kyc_tier",
    },
    "merchant": {
        "txn_id", "ts", "amount", "currency", "mcc", "merchant_id",
        "avs_result", "cvv2_result", "response_code",
        "cart_contents", "session_id", "ip_address", "device_fingerprint",
        "user_agent", "email_address", "shipping_address",
    },
    "acquirer": {
        "txn_id", "ts", "amount", "currency", "mcc", "merchant_id",
        "acquirer_id", "terminal_id", "pos_entry_mode", "response_code",
        "merchant_settlement_account", "merchant_onboarding_path",
    },
}

OUR_NODE = "network"

# Fields we could technically emit but deliberately refuse to use, with the
# reason. Printed verbatim into F15 so the refusal is visible, not silent.
DELIBERATE_EXCLUSIONS: Dict[str, str] = {
    "device_fingerprint": "merchant-side only; never reaches the network on card rails",
    "ip_address":         "merchant-side only",
    "cart_contents":      "merchant-side only; not in ISO 8583 or 20022 auth",
    "account_balance":    "issuer-side only",
    "customer_age":       "issuer-side only, and using it would raise a fairness question we cannot answer at this node",
    "email_address":      "merchant-side only",
    "shipping_address":   "merchant-side only",
}


class VisibilityError(RuntimeError):
    pass


def assert_visible(features: Iterable[str], node: str = OUR_NODE) -> None:
    """Raise if any feature is not observable from `node`.

    Call this at the top of every feature builder. It is three lines and it
    removes an entire category of quiet cheating.
    """
    allowed = NODE_FIELDS.get(node)
    if allowed is None:
        raise VisibilityError(f"unknown node {node!r}")
    bad = sorted(set(features) - allowed)
    if bad:
        detail = "; ".join(
            f"{b} ({DELIBERATE_EXCLUSIONS[b]})" if b in DELIBERATE_EXCLUSIONS else b
            for b in bad)
        raise VisibilityError(
            f"{len(bad)} field(s) not observable at node {node!r}: {detail}")


def derived_ok(base_fields: Iterable[str], node: str = OUR_NODE) -> bool:
    """Aggregates are legal iff every field they are computed from is legal.
    Velocity counts over token_pan are fine; velocity over IP is not."""
    try:
        assert_visible(base_fields, node)
        return True
    except VisibilityError:
        return False


def comparison_table() -> str:
    """Renders F15 straight from the declarations above, so the document and
    the code cannot drift apart."""
    nodes = ["network", "issuer", "merchant", "acquirer"]
    every = sorted(set().union(*NODE_FIELDS.values()))
    out = ["| Field | " + " | ".join(n.title() for n in nodes) + " |",
           "|" + "---|" * (len(nodes) + 1)]
    for f in every:
        marks = ["●" if f in NODE_FIELDS[n] else "" for n in nodes]
        note = f"  \n*{DELIBERATE_EXCLUSIONS[f]}*" if f in DELIBERATE_EXCLUSIONS else ""
        out.append(f"| `{f}`{note} | " + " | ".join(marks) + " |")
    return "\n".join(out)
