"""Routed detector portfolio.

The argument, stated before any number is reported:

A single fused classifier averages away specialisation. Phase 6 measured it —
Head C scores 0.677 PR-AUC on agentic fraud alone, and the A+B+C fusion scores
0.475 on the same subset. The fusion is worse than its own best component,
because the heads that are useless on that subset still contribute variance.

Real payment systems do not work that way. They route. So we route.

THREE RULES, and they are what separate this from choosing whichever number
looks best.

1. ROUTES ARE KEYED ON OBSERVABLE FIELDS ONLY.
   Not on trust link, not on attack family, not on anything that is a label.
   The router sees exactly what an authorisation message carries: the rail,
   whether an agent id is present, whether a mandate id is present. Every
   routing decision is reproducible at decision time in production.

2. ROUTES ARE DECLARED FROM STRUCTURE, BEFORE MEASUREMENT.
   The rail taxonomy was fixed in Phase 1 and the transaction schema in Phase
   2, both before any detector existed. The routes below follow from the
   four-party model and the chargeback property, not from inspecting scores.

3. EVERY CELL IS REPORTED.
   The output is a complete route x head matrix. Some cells are terrible. A
   table with holes in it is cherry-picking; a complete table with bad entries
   is a finding about which problems are hard.

Per-route conformal budgets follow from the same logic. A bank does not spend
the same friction on a small grocery tap and a delegated agent transfer, and
one quantile over the mixture holds the budget for neither.
"""
from __future__ import annotations
import math
import statistics as st
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from chakra.detect.features import FeatureSet
from chakra.detect.heads import Head, Fusion, ConformalBudget, CostModel


# ---------------------------------------------------------------------------
def route_of(fs: FeatureSet, has_agent: bool = False,
             has_mandate: bool = False) -> str:
    """The router. Observable fields only.

    Deliberately boring: three boolean checks on fields that appear on the
    wire. Anything cleverer would be harder to justify to an issuer and
    impossible to reproduce at decision time.
    """
    # Route on an INTRINSIC property of the FeatureSet. Block C is populated
    # only for agentic transactions, so its presence IS the agent signal and
    # it travels with the object.
    #
    # The previous version looked has_agent up in a dict keyed by txn_id and
    # built from the current batch. In the loop, where the defender remembers
    # rows from earlier rounds, every remembered agentic row fell out of that
    # dict and was silently misrouted to card or push. The agentic route then
    # never trained, Head C was never available, and AGT-004 and AGT-008
    # escaped at 100% in every iteration while the same attacks scored 98%
    # recall in the single-shot run. The discrepancy between those two numbers
    # is what exposed it.
    if has_agent or bool(fs.C):
        return "agentic"
    if fs.rail in ("R4", "R5"):
        return "push"
    if fs.rail == "R6":
        return "recurring"
    return "card"


ROUTE_RATIONALE = {
    "agentic":   ("agent_id present",
                  "Every authentication factor passes by design. The token is "
                  "the auth artifact, the mandate is signed, the history is "
                  "clean. There is no anomaly, so an anomaly detector has "
                  "nothing to find. Intent divergence is the only signal."),
    "push":      ("rail in {R4, R5}",
                  "No chargeback, so the decision must happen before "
                  "authorisation and there is no recourse afterwards. The "
                  "victim authorised it, so the signal is not in the "
                  "transaction but in the beneficiary's position in the graph."),
    "card":      ("rail in {R1, R2}",
                  "Classic pull-rail fraud with chargeback recourse. Velocity "
                  "and decline structure work here, and the literature is "
                  "thirty years deep. We do not need to be clever."),
    "recurring": ("rail == R6",
                  "A standing authorisation is a dormant attack surface, and "
                  "RBI exempts recurring payments from both proposed "
                  "safeguards. Drift over time is the risk, not any single "
                  "transaction."),
}

#: Which heads each route is allowed to use. Declared, not learned.
ROUTE_HEADS = {
    "agentic":   ["C_intent", "P_peer", "A_behavioural"],
    "push":      ["B_graph", "A_behavioural"],
    "card":      ["A_behavioural", "B_graph"],
    "recurring": ["C_intent", "P_peer", "A_behavioural"],
}

#: Per-route friction budget. Different populations, different costs.
ROUTE_ALPHA = {
    "agentic":   0.05,   # delegation is high-value and low-volume
    "push":      0.02,   # irreversible, so friction is worth more
    "card":      0.005,  # high volume, false declines cost the relationship
    "recurring": 0.02,
}


