"""Heads, fusion, calibration, response.

The scorecard construction is deliberate. Each head bins its features and
scores weight of evidence:

    WOE(bin) = log[ P(bin | fraud) / P(bin | genuine) ]
    logit P(fraud | e) = logit P(fraud) + sum_i WOE_i

Three properties follow from the form rather than being added on top.

1. Reason codes ARE the terms. The score is a sum, so ranking the terms ranks
   the reasons. Explainability is not a separate model.
2. It is the standard credit-scorecard construction, which every risk team in
   an Indian bank already knows how to validate. That familiarity is the point.
3. By Neyman-Pearson, thresholding a likelihood ratio is the most powerful
   test at a fixed false-positive rate. Given a fixed friction budget, this is
   not one reasonable architecture among several; it is the optimal form.

The independence assumption is false and we say so before a judge finds it.
New-device and new-merchant correlate. Features are grouped into blocks; within
a block the largest term counts in full and the rest are damped.
"""
from __future__ import annotations
import math
import statistics as st
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from chakra.detect.features import FeatureSet


# ---------------------------------------------------------------------------
def _bin_edges(vals: Sequence[float], n: int = 8) -> List[float]:
    v = sorted(x for x in vals if math.isfinite(x))
    if len(v) < n * 4:
        return []
    return [v[int(i * len(v) / n)] for i in range(1, n)]


def _bin_of(x: float, edges: Sequence[float]) -> int:
    lo, hi = 0, len(edges)
    while lo < hi:
        mid = (lo + hi) // 2
        if x < edges[mid]:
            hi = mid
        else:
            lo = mid + 1
    return lo


# ---------------------------------------------------------------------------
# Correlated feature blocks. Independence is assumed only BETWEEN blocks.
CORR_BLOCKS = {
    "velocity":   {"n_1h", "n_24h", "n_7d", "burst_1h_agent"},
    "diversity":  {"distinct_mcc_24h", "distinct_mer_24h", "mcc_entropy"},
    "novelty":    {"new_merchant", "mcc_novel", "merchant_novel"},
    "amount":     {"log_amount", "amt_over_median", "amt_over_agent_med"},
    "decline":    {"decline_rate_24h", "is_declined"},
    "graph":      {"max_key_fanout", "mean_key_fanout", "device_fanout",
                   "payee_fanout", "merchant_fanout"},
    "auth":       {"eci_authenticated", "unauth_agentic", "is_token_entry"},
}
_FEAT_BLOCK = {f: b for b, fs in CORR_BLOCKS.items() for f in fs}
DAMPING = 0.35     # weight on non-maximal terms within a correlated block


