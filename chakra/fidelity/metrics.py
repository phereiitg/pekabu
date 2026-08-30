"""Behavioural fidelity metrics, P1 through P4.

Both real and synthetic data are reduced to a common EventLog first, so the
identical code path measures both. If the metric had two implementations, any
difference between them would show up as fidelity.

  P1  inter-event timing     distribution of gaps, and their ordering
  P2  burst and lifetime     events per entity, active span, burst density
  P3  graph motifs           shared-attribute degree structure
  P4  velocity trigger rates how often a standard rule would fire

Everything is reported as a degradation ratio against a real-data noise floor:

    DR = d(synthetic, real) / d(real_half_A, real_half_B)

DR = 1.0 means the synthetic data differs from real data by no more than real
data differs from itself. DR = 25 means twenty-five times worse. The ratio
form matters for a reason we found the hard way in Phase 3: the lag-1
autocorrelation estimator is biased by about -1/(n-1) even on iid data, and a
ratio cancels that bias because numerator and denominator carry it equally.
"""
from __future__ import annotations
import math, random, statistics as st
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple


# ---------------------------------------------------------------- log ------
@dataclass
class Event:
    entity: str
    t: float                       # seconds
    amount: float
    category: str = ""             # MCC or ProductCD
    attrs: Dict[str, str] = field(default_factory=dict)   # graph keys
    is_fraud: bool = False


@dataclass
class EventLog:
    name: str
    events: List[Event]

    def by_entity(self) -> Dict[str, List[Event]]:
        d: Dict[str, List[Event]] = defaultdict(list)
        for e in self.events:
            d[e.entity].append(e)
        for v in d.values():
            v.sort(key=lambda x: x.t)
        return d

    def span_days(self) -> float:
        ts = [e.t for e in self.events]
        return (max(ts) - min(ts)) / 86400 if ts else 0.0

    def crop(self, days: float) -> "EventLog":
        """Match observation windows before comparing. Lifetime and burst
        statistics are window-dependent, so comparing a 182-day corpus to a
        45-day one measures the window, not the behaviour."""
        if not self.events:
            return self
        t0 = min(e.t for e in self.events)
        cut = t0 + days * 86400
        return EventLog(self.name, [e for e in self.events if e.t <= cut])


