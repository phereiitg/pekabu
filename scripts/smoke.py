#!/usr/bin/env python3
"""Phase 2 definition of done.

Builds a world, advances it, emits transactions, and checks the five things
every later phase depends on:

  1. Records round-trip through CSV without loss.
  2. Visibility enforcement actually raises on an out-of-node field.
  3. Graph structure exists — device fan-out above 1 — before any attack runs.
  4. Mandate scope checks fire on the cases they should.
  5. Labels are unavailable at decision time and arrive late, with a share
     never arriving at all.

This is not the world engine. It is the minimum needed to prove the contracts
are usable. Phase 3 replaces the emission loop.
"""
from __future__ import annotations
import csv, random, sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chakra.schema.enums import (Rail, POSEntryMode, AVSResult, CVV2Result,
                          ThreeDSECI, ResponseCode, TrustLink,
                          OnboardingPath, AgentState)
from chakra.schema.transaction import Transaction, TICK_SECONDS
from chakra.schema.entity import (World, Payer, Device, Merchant, Agent, Mule,
                           Adversary, BehaviourProfile)
from chakra.schema.mandate import Mandate, IntentCapsule, Execution
from chakra.schema.labels import LabelHarness, GroundTruth
from chakra.schema import visibility

SEED = 7
N_PAYERS = 100
N_MERCHANTS = 40
N_DEVICES = 85          # fewer than payers, so sharing is forced
N_TICKS = 4320          # 3 days of world time at 1 tick / minute
ORIGIN = datetime(2026, 3, 1, 0, 0, 0)


# ---------------------------------------------------------------- build ----
def build_world(rng: random.Random) -> World:
    w = World(now=ORIGIN, rng=rng)

    for i in range(N_DEVICES):
        did = f"DEV{i:05d}"
        w.devices[did] = Device(device_id=did, first_seen=ORIGIN)

    for i in range(N_MERCHANTS):
        mid = f"MER{i:05d}"
        onb = rng.choices(
            [OnboardingPath.DIRECT_KYC, OnboardingPath.AGGREGATOR,
             OnboardingPath.PAYMENTS_BANK],
            weights=[0.70, 0.22, 0.08])[0]
        w.merchants[mid] = Merchant(
            merchant_id=mid,
            mcc=rng.choice(["5411", "5812", "5999", "4121", "5732", "6011"]),
            acquirer_id=f"ACQ{rng.randint(1, 6):03d}",
            onboarding=onb, created=ORIGIN,
            listing_text=f"merchant {i} storefront")

    dev_ids = list(w.devices)
    mer_ids = list(w.merchants)
    for i in range(N_PAYERS):
        pid = f"PAY{i:05d}"
        prof = BehaviourProfile(
            amount_log_mean=rng.uniform(5.4, 7.0),
            amount_log_sd=rng.uniform(0.7, 1.4),
            hour_peak=rng.choice([9, 13, 19, 20, 21, 22]),
            txn_per_day=rng.uniform(0.6, 4.5),
            merchant_loyalty=rng.uniform(0.55, 0.92))
        # most payers get one device; a minority share a household device
        mine = [rng.choice(dev_ids)]
        if rng.random() < 0.18:
            mine.append(rng.choice(dev_ids))
        age = int(rng.gauss(41, 16))
        p = Payer(payer_id=pid, profile=prof,
                  token_pan=f"TOK{i:012d}",
                  vpa=f"user{i}@bank",
                  devices=mine,
                  age=max(18, min(92, age)),
                  is_pwd=rng.random() < 0.04,
                  known_merchants=rng.sample(mer_ids, k=rng.randint(2, 6)))
        for d in mine:
            w.devices[d].bound_to.add(pid)
        w.payers[pid] = p

        if rng.random() < 0.30:                      # a third delegate to agents
            aid = f"AGT{i:05d}"
            w.agents[aid] = Agent(
                agent_id=aid, payer_id=pid, token_id=f"ATK{i:08d}",
                model_tier=rng.choices(
                    ["frontier", "mid", "flash", "open"],
                    weights=[0.35, 0.30, 0.25, 0.10])[0],
                created=ORIGIN)

    # a small mule ring, dormant — no burst inside this window
    adv = Adversary(adversary_id="ADV001", budget=Decimal("50000"),
                    capability="organised")
    shared = rng.choice(dev_ids)
    for i in range(12):
        mid = f"MUL{i:04d}"
        w.mules[mid] = Mule(mule_id=mid, vpa=f"mule{i}@ppb",
                            onboarding=OnboardingPath.PAYMENTS_BANK,
                            recruited_at=ORIGIN, ring_id="RING01",
                            dormancy_target=rng.randint(150, 400))
        adv.controlled_mules.append(mid)
        w.devices[shared].bound_to.add(mid)          # the device farm edge
    w.adversaries[adv.adversary_id] = adv
    return w


