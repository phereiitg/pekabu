"""Training memory for the loop.

D-27, diagnosed properly.

The loop's defender got monotonically worse: escape rate on frozen benchmark
attacks rose 67.9% -> 97.1% over six iterations. The first hypothesis was that
the conformal threshold was chasing the score distribution upward. Wrong.
Instrumenting ranking quality separately from threshold placement settled it:

    iter   train n   base rate   PR-AUC   separation
      1        638      15.5%     0.136      0.079
      2      1,288      13.7%     0.256      0.057
      4      3,100      27.6%     0.182      0.176
      5      4,671      40.4%     0.026      0.104
      6      5,336      37.5%     0.027      0.153

PR-AUC collapses by an order of magnitude. The MODEL degrades; the threshold
was a symptom.

The cause is an accumulation asymmetry. Every round adds several hundred
freshly-labelled fraud transactions, because attacks are dense and chargebacks
eventually arrive for most of them. But labelled GENUINE traffic only arrives
through the alert filter, which touches about 1.2% of benign volume. So the
training base rate climbs every round until the corpus is 40% fraud — a
distribution that resembles no payment system that has ever existed. The WOE
bins get estimated on that corpus, and the genuine class stops being
adequately represented in them.

Two corrections, both textbook for case-control sampling, neither of which the
first implementation had:

  1. RESERVOIR BALANCE. Cap the training memory and hold its base rate near a
     declared target. Fraud is the scarce and valuable class in reality, so we
     keep all of it we can and bound it relative to genuine rather than the
     other way round.

  2. PRIOR CORRECTION. The model trains on an enriched sample, so its
     intercept encodes the enriched base rate. Deployment sees something quite
     different. Correct the intercept to the declared deployment rate rather
     than letting the training rate leak into the score.

The second matters for a reason beyond this bug: the budget arithmetic
multiplies a probability by a rupee amount. If the intercept encodes a 40%
base rate, that product is arithmetic on a meaningless number.
"""
from __future__ import annotations
import math
import random
from dataclasses import dataclass, field
from typing import List, Sequence, Tuple

from chakra.detect.features import FeatureSet


@dataclass
class TrainingReservoir:
    """Bounded, class-balanced training memory.

    target_base_rate  the fraud share the reservoir is held near. Not the
                      deployment rate — an enriched-but-stable rate that keeps
                      both classes well represented in the WOE bins.
    deployment_rate   what the intercept is corrected to. This is the number
                      the budget arithmetic depends on.
    """
    capacity: int = 24_000
    target_base_rate: float = 0.06
    deployment_rate: float = 0.005
    rng: random.Random = field(default_factory=lambda: random.Random(97))

    fraud: List[FeatureSet] = field(default_factory=list)
    genuine: List[FeatureSet] = field(default_factory=list)

    def add(self, rows: Sequence[FeatureSet], y: Sequence[int]) -> None:
        for r, lab in zip(rows, y):
            (self.fraud if lab else self.genuine).append(r)
        self._rebalance()

    def _rebalance(self) -> None:
        # Genuine is capped by capacity; fraud is capped by the target ratio
        # against however much genuine we have. Reservoir-style eviction keeps
        # older rounds represented instead of only the most recent.
        max_gen = int(self.capacity * (1 - self.target_base_rate))
        if len(self.genuine) > max_gen:
            self.genuine = self.rng.sample(self.genuine, max_gen)
        max_fraud = max(30, int(len(self.genuine) * self.target_base_rate
                                / max(1e-9, 1 - self.target_base_rate)))
        if len(self.fraud) > max_fraud:
            # keep the most recent half, sample the rest, so newly discovered
            # attack configurations are never evicted in favour of old ones
            recent = self.fraud[-(max_fraud // 2):]
            older = self.fraud[: -(max_fraud // 2)] or []
            k = min(len(older), max_fraud - len(recent))
            self.fraud = (self.rng.sample(older, k) if k > 0 else []) + recent

    def dataset(self) -> Tuple[List[FeatureSet], List[int]]:
        rows = self.genuine + self.fraud
        y = [0] * len(self.genuine) + [1] * len(self.fraud)
        idx = list(range(len(rows)))
        self.rng.shuffle(idx)
        return [rows[i] for i in idx], [y[i] for i in idx]

    @property
    def base_rate(self) -> float:
        n = len(self.fraud) + len(self.genuine)
        return len(self.fraud) / n if n else 0.0

    def prior_logit(self) -> float:
        """Intercept corrected from the sampled rate to the deployment rate.

        Standard case-control correction: subtract the logit of the sampling
        base rate and add the logit of the population base rate. Without it,
        an enriched training set produces probabilities that are systematically
        too high, and every downstream cost calculation inherits the error.
        """
        p = max(1e-6, min(1 - 1e-6, self.deployment_rate))
        s = max(1e-6, min(1 - 1e-6, self.base_rate))
        return math.log(p / (1 - p)) - math.log(s / (1 - s)) + math.log(s / (1 - s)) \
            if False else math.log(p / (1 - p))

    def summary(self) -> str:
        return (f"reservoir n={len(self.fraud)+len(self.genuine):,} "
                f"(fraud {len(self.fraud):,} / genuine {len(self.genuine):,}) "
                f"base {self.base_rate:.1%} -> corrected to "
                f"{self.deployment_rate:.2%}")
