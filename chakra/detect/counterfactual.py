"""Counterfactual reasons.

WHY NOT JUST RANK THE TERMS
---------------------------
An additive score gives reason codes for free: sort the weight-of-evidence
terms and you have "what was odd about this". That is genuinely useful and it is
what most scorecards ship.

It is also the wrong shape for the person receiving it. An analyst holding a
declined transaction does not want a ranked list of oddities — they want to know
what would have to be different. So does a customer on the phone, and so does a
regulator asking why a decision went the way it did.

    ranked terms       beneficiary novelty  +1.70
                       ceiling utilisation  +0.31
                       merchant unseen      +0.28

    counterfactual     Declined. Would have been approved if the merchant were
                       one this agent has used before, OR if the amount were
                       under Rs 2,940.

HOW IT IS COMPUTED
------------------
The score is a sum of per-feature weights, and each weight is a lookup on which
bin the feature landed in. So flipping the decision means moving features to
better bins until the total drops below the threshold:

    z  =  logit(pi)  +  sum_j  WOE_j( bin_j )
    goal:  find the smallest set S with
           z  -  sum_{j in S} [ WOE_j(bin_j) - WOE_j(bin_j*) ]  <  tau

where bin_j* is the most-genuine bin available for feature j. Greedy by weight
saved is optimal here for the single-feature case and near-optimal for sets,
because the terms are independent by construction — the same additivity that
makes reason codes free makes this cheap.

WHAT IT WILL NOT DO
-------------------
It reports feature moves, not real-world actions. "Amount under Rs 2,940" is a
statement about the score surface, not advice. And a move to a bin the entity
could never occupy — an account age of two years on an account opened last week
— is arithmetically valid and practically meaningless, so features that cannot
be acted on are excluded rather than dressed up.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from chakra.detect.features import FeatureSet
from chakra.detect.heads import Head, Fusion, _bin_of


#: Features an entity could plausibly differ on. Everything else describes
#: history that cannot be changed after the fact, and offering it as a
#: counterfactual would be noise dressed as an explanation.
ACTIONABLE = {
    'log_amount', 'amt_over_median', 'n_1h', 'n_24h',
    'distinct_mcc_24h', 'distinct_mer_24h', 'new_merchant', 'log_gap',
    'burst_ratio', 'gap_vs_own_median',
    'device_fanout', 'payee_fanout', 'max_key_fanout', 'ring_cohesion',
    'ceiling_utilisation', 'mcc_out_of_scope', 'expired', 'over_ceiling',
    'category_matches_intent', 'intent_similarity', 'intent_margin',
    'peer_merchant_share', 'peer_merchant_rank', 'peer_merchant_unseen',
    'peer_amount_q', 'peer_mcc_deviation',
}

#: How to say a feature out loud.
PHRASING = {
    'log_amount':              ('the amount were lower', 'amount'),
    'amt_over_median':         ('the amount were closer to this account\u2019s usual', 'amount'),
    'n_1h':                    ('there were fewer transactions in the last hour', 'velocity'),
    'n_24h':                   ('there were fewer transactions today', 'velocity'),
    'burst_ratio':             ('this were not part of a burst', 'velocity'),
    'gap_vs_own_median':       ('the timing matched this account\u2019s rhythm', 'velocity'),
    'distinct_mcc_24h':        ('fewer merchant categories were touched today', 'velocity'),
    'distinct_mer_24h':        ('fewer merchants were touched today', 'velocity'),
    'new_merchant':            ('this merchant had been used before', 'novelty'),
    'log_gap':                 ('more time had passed since the last payment', 'velocity'),
    'device_fanout':           ('fewer accounts shared this device', 'graph'),
    'payee_fanout':            ('fewer payers had paid this payee', 'graph'),
    'max_key_fanout':          ('this were not on a heavily shared key', 'graph'),
    'ring_cohesion':           ('these counterparties were not interlinked', 'graph'),
    'ceiling_utilisation':     ('less of the mandate ceiling were used', 'mandate'),
    'over_ceiling':            ('the amount were inside the ceiling', 'mandate'),
    'mcc_out_of_scope':        ('the category were inside the mandate', 'mandate'),
    'expired':                 ('the mandate had not expired', 'mandate'),
    'category_matches_intent': ('the category matched what was asked for', 'intent'),
    'intent_similarity':       ('the purchase matched the stated intent', 'intent'),
    'intent_margin':           ('the purchase were typical for this agent', 'intent'),
    'peer_merchant_share':     ('this merchant were one comparable agents use', 'peer'),
    'peer_merchant_rank':      ('this merchant were a common choice for this instruction', 'peer'),
    'peer_merchant_unseen':    ('any comparable agent had used this merchant', 'peer'),
    'peer_amount_q':           ('the amount were typical for this instruction', 'peer'),
    'peer_mcc_deviation':      ('the category matched what peers chose', 'peer'),
}


@dataclass
class Move:
    feature: str
    head: str
    family: str
    phrase: str
    saved: float          # log-odds removed by making this move
    observed: float       # the value it actually had
    target: float         # a representative value in the best bin


@dataclass
class Counterfactual:
    flipped: bool
    z: float
    tau: float
    gap: float                    # how much log-odds had to be removed
    singles: List[Move]           # any one of these alone would have flipped it
    combination: List[Move]       # the smallest set that does, if none alone can
    considered: int

    def sentence(self, decision: str = 'Declined') -> str:
        if not self.singles and not self.combination:
            return f'{decision}. No single feature change would have flipped this.'
        if self.singles:
            parts = [m.phrase for m in self.singles[:3]]
            joined = parts[0] if len(parts) == 1 else \
                ', or '.join([', '.join(parts[:-1]), parts[-1]])
            return f'{decision}. Would have been approved if {joined}.'
        parts = [m.phrase for m in self.combination]
        joined = ' and '.join([', '.join(parts[:-1]), parts[-1]]) if len(parts) > 1 else parts[0]
        return (f'{decision}. No single change flips it — would have needed '
                f'{joined} together.')


def explain(fs: FeatureSet, fusion: Fusion, heads: Sequence[Head],
            tau: float, max_terms: int = 4) -> Counterfactual:
    """Minimum-cost perturbation over the score surface.

    Returns single-feature flips where any one alone would have been enough,
    and otherwise the smallest greedy set. Both are useful and they answer
    different questions: the first is what to tell a customer, the second is
    what to tell an analyst about how far from the line the decision sat.
    """
    z = fusion.prob(fs)
    if z <= tau:
        return Counterfactual(False, z, tau, 0.0, [], [], 0)

    gap = z - tau
    moves: List[Move] = []

    for hd in heads:
        if not hd.trained or not hd.applicable(fs):
            continue
        a, _b = fusion.cal.get(hd.name, (1.0, 0.0))
        blk = fs.block(hd.block)
        for f, edges in hd.edges.items():
            if f not in blk or f not in ACTIONABLE:
                continue
            w = hd.woe.get(f, {})
            if not w:
                continue
            here = _bin_of(blk[f], edges)
            now_w = w.get(here, 0.0)
            best_bin = min(w, key=w.get)
            best_w = w[best_bin]
            # scaled by the head's Platt slope, because that is what actually
            # reaches the fused score
            saved = (now_w - best_w) * abs(a)
            if saved <= 1e-6:
                continue
            lo = edges[best_bin - 1] if 0 < best_bin <= len(edges) else (
                edges[0] if edges else blk[f])
            phrase, family = PHRASING.get(f, (f'{f} were different', 'other'))
            moves.append(Move(f, hd.name, family, phrase, saved, blk[f], lo))

    moves.sort(key=lambda m: -m.saved)
    singles = [m for m in moves if m.saved >= gap][:max_terms]

    combination: List[Move] = []
    if not singles:
        acc = 0.0
        seen_family = set()
        for m in moves:
            # one move per family, so we do not tell someone to change three
            # different velocity counters that all say the same thing
            if m.family in seen_family:
                continue
            combination.append(m)
            seen_family.add(m.family)
            acc += m.saved
            if acc >= gap or len(combination) >= max_terms:
                break
        if acc < gap:
            combination = []

    return Counterfactual(True, z, tau, gap, singles, combination, len(moves))
