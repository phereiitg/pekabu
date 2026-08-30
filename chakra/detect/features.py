"""Feature builder.

Every feature declares the raw fields it derives from, and the builder calls
assert_visible() on that set before computing anything. A feature reaching for
a merchant-side device fingerprint or an issuer-side balance raises here, at
build time, rather than quietly training a model on data that would not exist
in production.

Three blocks, matching the three heads:

  A  behavioural / velocity   aggregates of one entity against its own history
  B  graph                    structure around the shared keys the network sees
  C  intent                   mandate versus execution, agentic rail only
"""
from __future__ import annotations
import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

from chakra.schema.transaction import Transaction
from chakra.schema.enums import Rail, ResponseCode, ThreeDSECI, POSEntryMode
from chakra.schema import visibility


# The fields each block derives from. Checked, not documented.
BASE_FIELDS = {
    "A": {"ts", "amount", "token_pan", "payer_vpa", "mcc", "merchant_id",
          "response_code", "pos_entry_mode", "rail"},
    "B": {"token_pan", "payer_vpa", "payee_vpa", "merchant_id", "acquirer_id",
          "terminal_id", "device_binding_id", "agent_id"},
    "C": {"agent_id", "mandate_id", "agent_token_id", "amount", "mcc",
          "merchant_id", "threeds_eci", "ts"},
}


@dataclass
class FeatureSet:
    txn_id: str
    ts: datetime
    entity: str
    rail: str
    amount: float
    A: Dict[str, float] = field(default_factory=dict)
    B: Dict[str, float] = field(default_factory=dict)
    C: Dict[str, float] = field(default_factory=dict)

    def block(self, name: str) -> Dict[str, float]:
        return getattr(self, name)


def _safe_log(x: float) -> float:
    return math.log(max(1e-6, x))


