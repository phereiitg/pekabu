"""The loop.

Everything before this is a pipeline. This is what makes it a loop, and it is
the thesis the brief actually asks for: the attacks train the defence, and the
gaps the defence leaves generate the next attacks.

Framed properly, this is iterated best response. The attacker best-responds to
a fixed defender; the defender retrains against the attacker's response;
repeat. The escape rate is the convergence signal, which gives a principled
stopping criterion instead of stopping at six iterations because time ran out.

A flat escape rate means one of two things, and they are distinguishable:
  - the defender has covered the attacker's reachable strategy space, or
  - the attacker's search has stalled.
Mutator fitness tells you which. If fitness is still improving while escape
rate is flat, the defender is winning. If both are flat, the search is done.

The mutator does the work and the LLM does not. Published work on LLM+RL red
teaming found standalone language models fail to sustain multi-stage
campaigns, so the search is a parameter mutation over declared ranges and the
model is only invited to propose genuinely new vectors, occasionally, under
review.
"""
from __future__ import annotations
import json
import math
import random
import statistics as st
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from chakra.attacks.base import Attack


# ---------------------------------------------------------------------------
@dataclass
class Escape:
    """One attack transaction that got through."""
    txn_id: str
    vector_id: str
    route: str
    signature: str
    params: Dict[str, float]
    value: float
    score: float
    threshold: float

    @property
    def margin(self) -> float:
        """How far under the threshold it landed. A near-miss is more
        informative to the mutator than a comfortable escape, because the
        gradient is there."""
        return self.threshold - self.score


@dataclass
class IterationResult:
    index: int
    n_attacks: int
    n_escaped: int
    value_total: float
    value_escaped: float
    escape_by_vector: Dict[str, float]
    escape_by_route: Dict[str, float]
    coverage_error: Dict[str, float]
    mean_fitness: float
    new_families: List[str] = field(default_factory=list)

    @property
    def escape_rate(self) -> float:
        return self.n_escaped / max(1, self.n_attacks)

    @property
    def value_escape_rate(self) -> float:
        return self.value_escaped / max(1.0, self.value_total)


# ---------------------------------------------------------------------------
class RedSearch:
    """Population-based parameter search driven by the escape log."""

    def __init__(self, population: List[Attack], rng: random.Random,
                 elite: int = 3, offspring: int = 3) -> None:
        self.population = population
        self.rng = rng
        self.elite = elite
        self.offspring = offspring
        self.history: List[IterationResult] = []
        self._seen_signatures = {a.signature() for a in population}

    # -- fitness ---------------------------------------------------------
    @staticmethod
    def fitness(escaped: int, attempted: int, value_escaped: float,
                cost: float) -> float:
        """escape rate x value stolen / attacker cost.

        The cost term is not decoration. Without it the search converges on
        configurations that would never be economic — ten thousand mules, one
        rupee each — and a feasibility score should punish that. With it, the
        search finds attacks a real adversary would actually run.
        """
        if attempted <= 0 or cost <= 0:
            return 0.0
        return (escaped / attempted) * math.log1p(value_escaped) / cost

    # -- one generation --------------------------------------------------
    def evolve(self, scored: List[Tuple[Attack, float]]) -> List[Attack]:
        """Keep the elite, breed mutants from them, retain diversity.

        Deliberately simple. The point is not a clever optimiser; it is that
        the search is driven by measured escapes rather than by intuition, and
        that every configuration it proposes is inside a declared parameter
        range so it stays physically meaningful.
        """
        scored.sort(key=lambda x: -x[1])
        keep = [a for a, _ in scored[: self.elite]]
        nxt = list(keep)
        for parent in keep:
            for _ in range(self.offspring):
                child = parent.mutate(self.rng, scale=0.4)
                sig = child.signature()
                if sig in self._seen_signatures:
                    child = parent.mutate(self.rng, scale=0.7)
                    sig = child.signature()
                self._seen_signatures.add(sig)
                nxt.append(child)
        # keep one random survivor from the tail so the search does not
        # collapse onto a single lineage
        tail = [a for a, _ in scored[self.elite:]]
        if tail:
            nxt.append(self.rng.choice(tail))
        return nxt

    # -- reporting -------------------------------------------------------
    def stopping_signal(self) -> str:
        if len(self.history) < 3:
            return "running"
        last3 = self.history[-3:]
        er = [h.escape_rate for h in last3]
        fit = [h.mean_fitness for h in last3]
        er_flat = (max(er) - min(er)) < 0.03
        fit_rising = fit[-1] > fit[0] * 1.05
        if er_flat and fit_rising:
            return "defender ahead: escape rate flat while attacker fitness still climbing"
        if er_flat and not fit_rising:
            return "converged: neither escape rate nor attacker fitness moving"
        return "running"


# ---------------------------------------------------------------------------
def coverage_error_by_route(scores_by_route: Dict[str, List[float]],
                            thresholds: Dict[str, float],
                            alphas: Dict[str, float]) -> Dict[str, float]:
    """Observed step-up rate on genuine traffic minus the promised budget.

    This is F12, and it is the most interesting thing in the loop.

    The conformal guarantee assumes exchangeability. The red search is a
    machine for deliberately violating exchangeability. So when the attacker
    finds genuinely new ground, coverage breaks BEFORE any label arrives —
    which makes the guarantee a label-free early warning that the threat
    distribution has moved.

    That matters because the labels are the problem. Chargebacks land weeks
    later; a share never lands at all. A drift signal that needs no labels is
    the only kind that can fire in time.
    """
    out = {}
    for route, scores in scores_by_route.items():
        if not scores:
            continue
        tau = thresholds.get(route)
        a = alphas.get(route, 0.02)
        if tau is None:
            continue
        observed = sum(1 for s in scores if s > tau) / len(scores)
        out[route] = observed - a
    return out