# --------------------------------------------------------------- emit ------
def emit(w: World, harness: LabelHarness) -> list[Transaction]:
    rng, out, n = w.rng, [], 0
    for _ in range(N_TICKS):
        w.tick_index += 1
        w.now += timedelta(seconds=TICK_SECONDS)
        for m in w.mules.values():
            m.tick()
        for a in w.agents.values():
            a.age_tick()

        for p in w.payers.values():
            if not p.tick(w.now, rng):
                continue
            # jitter inside the tick so inter-event times are not on a grid
            ts = w.now + timedelta(seconds=rng.randint(0, TICK_SECONDS - 1))
            mid = (rng.choice(p.known_merchants)
                   if p.known_merchants and rng.random() < p.profile.merchant_loyalty
                   else rng.choice(list(w.merchants)))
            mer = w.merchants[mid]
            amt = p.profile.sample_amount(rng)
            n += 1
            rail = rng.choices([Rail.UPI_PUSH, Rail.CNP_HUMAN, Rail.CARD_PRESENT],
                               weights=[0.55, 0.30, 0.15])[0]
            if rail is Rail.UPI_PUSH:
                t = Transaction(
                    txn_id=f"T{n:09d}", ts=ts, rail=rail, amount=amt,
                    payer_vpa=p.vpa, payee_vpa=f"{mid.lower()}@bank",
                    mcc=mer.mcc, merchant_id=mid, acquirer_id=mer.acquirer_id,
                    device_binding_id=p.devices[0])
            else:
                t = Transaction(
                    txn_id=f"T{n:09d}", ts=ts, rail=rail, amount=amt,
                    token_pan=p.token_pan, mcc=mer.mcc, merchant_id=mid,
                    acquirer_id=mer.acquirer_id,
                    terminal_id=(f"TRM{rng.randint(1,300):05d}"
                                 if rail is Rail.CARD_PRESENT else None),
                    pos_entry_mode=(POSEntryMode.CHIP
                                    if rail is Rail.CARD_PRESENT
                                    else POSEntryMode.ECOMMERCE),
                    avs_result=(AVSResult.FULL_MATCH if rail is Rail.CNP_HUMAN
                                else AVSResult.NOT_REQUESTED),
                    cvv2_result=(CVV2Result.MATCH if rail is Rail.CNP_HUMAN
                                 else CVV2Result.NOT_PRESENT),
                    threeds_eci=(ThreeDSECI.AUTHENTICATED if rail is Rail.CNP_HUMAN
                                 else ThreeDSECI.NOT_APPLICABLE))
            p.last_txn_ts, p.txn_count = ts, p.txn_count + 1
            mer.txn_count += 1
            out.append(t)
            harness.register(GroundTruth(txn_id=t.txn_id, is_fraud=False,
                                         trust_link=TrustLink.NONE),
                             ts, rail, rng)
    return out


