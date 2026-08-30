"""Head S — session evidence.

WHY A FIFTH HEAD
----------------
Every other head scores one authorisation. That is the right unit for a card
payment, where a person taps once and the decision is over.

It is the wrong unit for a delegated agent. An agent handed a mandate does not
make one decision — it browses, compares, selects, checks out, confirms, and may
hold an open mandate across several purchases. Two attacks in our taxonomy are
invisible at transaction scale and obvious at session scale:

    AGT-021  context-window escalation — each step is individually reasonable
             and permissions creep upward across many of them
    AGT-023  goal-lock drift — a scheduled prompt reweights objectives a little
             each morning until the agent approves things it would have refused

Scoring each step alone, both look fine. Scoring the sequence, neither does.

WALD'S SEQUENTIAL PROBABILITY RATIO TEST
----------------------------------------
Accumulate log-likelihood ratio across the session and act when the evidence is
sufficient rather than after a fixed number of steps:

    Lambda_t  =  sum_{i<=t}  log [ P(o_i | manipulated) / P(o_i | legitimate) ]

    Lambda_t  >=  ln( (1-beta) / alpha )   ->  intervene
    Lambda_t  <=  ln( beta / (1-alpha) )   ->  clear the session, stop watching
    otherwise                              ->  observe one more step

Wald's optimality result: among all tests with error rates (alpha, beta), the
SPRT minimises the expected number of observations. That matters more here than
almost anywhere, because the cost of intervening early on a delegated payment is
not a declined transaction — it is the destruction of the thing the customer
delegated for. Waiting one step longer than necessary is a real cost, and this
is the test that provably waits the minimum.

WHERE THE PER-STEP LIKELIHOOD COMES FROM
----------------------------------------
The other heads already produce a calibrated log-likelihood ratio per
execution. That is exactly the quantity the SPRT wants to accumulate, so Head S
does not need its own model — it needs a memory. Each execution contributes its
fused LLR to the running total for that agent, and the boundaries convert the
total into a decision.

This also means Head S degrades gracefully: with one observation it says
nothing, which is correct, and its value appears only once a session exists.

HONEST LIMITATION
-----------------
The SPRT assumes independent observations. Consecutive executions by the same
agent are not independent — a compromised agent stays compromised — so the true
error rates are looser than the nominal alpha and beta. That inflates evidence
in the direction of intervening, which is the safer direction, but it means the
boundaries are a design choice rather than a guarantee. We damp the increment to
compensate and say so rather than quoting the nominal rates as if they held.
"""
from __future__ import annotations
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class SessionState:
    """One agent's running evidence."""
    agent_id: str
    lam: float = 0.0
    steps: int = 0
    last_ts: float = 0.0
    peak: float = 0.0
    crossed_at: Optional[int] = None
    history: List[float] = field(default_factory=list)


@dataclass
class SequentialTest:
    """Wald's SPRT over agent mandate sessions.

    alpha   tolerated false-intervention rate
    beta    tolerated miss rate
    gap     seconds of silence after which a session is considered over.
            Measured on the corpus: an agent makes a median of 5 executions
            spread over 96 days, with a 72-hour median gap between them. A
            browse-to-checkout window of a few hours therefore captures nothing
            — mean session length came out at 1.3 steps and the test degenerated
            into a threshold on one score.

            So the session here is not a shopping trip. It is an agent
            operating under a standing delegation over weeks, which is exactly
            where the two attacks this head exists for actually live: AGT-021
            escalates across sessions and AGT-023 drifts a little each morning.
            Fourteen days holds a real sequence together without merging
            unrelated ones.
    damp    increment scaling, because consecutive observations from one agent
            are correlated and the nominal boundaries would otherwise be
            reached on repetition rather than on evidence
    """
    alpha: float = 0.02
    beta: float = 0.20
    gap: float = 14 * 86400.0
    damp: float = 0.55

    _s: Dict[str, SessionState] = field(default_factory=dict)

    @property
    def upper(self) -> float:
        return math.log((1.0 - self.beta) / self.alpha)

    @property
    def lower(self) -> float:
        return math.log(self.beta / (1.0 - self.alpha))

    # ------------------------------------------------------------------
    def observe(self, agent_id: str, llr: float, ts: float) -> Dict[str, float]:
        """Add one execution and return the session block.

        The features are returned BEFORE the increment is applied, so a
        transaction is never scored using evidence it supplied itself — the
        same rule the per-entity aggregates follow everywhere else.
        """
        st = self._s.get(agent_id)
        if st is None or (ts - st.last_ts) > self.gap:
            # a new session: the previous one either concluded or went quiet
            st = SessionState(agent_id=agent_id, last_ts=ts)
            self._s[agent_id] = st

        # what the session looked like coming into this step
        out = {
            'sprt_lambda': st.lam,
            'sprt_steps': float(st.steps),
            'sprt_peak': st.peak,
            'sprt_to_upper': st.lam / self.upper if self.upper else 0.0,
            'sprt_crossed': 1.0 if st.crossed_at is not None else 0.0,
            'sprt_session_age': (ts - st.last_ts) if st.steps else 0.0,
            'sprt_drift': (st.history[-1] - st.history[-2]
                           if len(st.history) >= 2 else 0.0),
        }

        # then accumulate
        st.lam += self.damp * llr
        st.steps += 1
        st.last_ts = ts
        st.peak = max(st.peak, st.lam)
        st.history.append(st.lam)
        if st.crossed_at is None and st.lam >= self.upper:
            st.crossed_at = st.steps
        if st.lam <= self.lower:
            # cleared — stop carrying evidence against this agent
            st.lam = 0.0
            st.history.clear()
        return out

    # ------------------------------------------------------------------
    def decision(self, agent_id: str) -> str:
        st = self._s.get(agent_id)
        if st is None or st.steps == 0:
            return 'no session'
        if st.lam >= self.upper:
            return 'intervene'
        if st.lam <= self.lower:
            return 'cleared'
        return 'observe'

    def trace(self, agent_id: str) -> List[float]:
        st = self._s.get(agent_id)
        return list(st.history) if st else []

    def summary(self) -> Dict[str, float]:
        n = len(self._s)
        if not n:
            return {}
        crossed = [s for s in self._s.values() if s.crossed_at is not None]
        return {
            'sessions': float(n),
            'crossed': float(len(crossed)),
            'mean_steps_to_cross': (sum(s.crossed_at for s in crossed) / len(crossed)
                                    if crossed else 0.0),
            'mean_session_len': sum(s.steps for s in self._s.values()) / n,
            'upper': self.upper,
            'lower': self.lower,
        }