# ------------------------------------------------------------ distances ----
def w1(a: Sequence[float], b: Sequence[float], n: int = 512) -> float:
    """1-D Wasserstein between two empirical distributions, via quantiles.

    Scale-free version: both samples are divided by the pooled median first,
    because IEEE-CIS amounts are USD e-commerce and ours are INR. Comparing
    raw magnitudes would measure the currency.
    """
    a = sorted(x for x in a if x is not None and math.isfinite(x))
    b = sorted(x for x in b if x is not None and math.isfinite(x))
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    pooled = sorted(a + b)
    med = pooled[len(pooled) // 2] or 1.0
    a = [x / med for x in a]
    b = [x / med for x in b]

    def qs(xs):
        m = len(xs)
        return [xs[min(m - 1, int(i * m / n))] for i in range(n)]
    qa, qb = qs(a), qs(b)
    return sum(abs(x - y) for x, y in zip(qa, qb)) / n


def absdiff(a: Optional[float], b: Optional[float]) -> float:
    if a is None or b is None or not math.isfinite(a) or not math.isfinite(b):
        return float("nan")
    return abs(a - b)


# ----------------------------------------------------- autocorrelation -----
def _ac1(xs: Sequence[float]) -> Optional[float]:
    if len(xs) < 3:
        return None
    m = st.fmean(xs)
    den = sum((x - m) ** 2 for x in xs)
    if den == 0:
        return None
    return sum((a - m) * (b - m) for a, b in zip(xs, xs[1:])) / den


def lag1_excess(gap_lists: List[List[float]], rng: random.Random,
                min_gaps: int = 8) -> Optional[float]:
    """Lag-1 autocorrelation of log gaps, minus a within-entity shuffle null.

    The shuffle preserves the gap multiset and destroys only the ordering, so
    it carries the identical small-sample bias. The difference is the ordering
    signal and nothing else.
    """
    obs, null = [], []
    for g in gap_lists:
        lg = [math.log(x) for x in g if x > 0]
        if len(lg) < min_gaps:
            continue
        a = _ac1(lg)
        if a is None:
            continue
        s = lg[:]
        rng.shuffle(s)
        b = _ac1(s)
        if b is None:
            continue
        obs.append(a); null.append(b)
    if len(obs) < 20:
        return None
    return st.fmean(obs) - st.fmean(null)


# ---------------------------------------------------------------- P1 ------
def p1_features(log: EventLog, rng: random.Random) -> Dict[str, object]:
    gaps_all, gap_lists = [], []
    for ev in log.by_entity().values():
        g = [b.t - a.t for a, b in zip(ev, ev[1:]) if b.t > a.t]
        if g:
            gaps_all += g
            gap_lists.append(g)
    if not gaps_all:
        return {}
    return {
        "gaps": gaps_all,
        "cv": st.pstdev(gaps_all) / st.fmean(gaps_all),
        "lag1_excess": lag1_excess(gap_lists, rng),
        "frac_under_1h": sum(1 for g in gaps_all if g < 3600) / len(gaps_all),
    }


# ---------------------------------------------------------------- P2 ------
def p2_features(log: EventLog) -> Dict[str, object]:
    counts, spans, dens = [], [], []
    for ev in log.by_entity().values():
        counts.append(len(ev))
        if len(ev) > 1:
            span = (ev[-1].t - ev[0].t) / 86400
            spans.append(span)
            # burst density: share of events inside the busiest single hour
            best = 0
            for i, e in enumerate(ev):
                j = i
                while j < len(ev) and ev[j].t - e.t <= 3600:
                    j += 1
                best = max(best, j - i)
            dens.append(best / len(ev))
    if not counts:
        return {}
    return {
        "counts": counts,
        "spans": spans,
        "burst_density": dens,
        "mean_burst_density": st.fmean(dens) if dens else float("nan"),
    }


# ---------------------------------------------------------------- P3 ------
def p3_features(log: EventLog, attr: str) -> Dict[str, object]:
    """Shared-attribute structure: how many distinct entities touch the same
    attribute value, and how many distinct values each entity touches.

    This is the metric row-independent generators provably cannot reproduce.
    They sample shared attributes from marginals, which drives every fan-out
    toward 1 and destroys ring structure by construction.
    """
    a2e: Dict[str, set] = defaultdict(set)
    e2a: Dict[str, set] = defaultdict(set)
    for e in log.events:
        v = e.attrs.get(attr)
        if not v:
            continue
        a2e[v].add(e.entity)
        e2a[e.entity].add(v)
    if not a2e:
        return {}
    fan = [len(s) for s in a2e.values()]
    deg = [len(s) for s in e2a.values()]
    shared = sum(1 for f in fan if f > 1) / len(fan)
    # triangle-ish motif proxy: entity pairs co-occurring on 2+ shared values
    pair = Counter()
    for v, ents in a2e.items():
        if 1 < len(ents) <= 40:
            le = sorted(ents)
            for i in range(len(le)):
                for j in range(i + 1, len(le)):
                    pair[(le[i], le[j])] += 1
    motif = sum(1 for c in pair.values() if c >= 2)
    return {
        "fan_out": fan,
        "entity_degree": deg,
        "shared_frac": shared,
        "max_fan_out": max(fan),
        "motif_pairs": motif,
        "motif_rate": motif / max(1, len(e2a)),
    }


# ---------------------------------------------------------------- P4 ------
VELOCITY_RULES = {
    "ge3_in_1h":        lambda ev, i: sum(
        1 for x in ev[max(0, i - 20):i] if ev[i].t - x.t <= 3600) >= 3,
    "ge5_in_24h":       lambda ev, i: sum(
        1 for x in ev[max(0, i - 60):i] if ev[i].t - x.t <= 86400) >= 5,
    "ge4_distinct_cat_24h": lambda ev, i: len({
        x.category for x in ev[max(0, i - 60):i + 1]
        if ev[i].t - x.t <= 86400 and x.category}) >= 4,
}


def p4_features(log: EventLog) -> Dict[str, float]:
    hits = {k: 0 for k in VELOCITY_RULES}
    hits["amt_gt_5x_median"] = 0
    n = 0
    for ev in log.by_entity().values():
        amts = sorted(e.amount for e in ev)
        med = amts[len(amts) // 2] if amts else 0.0
        for i in range(len(ev)):
            n += 1
            for k, fn in VELOCITY_RULES.items():
                if fn(ev, i):
                    hits[k] += 1
            if med and ev[i].amount > 5 * med:
                hits["amt_gt_5x_median"] += 1
    return {k: (v / n if n else float("nan")) for k, v in hits.items()}


# --------------------------------------------------------- comparison -----
def compare(a: EventLog, b: EventLog, rng: random.Random,
            graph_attr: str = "device") -> Dict[str, float]:
    """Distance between two logs on every P1-P4 axis. Symmetric."""
    d: Dict[str, float] = {}
    a1, b1 = p1_features(a, rng), p1_features(b, rng)
    if a1 and b1:
        d["P1_gap_dist"] = w1(a1["gaps"], b1["gaps"])
        d["P1_cv"] = absdiff(a1["cv"], b1["cv"])
        d["P1_lag1"] = absdiff(a1["lag1_excess"], b1["lag1_excess"])
        d["P1_frac_1h"] = absdiff(a1["frac_under_1h"], b1["frac_under_1h"])

    a2, b2 = p2_features(a), p2_features(b)
    if a2 and b2:
        d["P2_count_dist"] = w1(a2["counts"], b2["counts"])
        d["P2_span_dist"] = w1(a2["spans"], b2["spans"])
        d["P2_burst_density"] = absdiff(a2["mean_burst_density"],
                                        b2["mean_burst_density"])

    a3, b3 = p3_features(a, graph_attr), p3_features(b, graph_attr)
    if a3 and b3:
        d["P3_fanout_dist"] = w1(a3["fan_out"], b3["fan_out"])
        d["P3_degree_dist"] = w1(a3["entity_degree"], b3["entity_degree"])
        d["P3_shared_frac"] = absdiff(a3["shared_frac"], b3["shared_frac"])
        d["P3_motif_rate"] = absdiff(a3["motif_rate"], b3["motif_rate"])

    a4, b4 = p4_features(a), p4_features(b)
    for k in a4:
        d[f"P4_{k}"] = absdiff(a4[k], b4[k])
    return d


def split_half(log: EventLog, rng: random.Random) -> Tuple[EventLog, EventLog]:
    """Split BY ENTITY, never by row. Splitting rows would put the same
    entity in both halves and make the floor artificially tight."""
    ents = sorted({e.entity for e in log.events})
    rng.shuffle(ents)
    half = set(ents[:len(ents) // 2])
    A = [e for e in log.events if e.entity in half]
    B = [e for e in log.events if e.entity not in half]
    return EventLog(log.name + "_A", A), EventLog(log.name + "_B", B)


def noise_floor(log: EventLog, rng: random.Random, repeats: int = 5,
                graph_attr: str = "device") -> Dict[str, float]:
    """How different real data is from itself. Averaged over several splits so
    a single unlucky partition does not set the denominator."""
    acc: Dict[str, List[float]] = defaultdict(list)
    for _ in range(repeats):
        A, B = split_half(log, rng)
        for k, v in compare(A, B, rng, graph_attr).items():
            if v is not None and math.isfinite(v):
                acc[k].append(v)
    return {k: st.fmean(v) for k, v in acc.items() if v}


def degradation(synth: EventLog, real: EventLog, floor: Dict[str, float],
                rng: random.Random, graph_attr: str = "device"
                ) -> Dict[str, float]:
    d = compare(synth, real, rng, graph_attr)
    out = {}
    for k, v in d.items():
        f = floor.get(k)
        if f and math.isfinite(v) and f > 1e-12:
            out[k] = v / f
    return out