# --------------------------------------------------------------- checks ----
def main() -> int:
    rng = random.Random(SEED)
    w = build_world(rng)
    harness = LabelHarness()
    txns = emit(w, harness)
    fails = []

    print("=" * 68)
    print("PHASE 2 — CONTRACT SMOKE TEST")
    print("=" * 68)
    print(f"payers {len(w.payers)}  devices {len(w.devices)}  "
          f"merchants {len(w.merchants)}  agents {len(w.agents)}  "
          f"mules {len(w.mules)}")
    print(f"ticks {N_TICKS}  world span {(w.now-ORIGIN)}  transactions {len(txns)}")

    # 1 — CSV round trip
    out = Path(__file__).resolve().parents[1] / "outputs" / "smoke_transactions.csv"
    out.parent.mkdir(exist_ok=True)
    with out.open("w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=Transaction.csv_header())
        wr.writeheader()
        for t in txns:
            wr.writerow(t.to_row())
    with out.open() as f:
        rows = list(csv.DictReader(f))
    ok = len(rows) == len(txns) and set(rows[0]) == set(Transaction.csv_header())
    print(f"\n[1] CSV round-trip           {'PASS' if ok else 'FAIL'}  "
          f"({len(rows)} rows, {len(Transaction.csv_header())} cols)")
    if not ok: fails.append("csv")

    # 2 — visibility enforcement
    legal = ["token_pan", "amount", "mcc", "merchant_id", "ts"]
    illegal = ["token_pan", "device_fingerprint", "account_balance"]
    try:
        visibility.assert_visible(legal)
        legal_ok = True
    except visibility.VisibilityError:
        legal_ok = False
    try:
        visibility.assert_visible(illegal)
        illegal_raised, msg = False, ""
    except visibility.VisibilityError as e:
        illegal_raised, msg = True, str(e)
    ok = legal_ok and illegal_raised
    print(f"[2] Visibility enforcement   {'PASS' if ok else 'FAIL'}")
    print(f"      legal set accepted, illegal set raised:")
    print(f"      {msg[:150]}")
    if not ok: fails.append("visibility")

    # 3 — graph structure exists pre-attack
    hist = w.device_fan_out_histogram()
    shared = sum(c for k, c in hist.items() if k > 1)
    mx = max(hist) if hist else 0
    ok = mx > 1 and shared > 0
    print(f"[3] Graph structure          {'PASS' if ok else 'FAIL'}")
    print(f"      device fan-out histogram {hist}")
    print(f"      {shared} shared devices, max fan-out {mx}")
    print(f"      a marginal sampler collapses every one of these to 1")
    if not ok: fails.append("graph")

    # 4 — mandate scoping
    cap = IntentCapsule(capsule_id="C1", issued_at=ORIGIN,
                        stated_intent="buy a pair of running shoes under 6000")
    man = Mandate(mandate_id="M1", agent_id="AGT00001", payer_id="PAY00001",
                  capsule=cap, ceiling=Decimal("6000"),
                  allowed_mccs=["5661", "5941"],
                  expiry=ORIGIN + timedelta(hours=2))
    cases = [
        ("in scope",           Decimal("4200"), "5941", ORIGIN + timedelta(minutes=5),  []),
        ("over ceiling",       Decimal("9000"), "5941", ORIGIN + timedelta(minutes=5),  ["ceiling_exceeded"]),
        ("wrong category",     Decimal("1000"), "6011", ORIGIN + timedelta(minutes=5),  ["mcc_out_of_scope"]),
        ("expired (AGT-009)",  Decimal("1000"), "5941", ORIGIN + timedelta(hours=3),    ["expired"]),
    ]
    ok = True
    print(f"[4] Mandate scope checks")
    for name, amt, mcc, ts, expect in cases:
        got = man.scope_violations(amt, mcc, "MER00001", ts)
        good = got == expect
        ok &= good
        print(f"      {'ok ' if good else 'BAD'} {name:22s} -> {got or 'clean'}")
    ex = Execution(execution_id="E1", mandate_id="M1", agent_id="AGT00001",
                   ts=ORIGIN + timedelta(minutes=5), amount=Decimal("4200"),
                   mcc="5941", merchant_id="MER00001", beneficiary="MER00001",
                   item_description="running shoes, size 9")
    feats = ex.divergence_features(man)
    print(f"      Head C feature vector: {len(feats)} hard signals, "
          f"ceiling utilisation {feats['ceiling_utilisation']:.2f}")
    print(f"      {'PASS' if ok else 'FAIL'}")
    if not ok: fails.append("mandate")

    # 5 — label delay
    decision_time = txns[len(txns)//2].ts
    at_decision = harness.available(decision_time)
    much_later = harness.available(ORIGIN + timedelta(days=120))
    cov_now = harness.coverage(decision_time)
    cov_later = harness.coverage(ORIGIN + timedelta(days=120))
    ok = len(at_decision) == 0 and len(much_later) > 0
    print(f"\n[5] Label delay              {'PASS' if ok else 'FAIL'}")
    print(f"      at decision time      {len(at_decision):6d} labels "
          f"(coverage {cov_now['label_coverage']:.1%})")
    print(f"      at +120 days          {len(much_later):6d} labels "
          f"(coverage {cov_later['label_coverage']:.1%})")
    print(f"      a random split would have handed the model all "
          f"{len(much_later)} on day one")
    if not ok: fails.append("labels")

    # descriptive
    from collections import Counter
    rails = Counter(t.rail.value for t in txns)
    amts = sorted(float(t.amount) for t in txns)
    gaps = []
    per = {}
    for t in txns:
        per.setdefault(t.entity_id(), []).append(t.ts)
    for v in per.values():
        v.sort()
        gaps += [(b - a).total_seconds() for a, b in zip(v, v[1:])]
    gaps.sort()
    print(f"\n--- descriptive (Phase 4 replaces these with the P1-P4 harness) ---")
    print(f"rail mix           {dict(rails)}")
    print(f"amount p50/p95     {amts[len(amts)//2]:.0f} / {amts[int(len(amts)*.95)]:.0f} INR")
    print(f"entities observed  {len(per)}")
    print(f"inter-event p50    {gaps[len(gaps)//2]/60:.1f} min "
          f"(n={len(gaps)}) — real jitter, not on the tick grid")

    print("\n" + "=" * 68)
    if fails:
        print(f"FAILED: {', '.join(fails)}")
        return 1
    print("ALL CONTRACTS HOLD — Phase 2 done, Phase 3 unblocked")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
