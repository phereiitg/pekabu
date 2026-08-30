"""The world engine.

Benign traffic only. No attacks. Phase 5 adds plugins that perturb this world;
nothing in this file knows fraud exists.

Event-driven rather than tick-polling. Each payer holds its next arrival on a
heap, so cost scales with events rather than with ticks x entities.
"""
from __future__ import annotations
import heapq, math, random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from chakra.schema.enums import Rail, OnboardingPath, AgentState, TrustLink
from chakra.schema.transaction import Transaction
from chakra.schema.entity import (World, Payer, Device, Merchant, Agent, Mule,
                           Adversary, BehaviourProfile, activity_chain)
from chakra.schema.mandate import Mandate, IntentCapsule, Execution
from chakra.schema.labels import LabelHarness, GroundTruth
from chakra.world.arrivals import HawkesArrival, circadian, weekday_factor
from chakra.rails import adapters


# --- MCC-conditional amounts ------------------------------------------------
# A grocery basket and an electronics purchase are not draws from the same
# distribution. Collapsing them is the fastest way to fail P1's amount
# structure while still looking fine on a global histogram.
MCC_AMOUNT = {
    "5411": (5.9, 0.75),   # groceries
    "5812": (6.1, 0.80),   # restaurants
    "5814": (5.3, 0.70),   # fast food
    "4121": (5.4, 0.65),   # ride hailing
    "5999": (6.6, 1.05),   # misc retail
    "5732": (8.2, 0.95),   # electronics
    "5661": (7.4, 0.80),   # footwear
    "5941": (7.5, 0.85),   # sporting goods
    "4900": (6.8, 0.55),   # utilities
    "6011": (8.6, 0.80),   # cash / ATM
    "5541": (6.7, 0.55),   # fuel
    "4814": (5.0, 0.60),   # telecom top-up
}
MCC_LIST = list(MCC_AMOUNT)
MCC_WEIGHTS = [0.17, 0.13, 0.10, 0.09, 0.11, 0.04, 0.03,
               0.03, 0.07, 0.05, 0.10, 0.08]

# Round-number preference. Real payment amounts pile up on 100/500/1000 —
# utilities, top-ups, transfers between people. A pure lognormal has no mass
# at round numbers at all and the histogram looks subtly synthetic.
ROUND_PRONE_MCC = {"4900", "4814", "6011"}


def sample_amount(mcc: str, payer_shift: float, rng: random.Random) -> Decimal:
    mu, sd = MCC_AMOUNT.get(mcc, (6.3, 1.0))
    v = math.exp(rng.gauss(mu + payer_shift, sd))
    v = max(5.0, min(v, 900000.0))
    p_round = 0.42 if mcc in ROUND_PRONE_MCC else 0.14
    if rng.random() < p_round:
        step = 50 if v < 800 else (100 if v < 5000 else 500)
        v = max(step, round(v / step) * step)
    return Decimal(f"{v:.2f}")


# --- intents for benign agent delegation ------------------------------------
MANDATE_LOG = []   # (Mandate, beneficiary, amount, ts, item) for Head C

BENIGN_INTENTS = [
    ("order groceries for the week under 3000", "5411", 3000),
    ("book a cab to the airport", "4121", 1500),
    ("buy running shoes size 9 under 6000", "5661", 6000),
    ("renew the broadband plan", "4900", 2500),
    ("order dinner for two", "5812", 1800),
    ("top up my phone", "4814", 500),
    ("buy a birthday gift under 4000", "5999", 4000),
    ("replace the kettle", "5732", 3500),
]


@dataclass
class EngineConfig:
    n_payers: int = 11000
    n_merchants: int = 900
    n_devices: int = 9200
    n_agents_frac: float = 0.26
    n_mules: int = 120
    # Population, not per-payer rate. IEEE-CIS holds ~24k entities over 45
    # days at a median of 2 events each. Our first calibration had 2,200
    # entities at a median of 15, which passed on volume and failed P2 badly.
    # Cutting the rate alone dropped total events 8x and made P1 and P3 noisy.
    # Many entities each doing little is the shape of the real data.
    days: int = 180
    # 45 days gave 974 training labels out of 35,246 transactions, because a
    # 21-day median chargeback delay against a 45-day corpus means almost
    # nothing has come back by the training cut-off. That is a real operating
    # condition, but it is not the one a deployed model faces — banks train on
    # years of history. 180 days lets genuine delayed labels land instead of
    # forcing us to widen the alert filter, which would have been fixing the
    # measurement rather than the problem.
    seed: int = 7
    origin: datetime = datetime(2026, 3, 1, 0, 0, 0)
    agent_rail_share: float = 0.34     # of an agent-owning payer's volume
    collect_share: float = 0.11        # of UPI volume that is collect


