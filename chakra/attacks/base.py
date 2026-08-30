"""Attack plugins.

Two rules that make the difference between this and a fraud-row generator.

1. An attack **perturbs the world**. It recruits mules, ages an agent, binds a
   device to twenty accounts, poisons a listing. The transactions are what
   falls out. A plugin that only appends rows with `is_fraud=1` produces data
   that no detector can learn structure from, which is the whole point of the
   fidelity argument.

2. Every attack exposes a **parameter dict with declared ranges**. Phase 7's
   mutator searches that space against the escape log. An attack with
   hard-coded constants cannot participate in the loop, so it is not really
   part of the system.

Each plugin carries its taxonomy ID, so every fraudulent transaction traces
back to a vector in taxonomy.json, and from there to an F3 or F3X technique.
"""
from __future__ import annotations
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any

from chakra.schema.enums import TrustLink, Rail
from chakra.schema.transaction import Transaction
from chakra.schema.entity import World
from chakra.schema.labels import GroundTruth, LabelHarness


@dataclass
class AttackContext:
    world: World
    origin: datetime
    days: int
    rng: random.Random
    harness: LabelHarness
    counter: List[int] = field(default_factory=lambda: [900_000_000])

    def next_id(self) -> str:
        self.counter[0] += 1
        return f"F{self.counter[0]:09d}"

    def at(self, seconds: float) -> datetime:
        return self.origin + timedelta(seconds=seconds)

    @property
    def horizon(self) -> float:
        return self.days * 86400.0


class Attack:
    """Base class. Subclasses set `vector_id`, `trust_link` and `PARAMS`."""

    vector_id: str = ""
    trust_link: TrustLink = TrustLink.NONE
    name: str = ""

    #: name -> (default, low, high). The mutator's search space.
    PARAMS: Dict[str, Tuple[float, float, float]] = {}

    def __init__(self, **overrides: float) -> None:
        self.params: Dict[str, float] = {k: v[0] for k, v in self.PARAMS.items()}
        for k, v in overrides.items():
            if k not in self.PARAMS:
                raise KeyError(f"{self.name}: unknown parameter {k!r}")
            self.params[k] = v

    # -- mutator interface ------------------------------------------------
    def mutate(self, rng: random.Random, scale: float = 0.35) -> "Attack":
        out = {}
        for k, (_d, lo, hi) in self.PARAMS.items():
            cur = self.params[k]
            step = (hi - lo) * scale
            out[k] = max(lo, min(hi, cur + rng.uniform(-step, step)))
        return type(self)(**out)

    def signature(self) -> str:
        p = ",".join(f"{k}={self.params[k]:.3f}" for k in sorted(self.params))
        return f"{self.vector_id}({p})"

    # -- cost, for the fitness function -----------------------------------
    def attacker_cost(self) -> float:
        """Relative cost of running this configuration. Without a cost term
        the search proposes attacks nobody would actually run, and the
        feasibility score suffers for it."""
        return 1.0

    # -- execution --------------------------------------------------------
    def run(self, ctx: AttackContext) -> List[Transaction]:
        raise NotImplementedError

    # -- helper -----------------------------------------------------------
    def emit(self, ctx: AttackContext, txn: Transaction,
             value_at_risk: Optional[float] = None) -> Transaction:
        ctx.harness.register(
            GroundTruth(txn_id=txn.txn_id, is_fraud=True,
                        vector_id=self.vector_id,
                        trust_link=self.trust_link,
                        value_at_risk=value_at_risk or float(txn.amount)),
            txn.ts, txn.rail, ctx.rng)
        return txn