# ---------------------------------------------------------------------------
@dataclass
class RouteModel:
    name: str
    fusion: Optional[Fusion] = None
    budget: Optional[ConformalBudget] = None
    n_train: int = 0
    n_fraud: int = 0
    trained: bool = False

    def score(self, fs: FeatureSet) -> float:
        if not self.trained or self.fusion is None:
            return 0.0
        return self.fusion.prob(fs)

    def flags(self, fs: FeatureSet) -> bool:
        if self.budget is None:
            return False
        return self.score(fs) > self.budget.threshold(fs.rail)


@dataclass
class Portfolio:
    """A detector per route, each with its own budget."""
    routes: Dict[str, RouteModel] = field(default_factory=dict)
    router: object = None

    def fit(self, rows: List[FeatureSet], y: Sequence[int],
            heads: Dict[str, Head], route_fn,
            cal_rows: Optional[List[FeatureSet]] = None,
            cal_y: Optional[Sequence[int]] = None) -> "Portfolio":
        """Fit a specialist per route.

        `cal_rows` is a HELD-OUT slice used only to set the conformal
        threshold. Split conformal guarantees coverage for data exchangeable
        with the calibration set, and training-period scores are not
        exchangeable with later traffic because the model has seen them. Fitting
        both on the same slice put every threshold too high — the push route
        ranked mule farms at 0.67 PR-AUC and caught none of them. When no
        calibration slice is supplied we fall back to the training genuine
        scores and the guarantee is nominal only.
        """
        by: Dict[str, List[int]] = defaultdict(list)
        for i, r in enumerate(rows):
            by[route_fn(r)].append(i)

        for rname, idx in by.items():
            allowed = ROUTE_HEADS.get(rname, list(heads))
            sub_rows = [rows[i] for i in idx]
            sub_y = [y[i] for i in idx]
            rm = RouteModel(name=rname, n_train=len(idx), n_fraud=sum(sub_y))
            if len(idx) < 60 or len(set(sub_y)) < 2:
                # Not enough signal to fit a specialist. Say so rather than
                # fitting one anyway and reporting its noise as a result.
                self.routes[rname] = rm
                continue
            hs = [heads[h] for h in allowed if h in heads and heads[h].trained]
            fus = Fusion(hs).fit_prior(sub_y).calibrate(sub_rows, sub_y)

            if cal_rows is not None and cal_y is not None:
                cs = [(r, lab) for r, lab in zip(cal_rows, cal_y)
                      if route_fn(r) == rname and not lab]
                genuine = [fus.prob(r) for r, _ in cs]
                rails = [r.rail for r, _ in cs]
                if len(genuine) < 40:      # too thin to calibrate on
                    genuine = [fus.prob(r) for r, lab in zip(sub_rows, sub_y) if not lab]
                    rails = [r.rail for r, lab in zip(sub_rows, sub_y) if not lab]
            else:
                genuine = [fus.prob(r) for r, lab in zip(sub_rows, sub_y) if not lab]
                rails = [r.rail for r, lab in zip(sub_rows, sub_y) if not lab]
            bud = ConformalBudget(alpha=ROUTE_ALPHA.get(rname, 0.02))
            if genuine:
                bud.fit(genuine, rails)
            rm.fusion, rm.budget, rm.trained = fus, bud, True
            self.routes[rname] = rm
        return self

    def score(self, fs: FeatureSet, route_fn) -> Tuple[str, float, bool]:
        r = route_fn(fs)
        m = self.routes.get(r)
        if m is None or not m.trained:
            return r, 0.0, False
        return r, m.score(fs), m.flags(fs)

    def total_friction(self, rows: List[FeatureSet], y: Sequence[int],
                       route_fn) -> float:
        """Observed step-up rate on genuine traffic across all routes.

        Reported so the portfolio and the monolith can be compared at EQUAL
        friction. Comparing them at different friction would be meaningless,
        and it is the comparison most people make.
        """
        gen = [(r, route_fn(r)) for r, lab in zip(rows, y) if not lab]
        if not gen:
            return float("nan")
        hit = 0
        for r, rn in gen:
            m = self.routes.get(rn)
            if m and m.trained and m.flags(r):
                hit += 1
        return hit / len(gen)
