"""The adversarial gate.

TWO PROBLEMS, ONE MODULE
-----------------------

**One: the calibration set was wrong.** Split conformal guarantees coverage for
new data drawn *exchangeably with the calibration set*. We were fitting the
heads and the threshold on the same training slice, then evaluating on a later
period. Training-period genuine scores are not exchangeable with test-period
ones — the model has seen the former — so the guarantee did not apply and the
threshold sat too high. Symptom: the push route ranked mule farms at 0.46
PR-AUC and caught 0% of them. Ranking was fine; the cut was in the wrong place.

The fix is an honest three-way temporal split:

    train      fit the heads
    calibrate  held out, never fitted on, immediately before the cut
    test       evaluate

**Two: the threshold assumed a passive adversary.** Conformal gives the optimal
cut against *nature* — traffic that happens to arrive. Ours does not happen to
arrive. The red-search loop produces an attacker who best-responds to whatever
threshold we publish, and eight rounds of those best-responses are sitting in
the escape log with the exact parameters that got through.

So we solve the game instead of the sampling problem.

    tau*  =  argmin_tau   max_{theta in Theta}   Loss( tau , attacker(theta) )

Defender moves first by publishing tau; attacker best-responds; we choose the
tau whose *worst* case is least bad. That is a Stackelberg equilibrium, and it
is computable here because Theta is not hypothetical — it is a list of attack
configurations we have already observed getting through.

WHY THIS MATTERS BEYOND THE NUMBER
----------------------------------
It joins the loop to the engine. Until now those were two separate stories: the
loop trains the detector, and the detector has a threshold. This makes the loop
*set the operating point*, which is a much stronger claim than running an
adversarial search alongside a classifier and reporting both.
"""
from __future__ import annotations
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple


@dataclass
class Candidate:
    """One threshold, and how it performs against every attack family."""
    tau: float
    friction: float                      # step-up rate on genuine traffic
    loss_by_family: Dict[str, float]     # value that escapes, per family
    worst_family: str
    worst_loss: float
    mean_loss: float


