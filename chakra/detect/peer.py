"""Head P — peer-relative intent.

WHY THIS HEAD EXISTS
--------------------
The obvious defence against a hijacked shopping agent is to check the money
went where the mandate said. It cannot be built, and finding that out is worth
stating plainly.

A user says "buy running shoes under Rs 6,000". They do not name a merchant —
choosing one is the whole point of delegating. In AP2 terms the user signs an
Intent Mandate, the agent then builds a Cart Mandate naming a specific merchant
and amount, and the payment settles against that cart. So:

    beneficiary on the wire  ==  beneficiary in the cart      always
    cart                     vs  intent                       is where it breaks

The manipulation happens upstream of the cart. By the time there is anything to
compare on an authorisation message, the wrong answer has already been signed
correctly. `beneficiary_match` is therefore not implementable as a hard check,
and any submission claiming it is has not looked closely at the protocol.

That leaves two things that can see the divergence: what the purchase MEANS
against the stated intent, and what comparable agents DID with the same
instruction. This head is the second one.

THE IDEA
--------
Our corpus holds 6,231 mandates. Hundreds of agents were handed comparable
instructions, and their executions form an empirical distribution. A poisoned
listing does not merely break a rule — it pushes the agent somewhere agents
given this instruction do not go.

So we score an execution against its peers rather than against a rule, which
needs no understanding of the text at all.

    q_k  =  F̂_c,k( observed_k )        empirical quantile within cluster c

The quantiles become an ordinary feature block. The existing weight-of-evidence
scorecard then learns which regions of the peer distribution are fraudulent,
so this drops into the same additive fusion as every other head with no special
handling.

NOTE ON HONESTY
---------------
The comparison set only exists because we simulated a population of agents
carrying out comparable mandates. A public dataset has no such thing, and
neither does a single bank's traffic in the early days of a rail. That is a
strength of the range and a limitation of the result, and it belongs in F16.
"""
from __future__ import annotations
import bisect
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple


@dataclass
class Execution:
    """One agent execution, reduced to the fields peers are compared on."""
    mandate_id: str
    cluster: str            # what the instruction asked for
    amount: float
    ceiling: float
    mcc: str
    hint_mcc: Optional[str]
    merchant: str
    issued_ts: float
    exec_ts: float