# ---------------------------------------------------------------------------
def build(cfg: EngineConfig) -> World:
    rng = random.Random(cfg.seed)
    w = World(now=cfg.origin, rng=rng)

    for i in range(cfg.n_devices):
        did = f"DEV{i:06d}"
        w.devices[did] = Device(device_id=did, first_seen=cfg.origin)

    # Merchant popularity is heavy-tailed. A uniform merchant distribution
    # destroys the token-merchant bipartite structure the graph head needs.
    for i in range(cfg.n_merchants):
        mid = f"MER{i:06d}"
        mcc = rng.choices(MCC_LIST, weights=MCC_WEIGHTS)[0]
        onb = rng.choices(
            [OnboardingPath.DIRECT_KYC, OnboardingPath.AGGREGATOR,
             OnboardingPath.PAYMENTS_BANK],
            weights=[0.66, 0.26, 0.08])[0]
        w.merchants[mid] = Merchant(
            merchant_id=mid, mcc=mcc,
            acquirer_id=f"ACQ{rng.randint(1, 14):03d}",
            onboarding=onb, created=cfg.origin,
            listing_text=f"{mcc} storefront {i}")
    # zipf-ish base popularity
    pop = {mid: (1.0 / (rank + 1.6) ** 0.85)
           for rank, mid in enumerate(w.merchants)}

    dev_ids = list(w.devices)
    mer_ids = list(w.merchants)
    mer_w = [pop[m] for m in mer_ids]

    for i in range(cfg.n_payers):
        pid = f"PAY{i:06d}"
        prof = BehaviourProfile(
            amount_log_mean=rng.gauss(0.0, 0.32),      # per-payer shift
            amount_log_sd=rng.uniform(0.7, 1.3),
            hour_peak=rng.choices([8, 9, 12, 13, 18, 19, 20, 21, 22],
                                  weights=[.07,.09,.10,.09,.11,.14,.16,.13,.11])[0],
            hour_spread=rng.uniform(2.2, 5.5),
            txn_per_day=max(0.02, rng.lognormvariate(-1.55, 0.95)),
            merchant_loyalty=rng.uniform(0.62, 0.96),
            primary_mccs=rng.sample(MCC_LIST, k=rng.choices([1,2,3],
                                                            weights=[.42,.38,.20])[0]),
            enter_day=(0 if rng.random() < 0.55
                       else rng.randint(0, max(1, cfg.days - 4))),
            exit_day=(cfg.days if rng.random() < 0.60
                      else rng.randint(3, cfg.days)),
            daily_activity=activity_chain(cfg.days, rng))
        mine = [rng.choice(dev_ids)]
        if rng.random() < 0.14:                       # household sharing
            mine.append(rng.choice(dev_ids))
        age = int(rng.gauss(40, 15))
        p = Payer(payer_id=pid, profile=prof,
                  token_pan=f"TOK{i:012d}", vpa=f"u{i}@bank",
                  devices=mine,
                  age=max(18, min(94, age)),
                  is_pwd=rng.random() < 0.035,
                  known_merchants=list(set(
                      rng.choices(mer_ids, weights=mer_w,
                                  k=rng.randint(3, 11)))))
        for d in mine:
            w.devices[d].bound_to.add(pid)
        w.payers[pid] = p

        if rng.random() < cfg.n_agents_frac:
            aid = f"AGT{i:06d}"
            w.agents[aid] = Agent(
                agent_id=aid, payer_id=pid, token_id=f"ATK{i:09d}",
                model_tier=rng.choices(["frontier", "mid", "flash", "open"],
                                       weights=[0.33, 0.31, 0.27, 0.09])[0],
                created=cfg.origin)

    adv = Adversary(adversary_id="ADV001", budget=Decimal("250000"),
                    capability="organised")
    farm = rng.sample(dev_ids, k=4)
    for i in range(cfg.n_mules):
        mid = f"MUL{i:05d}"
        w.mules[mid] = Mule(mule_id=mid, vpa=f"m{i}@ppb",
                            onboarding=OnboardingPath.PAYMENTS_BANK,
                            recruited_at=cfg.origin, ring_id="RING01",
                            dormancy_target=rng.randint(400, 2600))
        adv.controlled_mules.append(mid)
        w.devices[rng.choice(farm)].bound_to.add(mid)
    w.adversaries[adv.adversary_id] = adv

    w._pop = pop           # type: ignore[attr-defined]
    return w