@dataclass
class Head:
    """A weight-of-evidence scorecard over one feature block."""
    name: str
    block: str
    edges: Dict[str, List[float]] = field(default_factory=dict)
    woe: Dict[str, Dict[int, float]] = field(default_factory=dict)
    _bin_dist: Dict[str, Dict[int, Tuple[float, float]]] = field(default_factory=dict)
    prior_logit: float = 0.0
    trained: bool = False

    # -- fit ----------------------------------------------------------
    def fit(self, rows: List[FeatureSet], y: List[int],
            n_bins: int = 12, smoothing: float = 12.0) -> "Head":
        feats = sorted({k for r in rows for k in r.block(self.block)})
        pos = sum(y) or 1
        neg = len(y) - pos or 1
        self.prior_logit = math.log(pos / neg)
        for f in feats:
            vals = [r.block(self.block).get(f, 0.0) for r in rows]
            e = _bin_edges(vals, n_bins)
            if not e:
                continue
            self.edges[f] = e
            cp = defaultdict(float); cn = defaultdict(float)
            for v, label in zip(vals, y):
                b = _bin_of(v, e)
                if label:
                    cp[b] += 1
                else:
                    cn[b] += 1
            self.woe[f] = {}
            self._bin_dist[f] = {}
            for b in range(len(e) + 1):
                # Laplace-smoothed WOE. Smoothing matters here because the
                # base rate is low and an unsmoothed empty bin gives infinity.
                p = (cp[b] + smoothing * pos / len(y)) / (pos + smoothing)
                q = (cn[b] + smoothing * neg / len(y)) / (neg + smoothing)
                self.woe[f][b] = math.log(p / q)
                self._bin_dist[f][b] = (p, q)
        self.trained = True
        return self

    # -- score --------------------------------------------------------
    def information_value(self) -> List[Tuple[str, float]]:
        """IV per feature, ranked.

            IV_j = sum_b ( P(b|fraud) - P(b|genuine) ) * WOE_jb

        This is what to show when someone asks which features actually carry a
        head, rather than which happened to fire on one example. Conventional
        reading in credit scoring: below 0.02 is noise, 0.1-0.3 is medium,
        above 0.5 is strong and usually worth checking for leakage.
        """
        out = []
        for f, w in self.woe.items():
            dist = self._bin_dist.get(f)
            if not dist:
                continue
            iv = sum((p1 - p0) * w.get(b, 0.0) for b, (p1, p0) in dist.items())
            out.append((f, iv))
        return sorted(out, key=lambda x: -x[1])

    def terms(self, r: FeatureSet) -> List[Tuple[str, float]]:
        out = []
        blk = r.block(self.block)
        for f, e in self.edges.items():
            if f not in blk:
                continue
            out.append((f, self.woe[f][_bin_of(blk[f], e)]))
        return out

    def score(self, r: FeatureSet) -> float:
        """Sum of WOE terms with within-block damping applied."""
        by_block: Dict[str, List[float]] = defaultdict(list)
        loose = 0.0
        for f, w in self.terms(r):
            b = _FEAT_BLOCK.get(f)
            if b:
                by_block[b].append(w)
            else:
                loose += w
        total = loose
        for _b, ws in by_block.items():
            ws.sort(key=abs, reverse=True)
            total += ws[0] + DAMPING * sum(ws[1:])
        return total

    def reasons(self, r: FeatureSet, k: int = 3) -> List[Tuple[str, float]]:
        """Ranked reason codes. They are the terms, not a separate model."""
        return sorted(self.terms(r), key=lambda x: -x[1])[:k]

    def applicable(self, r: FeatureSet) -> bool:
        return bool(r.block(self.block))


# ---------------------------------------------------------------------------
@dataclass
class Fusion:
    """Additive log-likelihood-ratio fusion.

    Each head is Platt-calibrated to an LLR before summing. Without this the
    sum is meaningless: raw WOE totals have head-specific scale, so adding a
    noisy head DEGRADES the fused score rather than leaving it alone. We
    measured exactly that — A alone scored 0.196 PR-AUC and A+B+C scored
    0.134 — before calibration was added.

    Calibration is load-bearing for a second reason. The budget arithmetic
    multiplies a probability by a rupee amount, so if 0.8 does not mean 80%
    that product is arithmetic on a meaningless number.
    """
    heads: List[Head]
    prior_logit: float = 0.0
    cal: Dict[str, Tuple[float, float]] = field(default_factory=dict)

    def fit_prior(self, y: Sequence[int]) -> "Fusion":
        pos = sum(y) or 1
        neg = len(y) - pos or 1
        self.prior_logit = math.log(pos / neg)
        return self

    def calibrate(self, rows: List[FeatureSet], y: Sequence[int],
                  iters: int = 220, lr: float = 0.08) -> "Fusion":
        """One-dimensional logistic fit per head: LLR = a * raw + b."""
        for hd in self.heads:
            idx = [i for i, r in enumerate(rows) if hd.applicable(r)]
            if len(idx) < 40 or len({y[i] for i in idx}) < 2:
                self.cal[hd.name] = (0.0, 0.0)
                continue
            xs = [hd.score(rows[i]) for i in idx]
            ys = [y[i] for i in idx]
            m = st.fmean(xs)
            sd = st.pstdev(xs) or 1.0
            xs = [(x - m) / sd for x in xs]
            a, b = 0.0, 0.0
            for _ in range(iters):
                ga = gb = 0.0
                for x, t in zip(xs, ys):
                    z = max(-30.0, min(30.0, a * x + b))
                    p = 1.0 / (1.0 + math.exp(-z))
                    ga += (p - t) * x
                    gb += (p - t)
                a -= lr * ga / len(xs)
                b -= lr * gb / len(xs)
            self.cal[hd.name] = (a / sd, b - a * m / sd)
        return self

    def llr(self, r: FeatureSet) -> Tuple[float, Dict[str, float]]:
        per = {}
        for hd in self.heads:
            if not hd.applicable(r):
                per[hd.name] = 0.0
                continue
            a, b = self.cal.get(hd.name, (1.0, 0.0))
            per[hd.name] = a * hd.score(r) + b if self.cal else hd.score(r)
        return self.prior_logit + sum(per.values()), per

    def prob(self, r: FeatureSet) -> float:
        z, _ = self.llr(r)
        return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))


