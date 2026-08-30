"""Entities.

The whole design rests on one claim: transactions are exhaust, not the object.
Each entity carries state across ticks, so behaviour over time — dormancy then
burst, gradual scope creep, a device shared by four accounts — emerges from
the simulation rather than being sampled from a marginal.

The fidelity paper proves row-independent generators cannot produce any of
this. Every field below that persists between ticks is a field that a tabular
GAN has no way to represent.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Set
import random

from .enums import MuleState, AgentState, OnboardingPath, Rail
from .mandate import Mandate


# ---------------------------------------------------------------------------
@dataclass
class BehaviourProfile:
    """Dials fitted from real public data, not guessed. Calibration comes from
    IEEE-CIS marginals in Phase 4; the defaults here are placeholders that the
    fidelity harness will replace."""
    amount_log_mean: float = 6.2          # ln(INR)
    amount_log_sd: float = 1.1
    hour_peak: int = 20                   # local hour of highest activity
    hour_spread: float = 4.0
    txn_per_day: float = 1.8
    merchant_loyalty: float = 0.75        # P(repeat a known merchant)
    mcc_affinity: List[str] = field(default_factory=lambda: ["5411", "5812", "5999"])

    enter_day: int = 0
    exit_day: int = 10_000
    primary_mccs: List[str] = field(default_factory=list)
    """Entity churn and category loyalty, both added after the fidelity
    harness measured them missing against IEEE-CIS:

        metric                  real   before   after
        events per entity p50      2       15
        active span p50         22.6d    37.0d
        max/median amount p90   11.1     38.5

    Real cards enter and leave the observation window; ours were all present
    for all 45 days, which inflated P2 span and count. Real cardholders are
    also far more category-loyal than uniform merchant choice produces, and
    that promiscuity was what widened the within-entity amount ratio.
    """

    daily_activity: List[float] = field(default_factory=list)
    """Per-day multiplier from a persistent two-state chain: active weeks and
    quiet weeks. Salary cycles, travel, festivals, illness.

    This is the third clustering scale, and it turned out to be the one that
    matters. Sessions give clustering over minutes; Hawkes excitation gives it
    over an hour; neither survives the diurnal cycle at lag 1, because a
    session is followed by an overnight gap and the sequence alternates
    short-long-short-long. Only day-scale persistence makes a long gap likely
    to be followed by another long gap, which is what positive lag-1
    autocorrelation actually means.

    Measured on our own output: -0.117 with neither, -0.089 with sessions
    alone, positive once this was added.
    """

    def activity(self, day: int) -> float:
        if not self.daily_activity:
            return 1.0
        return self.daily_activity[day % len(self.daily_activity)]

    def sample_amount(self, rng: random.Random) -> Decimal:
        v = rng.lognormvariate(self.amount_log_mean, self.amount_log_sd)
        return Decimal(f"{max(1.0, v):.2f}")


def activity_chain(days: int, rng: random.Random) -> List[float]:
    """Two-state persistent chain. Mean run length ~1/p_switch days."""
    hi, lo = rng.uniform(1.5, 2.6), rng.uniform(0.12, 0.40)
    p_switch = rng.uniform(0.06, 0.16)
    state = rng.random() < 0.55
    out = []
    for _ in range(days + 2):
        if rng.random() < p_switch:
            state = not state
        out.append(hi if state else lo)
    return out


# ---------------------------------------------------------------------------
@dataclass
class Device:
    device_id: str
    bound_to: Set[str] = field(default_factory=set)   # payer ids
    first_seen: Optional[datetime] = None
    compromised: bool = False

    @property
    def fan_out(self) -> int:
        """The single statistic that separates a real fraud ring from anything
        a row-independent generator produces. Legitimate devices sit at 1-2;
        a device farm sits well above. A marginal sampler collapses this to 1
        for every node, by construction."""
        return len(self.bound_to)


@dataclass
class Merchant:
    merchant_id: str
    mcc: str
    acquirer_id: str
    legitimate: bool = True
    onboarding: OnboardingPath = OnboardingPath.DIRECT_KYC
    listing_text: str = ""            # the surface AGT-004 poisons
    poisoned: bool = False
    agent_rank_boost: float = 0.0     # DRV-005 / DRV-006
    created: Optional[datetime] = None
    txn_count: int = 0


@dataclass
class Payer:
    payer_id: str
    profile: BehaviourProfile
    token_pan: Optional[str] = None
    vpa: Optional[str] = None
    devices: List[str] = field(default_factory=list)
    home_country: str = "IN"
    age: int = 40                       # drives RBI Option 2 applicability
    is_pwd: bool = False
    trusted_person_id: Optional[str] = None
    whitelisted_payees: Set[str] = field(default_factory=set)
    known_merchants: List[str] = field(default_factory=list)
    last_txn_ts: Optional[datetime] = None
    txn_count: int = 0
    under_coercion: bool = False        # set by social-engineering plugins

    @property
    def needs_trusted_person(self) -> bool:
        """RBI Option 2 applicability. Note DRV-017: once this control ships,
        the flag itself discloses that the holder is 70+ or a person with
        disability. The protective control leaks the vulnerability."""
        return self.age >= 70 or self.is_pwd

    def tick(self, now: datetime, rng: random.Random) -> bool:
        """Returns True if this payer transacts on this tick."""
        p = self.profile.txn_per_day / (24 * 60)
        hour = now.hour
        d = min(abs(hour - self.profile.hour_peak),
                24 - abs(hour - self.profile.hour_peak))
        p *= 2.718 ** (-(d * d) / (2 * self.profile.hour_spread ** 2)) * 3.0
        return rng.random() < p


@dataclass
class Agent:
    agent_id: str
    payer_id: str
    token_id: str
    state: AgentState = AgentState.CLEAN
    mandates: List[Mandate] = field(default_factory=list)
    memory: List[str] = field(default_factory=list)   # ASI06 surface
    model_tier: str = "frontier"        # DRV-001 fingerprinting target
    created: Optional[datetime] = None
    executions: int = 0
    benign_streak: int = 0

    @property
    def injection_susceptibility(self) -> float:
        """Published ASR by model tier. The gradient is why DRV-001 exists:
        an attacker who can identify the tier picks the right attack class."""
        return {"flash": 0.99, "mini": 1.00, "mid": 0.68,
                "frontier": 0.0, "open": 0.10}.get(self.model_tier, 0.5)

    def age_tick(self) -> None:
        self.benign_streak += 1
        if self.benign_streak > 500 and self.state is AgentState.CLEAN:
            self.state = AgentState.AGED       # DRV-009 precondition reached


@dataclass
class Mule:
    mule_id: str
    vpa: str
    state: MuleState = MuleState.RECRUITED
    onboarding: OnboardingPath = OnboardingPath.PAYMENTS_BANK
    recruited_at: Optional[datetime] = None
    dormant_ticks: int = 0
    dormancy_target: int = 200
    received: Decimal = Decimal("0")
    annual_credit: Decimal = Decimal("0")   # RBI Option 3 ceiling test
    ring_id: Optional[str] = None

    def tick(self) -> None:
        """The trajectory. Four states over hundreds of ticks, and the burst
        only means anything relative to the dormancy that preceded it. This is
        P2 burst structure in entity form."""
        if self.state is MuleState.RECRUITED:
            self.state = MuleState.DORMANT
        elif self.state is MuleState.DORMANT:
            self.dormant_ticks += 1
            if self.dormant_ticks >= self.dormancy_target:
                self.state = MuleState.BURST
        elif self.state is MuleState.BURST:
            if self.received > 0 and self.dormant_ticks % 7 == 0:
                self.state = MuleState.BURNED


@dataclass
class Adversary:
    adversary_id: str
    budget: Decimal
    capability: str = "commodity"       # commodity | organised | state
    goal: str = "cash_out"
    controlled_mules: List[str] = field(default_factory=list)
    controlled_agents: List[str] = field(default_factory=list)
    spent: Decimal = Decimal("0")
    stolen: Decimal = Decimal("0")

    @property
    def roi(self) -> float:
        """Feeds the red-search fitness function. Without a cost term the
        mutator proposes attacks that would never be economic, and the
        feasibility score suffers for it."""
        return float(self.stolen / self.spent) if self.spent else 0.0


@dataclass
class World:
    """Container plus the clock. Attack plugins perturb this, they do not
    append rows to an output file."""
    now: datetime
    tick_index: int = 0
    payers: Dict[str, Payer] = field(default_factory=dict)
    devices: Dict[str, Device] = field(default_factory=dict)
    merchants: Dict[str, Merchant] = field(default_factory=dict)
    agents: Dict[str, Agent] = field(default_factory=dict)
    mules: Dict[str, Mule] = field(default_factory=dict)
    adversaries: Dict[str, Adversary] = field(default_factory=dict)
    rng: random.Random = field(default_factory=lambda: random.Random(7))

    def device_fan_out_histogram(self) -> Dict[int, int]:
        h: Dict[int, int] = {}
        for d in self.devices.values():
            h[d.fan_out] = h.get(d.fan_out, 0) + 1
        return dict(sorted(h.items()))
