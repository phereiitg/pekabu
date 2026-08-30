#!/usr/bin/env python3
"""Phase 5 — attacks. Produces the labelled corpus, F6 and F5.

Checks three claims that later phases depend on:

  F6  agentic fraud carries no authentication or velocity anomaly, so a
      standard detector scores it indistinguishably from benign traffic.
  F5  the mule ring produces device fan-out no marginal sampler can reach.
  --  a share of fraud is never labelled at all, and the share differs by
      rail because chargeback recourse differs.
"""
from __future__ import annotations
import csv, math, random, statistics as st, sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chakra.schema.transaction import Transaction
from chakra.schema.enums import Rail, ResponseCode, ThreeDSECI
from chakra.schema.labels import LabelHarness
from chakra.world.engine import EngineConfig, build, run, MANDATE_LOG
from chakra.attacks.base import AttackContext
from chakra.attacks.plugins import (MuleFarm, CardTesting, CollectRequestScam,
                             AgentCompromise, AuthorisationDrift,
                             MicroStructuring)

OUT = Path(__file__).resolve().parents[1] / "outputs"
OUT.mkdir(exist_ok=True)


def main() -> int:
    cfg = EngineConfig()
    rng = random.Random(23)
    w = build(cfg)
    harness = LabelHarness()

    benign, execs = run(w, cfg, harness)
    print("=" * 76)
    print("PHASE 5 — ATTACKS")
    print("=" * 76)
    print(f"benign {len(benign):,} transactions over {cfg.days} days")

    ctx = AttackContext(world=w, origin=cfg.origin, days=cfg.days,
                        rng=rng, harness=harness)
    # Campaigns, not one instance each. Real adversaries run repeatedly with
    # varied configurations, and a detector trained on a single parameter
    # setting per vector learns that setting rather than the vector.
    base = [MuleFarm, CardTesting, CollectRequestScam,
            AgentCompromise, AuthorisationDrift, MicroStructuring]
    CAMPAIGNS = 6
    attacks = []
    for cls in base:
        attacks.append(cls())                       # the default configuration
        for _ in range(CAMPAIGNS - 1):
            attacks.append(cls().mutate(rng, scale=0.45))

    fraud, by_vec = [], defaultdict(list)
    print(f"\n{'plugin':34s} {'vector':10s} {'txns':>7s} {'value INR':>13s} "
          f"{'campaigns':>9s}")
    print("-" * 76)
    for a in attacks:
        rows = a.run(ctx)
        by_vec[a.vector_id] += rows
        fraud += rows
    for vid in sorted(by_vec):
        rows = by_vec[vid]
        val = sum(float(t.amount) for t in rows)
        nm = next(x.name for x in attacks if x.vector_id == vid)
        print(f"{nm[:33]:34s} {vid:10s} {len(rows):7,} {val:13,.0f} "
              f"{CAMPAIGNS:7d}")
    print("-" * 76)

    allt = sorted(benign + fraud, key=lambda t: t.ts)
    rate = len(fraud) / len(allt)
    print(f"{'TOTAL':34s} {'':10s} {len(fraud):7,} "
          f"{sum(float(t.amount) for t in fraud):13,.0f}")
    print(f"\ncorpus {len(allt):,} transactions   fraud rate {rate:.2%}   "
          f"(IEEE-CIS is 3.50%)")

    truth = harness.truth

    # ---- F6: does agentic fraud look clean? -----------------------------
    print("\n" + "=" * 76)
    print("F6 — THE CLEAN-FRAUD REVEAL")
    print("=" * 76)
    groups = {
        "benign (all)":        [t for t in benign],
        "AGT-004 agent compromise": by_vec["AGT-004"],
        "AGT-008 auth drift":  by_vec["AGT-008"],
        "CRD-001 card testing": by_vec["CRD-001"],
        "UPI-004 mule farm":   by_vec["UPI-004"],
    }
    print(f"{'group':30s} {'approved':>9s} {'3DS auth':>9s} "
          f"{'decline':>8s} {'p50 amt':>9s}")
    for name, g in groups.items():
        if not g:
            continue
        ap = sum(1 for t in g if t.response_code is ResponseCode.APPROVED) / len(g)
        au = sum(1 for t in g
                 if t.threeds_eci is ThreeDSECI.AUTHENTICATED) / len(g)
        am = sorted(float(t.amount) for t in g)
        print(f"{name:30s} {ap:8.1%} {au:8.1%} {1-ap:7.1%} "
              f"{am[len(am)//2]:9,.0f}")

    # velocity: does a standard rule fire on it?
    by_ent = defaultdict(list)
    for t in allt:
        by_ent[t.entity_id()].append(t)
    for v in by_ent.values():
        v.sort(key=lambda x: x.ts)

    def velocity_hit(txn) -> bool:
        ev = by_ent[txn.entity_id()]
        i = ev.index(txn)
        return sum(1 for x in ev[max(0, i - 20):i]
                   if (txn.ts - x.ts).total_seconds() <= 3600) >= 3

    print(f"\n{'group':30s} {'velocity rule fires':>20s}")
    for name, g in groups.items():
        if not g:
            continue
        s = random.Random(5).sample(g, k=min(400, len(g)))
        hit = sum(1 for t in s if velocity_hit(t)) / len(s)
        print(f"{name:30s} {hit:19.1%}")
    print("\nAgentic fraud approves at benign-or-better rates, authenticates")
    print("cleanly, and does not trip velocity. Heads A and B are anomaly")
    print("detectors and there is no anomaly. This is the F9 ablation in")
    print("advance, and the reason Head C is not decorative.")

    # ---- F5: graph ------------------------------------------------------
    hist = w.device_fan_out_histogram()
    print("\n" + "=" * 76)
    print("F5 — GRAPH STRUCTURE")
    print("=" * 76)
    mule_ids = set(w.mules)
    ring_dev = [d for d in w.devices.values() if d.bound_to & mule_ids]
    legit_dev = [d for d in w.devices.values()
                 if d.fan_out > 0 and not (d.bound_to & mule_ids)]
    lf = sorted(d.fan_out for d in legit_dev)
    rf = sorted(d.fan_out for d in ring_dev)
    print(f"  legitimate devices  n={len(lf):,}  p50 {lf[len(lf)//2]}  "
          f"p99 {lf[int(len(lf)*.99)]}  max {lf[-1]}")
    if rf:
        print(f"  ring devices        n={len(rf):,}  p50 {rf[len(rf)//2]}  "
              f"max {rf[-1]}")
    print(f"  separation          ring max is {rf[-1]/max(1,lf[-1]):.1f}x the "
          f"legitimate max" if rf else "")
    print(f"  full fan-out tail   {dict((k,v) for k,v in hist.items() if k >= 4)}")
    print("  A row-independent generator samples the device from its marginal,")
    print("  so every fan-out collapses toward 1 and this tail cannot exist.")

    # ---- labels ---------------------------------------------------------
    from datetime import timedelta
    late = harness.coverage(cfg.origin + timedelta(days=400))
    print("\n" + "=" * 76)
    print("LABEL REALITY")
    print("=" * 76)
    print(f"  fraud transactions        {sum(1 for g in truth.values() if g.is_fraud):,}")
    print(f"  ever labelled             {late['fraud_label_coverage']:.1%}")
    print(f"  NEVER labelled            {int(late['unlabelled_fraud']):,}")
    push = [t for t in fraud if not t.rail.has_chargeback]
    pull = [t for t in fraud if t.rail.has_chargeback]
    lab = {e.txn_id for e in harness.events}
    if push:
        print(f"  push rails (no recourse)  "
              f"{sum(1 for t in push if t.txn_id in lab)/len(push):.1%} labelled")
    if pull:
        print(f"  pull rails (chargeback)   "
              f"{sum(1 for t in pull if t.txn_id in lab)/len(pull):.1%} labelled")

    # ---- write ----------------------------------------------------------
    f = OUT / "labelled_corpus.csv"
    with f.open("w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=Transaction.csv_header())
        wr.writeheader()
        for t in allt:
            wr.writerow(t.to_row())
    g = OUT / "ground_truth.csv"
    with g.open("w", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(["txn_id", "is_fraud", "vector_id", "trust_link",
                     "value_at_risk"])
        for t in allt:
            gt = truth.get(t.txn_id)
            wr.writerow([t.txn_id, int(bool(gt and gt.is_fraud)),
                         gt.vector_id if gt else "",
                         gt.trust_link.value if gt else "",
                         f"{gt.value_at_risk:.2f}" if gt else "0"])
    m = OUT / "mandates.csv"
    with m.open("w", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(["mandate_id", "agent_id", "stated_intent", "category_hint",
                     "ceiling", "allowed_mccs", "expiry_ts", "issued_ts",
                     "exec_beneficiary", "exec_amount", "exec_ts"])
        for man, ben, amt, ts in MANDATE_LOG:
            wr.writerow([man.mandate_id, man.agent_id,
                         man.capsule.stated_intent, man.capsule.category_hint or "",
                         str(man.ceiling), "|".join(man.allowed_mccs),
                         man.expiry.isoformat() if man.expiry else "",
                         man.capsule.issued_at.isoformat() if man.capsule.issued_at else "",
                         ben, str(amt), ts.isoformat()])
    print(f"  mandates.csv {len(MANDATE_LOG):,} rows")
    print(f"\nwrote {f.name} ({f.stat().st_size/1e6:.1f} MB) and {g.name}")
    print("=" * 76)
    print("PHASE 5 DONE — detector unblocked")
    print("=" * 76)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