@dataclass
class PeerIndex:
    """Empirical distributions of what comparable mandates produced.

    Fitted on the TRAINING period only. Fitting on everything would let the
    attack define its own peer group, which is the same time-travel mistake as
    a random split, wearing a different hat.
    """
    min_cluster: int = 25

    # cluster -> sorted values, for empirical quantiles
    _amount_ratio: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))
    _time_to_exec: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))
    _item_sim: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))
    # cluster -> merchant -> how often peers chose it
    _merchant_pop: Dict[str, Dict[str, int]] = field(default_factory=lambda: defaultdict(lambda: defaultdict(int)))
    _mcc_match_rate: Dict[str, List[int]] = field(default_factory=lambda: defaultdict(list))
    _built: bool = False

    # ---- fit ---------------------------------------------------------
    def add(self, e: Execution, item_sim: Optional[float] = None) -> None:
        c = e.cluster
        self._amount_ratio[c].append(e.amount / max(1.0, e.ceiling))
        self._time_to_exec[c].append(max(0.0, e.exec_ts - e.issued_ts))
        self._merchant_pop[c][e.merchant] += 1
        self._mcc_match_rate[c].append(1 if (e.hint_mcc and e.mcc == e.hint_mcc) else 0)
        if item_sim is not None:
            self._item_sim[c].append(item_sim)

    def build(self) -> "PeerIndex":
        for d in (self._amount_ratio, self._time_to_exec, self._item_sim):
            for v in d.values():
                v.sort()
        self._built = True
        return self

    def size(self, cluster: str) -> int:
        return len(self._amount_ratio.get(cluster, ()))

    @property
    def clusters(self) -> List[str]:
        return sorted(self._amount_ratio)

    # ---- score -------------------------------------------------------
    @staticmethod
    def _quantile(sorted_vals: Sequence[float], x: float) -> float:
        if not sorted_vals:
            return 0.5
        i = bisect.bisect_left(sorted_vals, x)
        return i / len(sorted_vals)

    @staticmethod
    def _tail(q: float) -> float:
        """How far into a tail a quantile sits, as nats.

        A two-sided surprisal: 0 at the median, growing without bound at either
        edge. Bounded at 1e-4 so a single extreme value cannot dominate the sum.
        """
        p = 2.0 * min(max(q, 1e-4), 1.0 - 1e-4)
        p = min(p, 2.0 - p)
        return -math.log(max(1e-4, p))

    def features(self, e: Execution,
                 item_sim: Optional[float] = None) -> Dict[str, float]:
        """The peer block for one execution.

        `peer_support` says how many comparable executions the score rests on.
        Without it, an execution in a cluster of three would look wildly
        anomalous for no reason other than that we had nothing to compare it to
        — and the scorecard needs to be able to learn to distrust exactly that.
        """
        c = e.cluster
        n = self.size(c)
        if not self._built or n < self.min_cluster:
            # Not enough comparable executions to say anything. The head must be
            # able to learn to stay quiet here rather than treat a thin cluster
            # as evidence.
            return {'peer_seen': 0.0}

        ar = e.amount / max(1.0, e.ceiling)
        tt = max(0.0, e.exec_ts - e.issued_ts)
        q_amount = self._quantile(self._amount_ratio[c], ar)
        q_time = self._quantile(self._time_to_exec[c], tt)

        pop = self._merchant_pop[c]
        total = sum(pop.values()) or 1
        chosen = pop.get(e.merchant, 0)
        # share of peers who went to this merchant; 0 means nobody else did
        merch_share = chosen / total
        # rank among merchants peers used, normalised; 1.0 = never chosen
        ranked = sorted(pop.values(), reverse=True)
        rank = bisect.bisect_left([-v for v in ranked], -chosen) if chosen else len(ranked)
        merch_rank = rank / max(1, len(ranked))

        match_rate = (sum(self._mcc_match_rate[c]) / len(self._mcc_match_rate[c])
                      if self._mcc_match_rate[c] else 0.5)
        mcc_ok = 1.0 if (e.hint_mcc and e.mcc == e.hint_mcc) else 0.0

        # `peer_support` and `peer_distinct_merchants` are CLUSTER-LEVEL
        # CONSTANTS — identical for every execution in a cluster. Scored, they
        # act as a cluster identifier, and because our attack plugin always
        # used the same stated intent the model learned "this cluster is fraud"
        # and posted 0.97 PR-AUC on agentic. Their information value came back
        # at 4.3 and 4.2, the top two features in the head, which is what gave
        # it away.
        #
        # They are kept out of the scored block and returned separately, so the
        # head sees only quantities that describe THIS execution's position
        # relative to its peers.
        out = {
            'peer_seen': 1.0,
            'peer_amount_q': q_amount,
            'peer_amount_tail': self._tail(q_amount),
            'peer_time_q': q_time,
            'peer_time_tail': self._tail(q_time),
            'peer_merchant_share': merch_share,
            'peer_merchant_rank': merch_rank,
            'peer_merchant_unseen': 1.0 if chosen == 0 else 0.0,
            'peer_mcc_deviation': match_rate - mcc_ok,
        }

        if item_sim is not None and self._item_sim.get(c):
            q_sim = self._quantile(self._item_sim[c], item_sim)
            out['peer_item_sim_q'] = q_sim
            out['peer_item_sim_tail'] = self._tail(q_sim)

        return out


# ---------------------------------------------------------------------------
def cluster_of(stated_intent: str, hint_mcc: Optional[str]) -> str:
    """Which peer group an instruction belongs to.

    Exact category hint is the cheap first pass and it is honest about being
    one: a real deployment would cluster intent embeddings, and the fallback
    below keeps the head working when no hint was declared.
    """
    if hint_mcc:
        return f'mcc:{hint_mcc}'
    words = [w for w in (stated_intent or '').lower().split() if len(w) > 3]
    return 'txt:' + '_'.join(sorted(words)[:3]) if words else 'txt:unknown'


def _ts(v) -> float:
    """mandates.csv writes ISO timestamps; the loop passes epoch floats."""
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        from datetime import datetime
        return datetime.fromisoformat(v).timestamp()


def build_index(rows: Sequence[dict], cutoff_ts: float,
                min_cluster: int = 25) -> PeerIndex:
    """Fit from mandates.csv, using only executions before the cut-off.

    `rows` are dicts as written by run_attacks.py: mandate_id, agent_id,
    stated_intent, category_hint, ceiling, allowed_mccs, expiry_ts, issued_ts,
    exec_beneficiary, exec_amount, exec_ts.
    """
    idx = PeerIndex(min_cluster=min_cluster)
    for r in rows:
        try:
            issued = _ts(r['issued_ts'])
            ts = _ts(r['exec_ts'])
        except (KeyError, TypeError, ValueError):
            continue
        if ts > cutoff_ts:
            continue
        hint = r.get('category_hint') or None
        idx.add(Execution(
            mandate_id=r['mandate_id'],
            cluster=cluster_of(r.get('stated_intent', ''), hint),
            amount=float(r['exec_amount']),
            ceiling=float(r['ceiling']),
            mcc=(r.get('allowed_mccs') or '').split('|')[0] or '',
            hint_mcc=hint,
            merchant=r.get('exec_beneficiary', ''),
            issued_ts=issued,
            exec_ts=ts,
        ))
    return idx.build()