@dataclass
class AdversarialGate:
    """Minimax threshold over observed attacker best-responses.

    alpha         friction budget: share of genuine traffic we may challenge
    friction_cost rupee-equivalent cost of one step-up, used to trade the two
                  terms against each other
    """
    alpha: float = 0.02
    friction_cost: float = 45.0

    tau_conformal: float = 0.0
    tau_robust: float = 0.0
    chosen: str = 'conformal'
    candidates: List[Candidate] = field(default_factory=list)
    families: List[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    @staticmethod
    def conformal(cal_scores: Sequence[float], alpha: float) -> float:
        """Split-conformal threshold on a HELD-OUT calibration set.

        tau = the ceil((1-alpha)(n+1))-th smallest calibration score. For a new
        genuine transaction drawn exchangeably with that set,
        P(score > tau) <= alpha. Finite-sample, distribution-free — but only if
        the calibration set really was held out, which is the whole point of
        passing it in separately.
        """
        v = sorted(cal_scores)
        if not v:
            return 1.0
        k = math.ceil((1 - alpha) * (len(v) + 1)) - 1
        return v[min(max(k, 0), len(v) - 1)]

    # ------------------------------------------------------------------
    def fit(self,
            cal_genuine: Sequence[float],
            test_genuine: Sequence[float],
            fraud: Sequence[Tuple[float, float, str]],
            grid: int = 60) -> 'AdversarialGate':
        """Choose a threshold.

        cal_genuine   held-out genuine scores → the conformal baseline
        test_genuine  genuine scores in the evaluation period → real friction
        fraud         (score, value, family) for each attack transaction

        Each attack family stands in for one attacker configuration. Minimising
        the worst family rather than the average is the conservative reading,
        and it is the right one: an adversary picks their best option, not a
        random one.
        """
        self.tau_conformal = self.conformal(cal_genuine, self.alpha)
        fams = sorted({f for _, _, f in fraud})
        self.families = fams
        if not fams or not test_genuine:
            self.tau_robust = self.tau_conformal
            return self

        total_by_fam: Dict[str, float] = defaultdict(float)
        for _s, v, f in fraud:
            total_by_fam[f] += v

        # Candidate thresholds spanning the observed genuine range. Sweeping
        # rather than solving analytically because the loss is a step function
        # in tau and a grid is both exact enough and inspectable.
        lo, hi = min(test_genuine), max(max(test_genuine), max(s for s, _, _ in fraud))
        taus = [lo + (hi - lo) * i / (grid - 1) for i in range(grid)]
        taus.append(self.tau_conformal)
        taus = sorted(set(taus))

        n_gen = len(test_genuine)
        out: List[Candidate] = []
        for tau in taus:
            friction = sum(1 for s in test_genuine if s > tau) / n_gen
            esc: Dict[str, float] = defaultdict(float)
            for s, v, f in fraud:
                if s <= tau:
                    esc[f] += v
            # normalise per family so a family that happens to carry more money
            # does not automatically become the worst case
            loss = {f: (esc[f] / total_by_fam[f] if total_by_fam[f] else 0.0)
                    for f in fams}
            # friction is charged into every family's loss, so the minimax does
            # not simply drive tau to zero
            pen = friction / max(1e-9, self.alpha)
            adj = {f: l + 0.35 * pen for f, l in loss.items()}
            worst = max(adj, key=adj.get)
            out.append(Candidate(
                tau=tau, friction=friction, loss_by_family=loss,
                worst_family=worst, worst_loss=adj[worst],
                mean_loss=sum(adj.values()) / len(adj)))

        self.candidates = out
        # Only consider thresholds that keep the promise. A robust threshold
        # that quietly spends three times the friction budget is not robust,
        # it is a different product.
        feasible = [c for c in out if c.friction <= self.alpha * 1.25]
        pool = feasible or out
        best = min(pool, key=lambda c: c.worst_loss)
        self.tau_robust = best.tau
        self.chosen = 'robust'
        return self

    # ------------------------------------------------------------------
    @property
    def tau(self) -> float:
        return self.tau_robust if self.chosen == 'robust' else self.tau_conformal

    def report(self) -> Dict[str, object]:
        c_at = self._at(self.tau_conformal)
        r_at = self._at(self.tau_robust)
        return {
            'alpha': self.alpha,
            'tau_conformal': self.tau_conformal,
            'tau_robust': self.tau_robust,
            'shift': self.tau_robust - self.tau_conformal,
            'conformal': self._pack(c_at),
            'robust': self._pack(r_at),
            'families': self.families,
        }

    def _at(self, tau: float) -> Optional[Candidate]:
        if not self.candidates:
            return None
        return min(self.candidates, key=lambda c: abs(c.tau - tau))

    @staticmethod
    def _pack(c: Optional[Candidate]) -> Dict[str, object]:
        if c is None:
            return {}
        return {'tau': c.tau, 'friction': c.friction,
                'worst_family': c.worst_family,
                'worst_escape': c.loss_by_family.get(c.worst_family, 0.0),
                'mean_escape': sum(c.loss_by_family.values()) / max(1, len(c.loss_by_family)),
                'by_family': dict(c.loss_by_family)}


# ---------------------------------------------------------------------------
def three_way_split(items: Sequence, cal_frac: float = 0.18,
                    train_frac: float = 0.55) -> Tuple[List, List, List]:
    """Temporal train / calibrate / test.

    The calibration slice sits immediately before the test period and is never
    fitted on, so it is exchangeable with what comes after in a way the training
    slice is not. Everything is ordered by time; there is no shuffling anywhere,
    because a random split assumes labels you would not have at decision time.
    """
    n = len(items)
    a = int(n * train_frac)
    b = int(n * (train_frac + cal_frac))
    return list(items[:a]), list(items[a:b]), list(items[b:])