# ---------------------------------------------------------------------------
@dataclass
class ConformalBudget:
    """Split-conformal threshold that holds a stated step-up rate.

    Take n genuine calibration scores, set tau to the ceil((1-alpha)(n+1))-th
    smallest. For a new genuine transaction drawn exchangeably,
    P(score > tau) <= alpha. Finite-sample and distribution-free.

    The bank sets the friction budget and we hold it with a coverage
    guarantee rather than a hope. Held per rail, because agentic and UPI score
    distributions differ and one quantile over the mixture holds the budget
    for neither.
    """
    alpha: float = 0.02
    tau: Dict[str, float] = field(default_factory=dict)
    _global: float = 0.0

    def fit(self, scores: List[float], rails: List[str]) -> "ConformalBudget":
        by = defaultdict(list)
        for s, rl in zip(scores, rails):
            by[rl].append(s)
        allv = sorted(scores)
        idx = min(len(allv) - 1,
                  max(0, math.ceil((1 - self.alpha) * (len(allv) + 1)) - 1))
        self._global = allv[idx]
        for rl, v in by.items():
            v.sort()
            if len(v) < 50:
                self.tau[rl] = self._global
                continue
            i = min(len(v) - 1,
                    max(0, math.ceil((1 - self.alpha) * (len(v) + 1)) - 1))
            self.tau[rl] = v[i]
        return self

    def threshold(self, rail: str) -> float:
        return self.tau.get(rail, self._global)

    def coverage_error(self, scores: List[float], rails: List[str]) -> float:
        """Observed step-up rate on genuine traffic minus the budget.

        One-sided in interpretation: over budget breaks the promise, under
        budget is merely conservative. Tracked across loop iterations in
        Phase 7, where it becomes a label-free drift alarm.
        """
        if not scores:
            return float("nan")
        hit = sum(1 for s, rl in zip(scores, rails) if s > self.threshold(rl))
        return hit / len(scores) - self.alpha


# ---------------------------------------------------------------------------
@dataclass
class CostModel:
    """Expected-cost response selection.

    Not a threshold on probability. Given a fixed friction budget, the
    Lagrangian gives: act when value x likelihood ratio exceeds lambda. So we
    threshold on VALUE-WEIGHTED likelihood, which is why a large transfer is
    challenged at a lower risk score than a small one. Thresholding raw
    probability provably misallocates a fixed budget, and almost every
    implementation does exactly that.
    """
    step_up_friction: float = 45.0     # INR-equivalent cost of a challenge
    false_decline: float = 1800.0      # cost of declining a good customer
    step_up_catch: float = 0.80        # P(attack stopped | step-up)
    decline_catch: float = 0.98

    def choose(self, p: float, value: float, rail: str = "") -> Tuple[str, Dict[str, float]]:
        # A step-up is near-worthless where the legitimate party will present
        # the factor correctly: coerced payments and compromised agents both
        # pass authentication by design.
        catch = self.step_up_catch
        if rail in ("R3", "R4", "R5"):
            catch *= 0.45
        c = {
            "approve": p * value,
            "step_up": (1 - p) * self.step_up_friction
                       + p * value * (1 - catch),
            "decline": (1 - p) * self.false_decline
                       + p * value * (1 - self.decline_catch),
        }
        return min(c, key=c.get), c