# ---------------------------------------------------------------------------
def run(w: World, cfg: EngineConfig, harness: LabelHarness
        ) -> Tuple[List[Transaction], List[Execution]]:
    rng = w.rng
    horizon = cfg.days * 86400.0
    origin_wd = cfg.origin.weekday()
    pop = w._pop                                    # type: ignore[attr-defined]
    mer_ids = list(w.merchants)
    mer_w = [pop[m] for m in mer_ids]

    agents_by_payer: Dict[str, str] = {a.payer_id: a.agent_id
                                       for a in w.agents.values()}

    # schedule first arrival per payer
    heap: List[Tuple[float, str]] = []
    clocks: Dict[str, HawkesArrival] = {}
    for pid, p in w.payers.items():
        mu = p.profile.txn_per_day / 86400.0
        clocks[pid] = HawkesArrival(mu=mu, tau=rng.uniform(900, 5400))
        t0 = rng.expovariate(mu) * rng.uniform(0.2, 1.0)
        heapq.heappush(heap, (t0, pid))

    txns: List[Transaction] = []
    execs: List[Execution] = []
    n = 0

    while heap:
        t, pid = heapq.heappop(heap)
        if t >= horizon:
            continue
        p = w.payers[pid]
        clk = clocks[pid]

        # circadian and weekday act as an acceptance filter on the arrival,
        # keeping the Hawkes machinery clean
        accept = min(1.0, circadian(t, p.profile.hour_peak,
                                    p.profile.hour_spread) *
                     weekday_factor(t, origin_wd) *
                     p.profile.activity(int(t // 86400)) * 0.42)

        # Sessions. A person opens an app, makes two or three purchases a few
        # minutes apart, then goes quiet until tomorrow.
        #
        # This is the mechanism that puts POSITIVE lag-1 autocorrelation into
        # real inter-event times. Without it the diurnal cycle alternates
        # long-short-long-short and lag-1 comes out negative — measured at
        # -0.117 before this block existed. That is the same defect the
        # fidelity paper proves row-independent generators cannot escape, so
        # inheriting it here would have made our own P1 noise floor
        # unreachable before a single attack was written.
        day = int(t // 86400)
        in_window = p.profile.enter_day <= day <= p.profile.exit_day
        session = 0
        if in_window and rng.random() < accept:
            clk.observe(t)
            session = 1
            while session < 5 and rng.random() < 0.44:
                session += 1

        t_off = 0.0
        for _s in range(session):
            ts = cfg.origin + timedelta(seconds=t + t_off)
            t_off += math.exp(rng.gauss(4.9, 0.85))    # median ~2.2 min
            n += 1

            # merchant: loyalty first, then preferential attachment
            if p.known_merchants and rng.random() < p.profile.merchant_loyalty:
                mid = rng.choice(p.known_merchants)
            else:
                # category loyalty: real cardholders concentrate hard, and
                # uniform merchant choice was producing 5 distinct MCCs a day
                # against a real median of 1
                for _try in range(6):
                    mid = rng.choices(mer_ids, weights=mer_w)[0]
                    if (not p.profile.primary_mccs
                            or w.merchants[mid].mcc in p.profile.primary_mccs):
                        break
                if len(p.known_merchants) < 12:
                    p.known_merchants.append(mid)
            mer = w.merchants[mid]
            amt = sample_amount(mer.mcc, p.profile.amount_log_mean, rng)

            aid = agents_by_payer.get(pid)
            use_agent = aid is not None and rng.random() < cfg.agent_rail_share

            if use_agent:
                agent = w.agents[aid]
                text, mcc_hint, ceiling = rng.choice(BENIGN_INTENTS)
                cap = IntentCapsule(capsule_id=f"CAP{n:09d}",
                                    stated_intent=text,
                                    category_hint=mcc_hint, issued_at=ts)
                man = Mandate(mandate_id=f"MAN{n:09d}", agent_id=aid,
                              payer_id=pid, capsule=cap,
                              ceiling=Decimal(str(ceiling)),
                              allowed_mccs=[mcc_hint],
                              expiry=ts + timedelta(hours=rng.randint(1, 24)),
                              signature=cap.digest())
                # a benign agent stays in scope
                mer_c = [m for m in p.known_merchants
                         if w.merchants[m].mcc == mcc_hint]
                if mer_c:
                    mid = rng.choice(mer_c); mer = w.merchants[mid]
                amt = min(sample_amount(mcc_hint, p.profile.amount_log_mean, rng),
                          Decimal(str(ceiling)) - Decimal("1"))
                if amt <= 0:
                    amt = Decimal("99")
                t_obj = adapters.card_auth(
                    f"T{n:09d}", ts, amt, token_pan=p.token_pan,
                    merchant_id=mid, mcc=mer.mcc, acquirer_id=mer.acquirer_id,
                    rng=rng, agent_id=aid, mandate_id=man.mandate_id,
                    agent_token_id=agent.token_id)
                man.record(amt)
                agent.mandates.append(man)
                # An honest execution buys something from the category it was
                # asked for. Without an item description there is nothing for
                # the semantic check to compare against.
                from chakra.detect.semantic import item_for
                MANDATE_LOG.append((man, mid, amt, ts, item_for(mcc_hint, rng)))
                agent.executions += 1
                agent.age_tick()
                execs.append(Execution(
                    execution_id=f"EX{n:09d}", mandate_id=man.mandate_id,
                    agent_id=aid, ts=ts, amount=amt, mcc=mer.mcc,
                    merchant_id=mid, beneficiary=mid,
                    item_description=text))
            else:
                roll = rng.random()
                if roll < 0.52:
                    dev = p.devices[0]
                    if roll < 0.52 * cfg.collect_share:
                        t_obj = adapters.upi_collect(
                            f"T{n:09d}", ts, amt, payer_vpa=p.vpa,
                            payee_vpa=f"{mid.lower()}@bank",
                            device_binding_id=dev,
                            collect_request_id=f"CR{n:09d}", rng=rng,
                            mcc=mer.mcc, merchant_id=mid,
                            acquirer_id=mer.acquirer_id)
                    else:
                        t_obj = adapters.upi_push(
                            f"T{n:09d}", ts, amt, payer_vpa=p.vpa,
                            payee_vpa=f"{mid.lower()}@bank",
                            device_binding_id=dev, rng=rng,
                            mcc=mer.mcc, merchant_id=mid,
                            acquirer_id=mer.acquirer_id)
                elif roll < 0.80:
                    t_obj = adapters.card_auth(
                        f"T{n:09d}", ts, amt, token_pan=p.token_pan,
                        merchant_id=mid, mcc=mer.mcc,
                        acquirer_id=mer.acquirer_id, rng=rng)
                else:
                    t_obj = adapters.card_auth(
                        f"T{n:09d}", ts, amt, token_pan=p.token_pan,
                        merchant_id=mid, mcc=mer.mcc,
                        acquirer_id=mer.acquirer_id, rng=rng, present=True,
                        terminal_id=f"TRM{rng.randint(1, 2600):06d}")

            txns.append(t_obj)
            p.last_txn_ts, p.txn_count = ts, p.txn_count + 1
            mer.txn_count += 1
            harness.register(GroundTruth(txn_id=t_obj.txn_id, is_fraud=False,
                                         trust_link=TrustLink.NONE),
                             ts, t_obj.rail, rng)

        gap = clk.next_gap(t, rng)
        heapq.heappush(heap, (t + gap, pid))

    for m in w.mules.values():
        for _ in range(int(horizon // 3600)):
            m.tick()
    w.now = cfg.origin + timedelta(seconds=horizon)
    txns.sort(key=lambda x: x.ts)
    return txns, execs