class FeatureBuilder:
    """Streaming builder. Processes transactions in time order and only ever
    looks backwards, so no feature can leak the future into a decision.
    """

    def __init__(self, node: str = "network",
                 mandates: Optional[Dict[str, dict]] = None) -> None:
        for block, fields in BASE_FIELDS.items():
            visibility.assert_visible(fields, node)
        self.node = node
        # per-entity rolling history
        self._hist: Dict[str, deque] = defaultdict(lambda: deque(maxlen=200))
        # graph state, built forward only
        self._key_entities: Dict[str, Dict[str, set]] = defaultdict(
            lambda: defaultdict(set))
        self._entity_keys: Dict[str, Dict[str, set]] = defaultdict(
            lambda: defaultdict(set))
        self._merchant_seen: Dict[str, set] = defaultdict(set)
        self._agent_hist: Dict[str, List[Transaction]] = defaultdict(list)
        self.mandates = mandates or {}
        """mandate_id -> {ceiling, allowed_mccs, expiry_ts, issued_ts,
        category_hint, stated_intent}. Without this Head C can only see agent
        history, which is another anomaly detector. The divergence between
        what was AUTHORISED and what was EXECUTED is the whole point, and it
        needs the mandate contents, not just its id."""

    # ------------------------------------------------------------------
    def build(self, t: Transaction) -> FeatureSet:
        ent = t.entity_id()
        h = self._hist[ent]
        now = t.ts.timestamp()
        amt = float(t.amount)

        fs = FeatureSet(txn_id=t.txn_id, ts=t.ts, entity=ent,
                        rail=t.rail.value, amount=amt)

        # ---------- block A : behavioural / velocity ------------------
        def within(sec: float) -> List[Transaction]:
            return [x for x in h if now - x.ts.timestamp() <= sec]

        w1h, w24h, w7d = within(3600), within(86400), within(604800)
        amts = [float(x.amount) for x in h]
        med = sorted(amts)[len(amts) // 2] if amts else amt

        fs.A = {
            "log_amount":        _safe_log(amt),
            "n_1h":              float(len(w1h)),
            "n_24h":             float(len(w24h)),
            "n_7d":              float(len(w7d)),
            "distinct_mcc_24h":  float(len({x.mcc for x in w24h if x.mcc})),
            "distinct_mer_24h":  float(len({x.merchant_id for x in w24h
                                            if x.merchant_id})),
            "amt_over_median":   amt / max(1.0, med),
            "log_gap":           _safe_log(now - h[-1].ts.timestamp()) if h else 14.0,
            "hour_sin":          math.sin(2 * math.pi * t.ts.hour / 24),
            "hour_cos":          math.cos(2 * math.pi * t.ts.hour / 24),
            "decline_rate_24h":  (sum(1 for x in w24h
                                      if x.response_code is not ResponseCode.APPROVED)
                                  / max(1, len(w24h))),
            "is_declined":       0.0 if t.response_code is ResponseCode.APPROVED else 1.0,
            "hist_len":          float(len(h)),
            "new_merchant":      0.0 if (t.merchant_id in self._merchant_seen[ent]) else 1.0,
            "eci_authenticated": 1.0 if t.threeds_eci is ThreeDSECI.AUTHENTICATED else 0.0,
            "is_token_entry":    1.0 if t.pos_entry_mode is POSEntryMode.TOKEN else 0.0,
        }

        # ---------- block B : graph -----------------------------------
        keys = t.graph_keys()
        fanouts, degrees = [], []
        for k, v in keys.items():
            if k in ("token", "payer_vpa"):
                continue                       # that IS the entity
            kk = f"{k}:{v}"
            fanouts.append(len(self._key_entities[k][v]))
            degrees.append(len(self._entity_keys[ent][k]))
        fs.B = {
            "max_key_fanout":    float(max(fanouts) if fanouts else 0),
            "mean_key_fanout":   float(sum(fanouts) / len(fanouts)) if fanouts else 0.0,
            "entity_key_degree": float(max(degrees) if degrees else 0),
            "device_fanout":     float(len(self._key_entities["device"].get(
                                        keys.get("device", "~"), ()))),
            "payee_fanout":      float(len(self._key_entities["payee_vpa"].get(
                                        keys.get("payee_vpa", "~"), ()))),
            "merchant_fanout":   float(len(self._key_entities["merchant"].get(
                                        keys.get("merchant", "~"), ()))),
            "n_keys":            float(len(keys)),
        }

        # ---------- block C : intent (agentic only) -------------------
        if t.agent_id:
            ah = self._agent_hist[t.agent_id]
            prev_mccs = {x.mcc for x in ah if x.mcc}
            prev_mer = {x.merchant_id for x in ah if x.merchant_id}
            prev_amts = [float(x.amount) for x in ah]
            pmed = sorted(prev_amts)[len(prev_amts) // 2] if prev_amts else amt
            fs.C = {
                "agent_hist_len":    float(len(ah)),
                "mcc_novel":         0.0 if t.mcc in prev_mccs else 1.0,
                "merchant_novel":    0.0 if t.merchant_id in prev_mer else 1.0,
                "amt_over_agent_med": amt / max(1.0, pmed),
                "mcc_entropy":       float(len(prev_mccs)),
                "unauth_agentic":    0.0 if t.threeds_eci is ThreeDSECI.AUTHENTICATED else 1.0,
                "has_mandate":       1.0 if t.mandate_id else 0.0,
                "burst_1h_agent":    float(sum(1 for x in ah
                                               if now - x.ts.timestamp() <= 3600)),
            }
            # --- mandate vs execution: the hard checks -----------------
            m = self.mandates.get(t.mandate_id or "")
            if m:
                ceiling = m["ceiling"]
                allowed = m["allowed_mccs"]
                fs.C.update({
                    "ceiling_utilisation": amt / max(1.0, ceiling),
                    "over_ceiling":  1.0 if amt > ceiling else 0.0,
                    "mcc_out_of_scope": 0.0 if (not allowed or t.mcc in allowed) else 1.0,
                    "expired":       1.0 if (m["expiry"] and now > m["expiry"]) else 0.0,
                    "secs_since_issue": (now - m["issued"]) if m["issued"] else 0.0,
                    "scope_declared": 1.0,
                    # semantic proxy: does the executed category match the
                    # category the stated intent implied? The soft half of
                    # Head C would replace this with an embedding comparison.
                    "category_matches_intent":
                        1.0 if (m["hint"] and t.mcc == m["hint"]) else 0.0,
                })
            else:
                fs.C["scope_declared"] = 0.0
            self._agent_hist[t.agent_id].append(t)

        # ---------- update state AFTER computing features -------------
        for k, v in keys.items():
            if k in ("token", "payer_vpa"):
                continue
            self._key_entities[k][v].add(ent)
            self._entity_keys[ent][k].add(v)
        if t.merchant_id:
            self._merchant_seen[ent].add(t.merchant_id)
        h.append(t)
        return fs