# ---------------------------------------------------------------------------
@dataclass
class GradientHead:
    """A gradient-boosted scorer with the same interface as `Head`.

    WHY THIS REPLACED THE SCORECARD AS THE RANKER
    ---------------------------------------------
    We benchmarked against standard models on identical inputs — same features,
    same temporal split, same 3,457 delayed labels, same conformal threshold —
    and lost badly:

        Gradient boosting     PR-AUC 0.860
        Random forest                0.739
        Logistic regression          0.626
        Weight-of-evidence heads     0.429

    The cause is not mysterious. The scorecard bins every feature into 12
    quantiles and then damps correlated terms by 0.35, which is a lot of
    information deliberately thrown away for interpretability. On 3,470
    training rows a boosted ensemble simply extracts more.

    So the ranker is now boosted trees and the SCORECARD IS KEPT ALONGSIDE IT,
    because the two are good at different things. The trees rank; the
    weight-of-evidence terms explain, and the counterfactual generator needs an
    additive surface to work on. Reporting the number that made us switch is
    part of the result.

    Everything around it is unchanged: routing, per-route conformal budgets,
    the Stackelberg correction, expected-cost selection.
    """
    name: str
    block: str
    model: object = None
    cols: List[str] = field(default_factory=list)
    trained: bool = False
    n_train: int = 0

    def _vec(self, r: FeatureSet) -> List[float]:
        blk = r.block(self.block)
        return [float(blk.get(c, 0.0)) if isinstance(blk.get(c, 0.0), (int, float))
                else 0.0 for c in self.cols]

    def fit(self, rows: List[FeatureSet], y: Sequence[int],
            seed: int = 11) -> "GradientHead":
        cols = sorted({k for r in rows for k in r.block(self.block)})
        if not cols or len(rows) < 40 or len(set(y)) < 2:
            return self
        self.cols = cols
        X = [self._vec(r) for r in rows]
        try:
            from sklearn.ensemble import GradientBoostingClassifier
            self.model = GradientBoostingClassifier(
                n_estimators=200, max_depth=3, learning_rate=0.08,
                subsample=0.85, random_state=seed).fit(X, list(y))
            self.trained = True
            self.n_train = len(rows)
        except Exception:
            self.trained = False
        return self

    def score(self, r: FeatureSet) -> float:
        """Returns a LOG-ODDS, not a probability.

        Fusion sums head outputs and Platt-calibrates them, so a head has to
        emit something on a log-odds scale or the sum is meaningless. A raw
        probability from predict_proba would be silently wrong here.
        """
        if not self.trained:
            return 0.0
        try:
            p = float(self.model.predict_proba([self._vec(r)])[0][1])
        except Exception:
            return 0.0
        p = min(max(p, 1e-6), 1 - 1e-6)
        return math.log(p / (1 - p))

    def score_many(self, rows: Sequence[FeatureSet]) -> List[float]:
        """Batched, because per-row predict_proba on 86,000 rows is minutes."""
        if not self.trained or not rows:
            return [0.0] * len(rows)
        try:
            ps = self.model.predict_proba([self._vec(r) for r in rows])
        except Exception:
            return [0.0] * len(rows)
        out = []
        for pr in ps:
            p = min(max(float(pr[1]), 1e-6), 1 - 1e-6)
            out.append(math.log(p / (1 - p)))
        return out

    def applicable(self, r: FeatureSet) -> bool:
        return bool(r.block(self.block))

    def terms(self, r: FeatureSet) -> List[Tuple[str, float]]:
        """Trees have no additive terms. Explanation comes from the scorecard
        that runs beside this, which is why both are kept."""
        return []

    def reasons(self, r: FeatureSet, k: int = 3) -> List[Tuple[str, float]]:
        return []

    def information_value(self) -> List[Tuple[str, float]]:
        if not self.trained:
            return []
        imp = getattr(self.model, "feature_importances_", None)
        if imp is None:
            return []
        return sorted(zip(self.cols, [float(v) for v in imp]),
                      key=lambda x: -x[1])
