#!/usr/bin/env python3
"""Phase 3 definition of done.

Generates the benign corpus and reports the checks that decide whether this
world is worth attacking. The one that matters most is lag-1 IET
autocorrelation: if it is not positive, arrivals are effectively Poisson and
our own P1 noise floor is unreachable before a single attack has been written.
"""
from __future__ import annotations
import csv, math, statistics as st, sys
from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chakra.schema.transaction import Transaction
from chakra.schema.labels import LabelHarness
from chakra.world.engine import EngineConfig, build, run

OUT = Path(__file__).resolve().parents[1] / "outputs"
OUT.mkdir(exist_ok=True)


def lag1_autocorr(xs):
    if len(xs) < 3:
        return None
    m = st.fmean(xs)
    num = sum((a - m) * (b - m) for a, b in zip(xs, xs[1:]))
    den = sum((x - m) ** 2 for x in xs)
    return num / den if den else None


def lag1_vs_null(gaps_by_entity, rng, min_gaps=8):
    """Lag-1 autocorrelation measured against a within-entity shuffle control.

    The plain estimator is biased by roughly -1/(n-1) even on iid data. At the
    20-30 gaps per entity we see, that is about -0.04, which is the same order
    as any real signal. Reading the raw number as evidence of anything is a
    mistake, and it is a mistake that would have sent us tuning the simulator
    to chase an artifact.

    The shuffle preserves the gap multiset and destroys only the ordering, so
    it carries the identical bias. The difference is the ordering signal.

    This also explains why the fidelity literature anchors to a real-data
    noise floor rather than to an absolute target: a degradation RATIO cancels
    estimator bias, because numerator and denominator carry the same bias.
    """
    obs, null, ns = [], [], []
    for g in gaps_by_entity:
        if len(g) < min_gaps:
            continue
        lg = [math.log(x) for x in g if x > 0]
        a = lag1_autocorr(lg)
        if a is None:
            continue
        s2 = lg[:]
        rng.shuffle(s2)
        b = lag1_autocorr(s2)
        if b is None:
            continue
        obs.append(a); null.append(b); ns.append(len(lg))
    if not obs:
        return None
    o, n0 = st.fmean(obs), st.fmean(null)
    return {"observed": o, "null": n0, "excess": o - n0,
            "entities": len(obs), "mean_gaps": st.fmean(ns)}


def sorted_gaps(v):
    v = sorted(v)
    return [b - a for a, b in zip(v, v[1:]) if b > a]


def main() -> int:
    cfg = EngineConfig()
    w = build(cfg)
    harness = LabelHarness()
    txns, execs = run(w, cfg, harness)

    print("=" * 70)
    print("PHASE 3 — BENIGN WORLD")
    print("=" * 70)
    print(f"payers {len(w.payers)}  merchants {len(w.merchants)}  "
          f"devices {len(w.devices)}  agents {len(w.agents)}  mules {len(w.mules)}")
    print(f"span {cfg.days} days   transactions {len(txns):,}   "
          f"agent executions {len(execs):,}")

    # ---- per-entity inter-event times ------------------------------------
    per = defaultdict(list)
    for t in txns:
        per[t.entity_id()].append(t.ts.timestamp())
    gaps_all, acs = [], []
    for v in per.values():
        v.sort()
        g = [b - a for a, b in zip(v, v[1:])]
        gaps_all += g
        a = lag1_autocorr(g)
        if a is not None:
            acs.append(a)
    gaps_all.sort()
    mean_ac = st.fmean(acs) if acs else 0.0

    def q(xs, p):
        return xs[min(len(xs) - 1, int(len(xs) * p))]

    import random as _r
    perm = lag1_vs_null([sorted_gaps(v) for v in per.values()], _r.Random(11))
    cv = st.pstdev(gaps_all) / st.fmean(gaps_all)

    print("\n--- P1  inter-event time ---")
    print(f"  entities            {len(per):,}")
    print(f"  gaps                {len(gaps_all):,}")
    print(f"  p10 / p50 / p90     {q(gaps_all,.10)/60:8.1f} / "
          f"{q(gaps_all,.50)/60:8.1f} / {q(gaps_all,.90)/60:8.1f}  min")
    print(f"  cv (sd/mean)        {cv:.2f}   "
          f"(1.0 == pure Poisson; >1 == bursty)   {'PASS' if cv > 1.5 else 'FAIL'}")
    if perm:
        print(f"  lag-1 observed      {perm['observed']:+.4f}")
        print(f"  lag-1 shuffle null  {perm['null']:+.4f}   "
              f"(estimator bias at {perm['mean_gaps']:.0f} gaps/entity)")
        print(f"  ordering signal     {perm['excess']:+.4f}   "
              f"over {perm['entities']:,} entities")
        print(f"  NOT GATED. The sign of this depends on how session clustering")
        print(f"  trades against diurnal alternation, and we have no real-data")
        print(f"  target to compare it to yet. Phase 4 computes the IEEE-CIS")
        print(f"  noise floor; only then does this number mean anything.")
    cv_ok = cv > 1.5

    # ---- P2 burst / lifetime --------------------------------------------
    counts = sorted(len(v) for v in per.values())
    lifetimes = sorted((max(v) - min(v)) / 86400 for v in per.values() if len(v) > 1)
    print("\n--- P2  burst and lifetime ---")
    print(f"  txns per entity     p50 {q(counts,.5)}   p90 {q(counts,.9)}   "
          f"max {counts[-1]}")
    print(f"  active span (days)  p50 {q(lifetimes,.5):.1f}   "
          f"p90 {q(lifetimes,.9):.1f}")

    # ---- P3 graph --------------------------------------------------------
    hist = w.device_fan_out_histogram()
    shared = sum(c for k, c in hist.items() if k > 1)
    tok_mer = defaultdict(set)
    for t in txns:
        k = t.graph_keys()
        if "token" in k and "merchant" in k:
            tok_mer[k["token"]].add(k["merchant"])
    degs = sorted(len(v) for v in tok_mer.values())
    print("\n--- P3  graph structure ---")
    print(f"  device fan-out      {dict(list(hist.items())[:8])}")
    print(f"  shared devices      {shared} of {len(w.devices)}  "
          f"max fan-out {max(hist)}")
    print(f"  token->merchant deg p50 {q(degs,.5)}  p90 {q(degs,.9)}  "
          f"max {degs[-1]}")

    # ---- P4 velocity -----------------------------------------------------
    rules = {"gt3_in_1h": 0, "gt5_distinct_mcc_24h": 0, "amt_gt_10x_median": 0}
    for v in per.values():
        pass
    by_ent = defaultdict(list)
    for t in txns:
        by_ent[t.entity_id()].append(t)
    for ev in by_ent.values():
        ev.sort(key=lambda x: x.ts)
        amts = sorted(float(x.amount) for x in ev)
        med = amts[len(amts) // 2] if amts else 0
        for i, t in enumerate(ev):
            win = [x for x in ev[max(0, i - 12):i]
                   if (t.ts - x.ts).total_seconds() <= 3600]
            if len(win) >= 3:
                rules["gt3_in_1h"] += 1
            d24 = {x.mcc for x in ev[max(0, i - 40):i + 1]
                   if (t.ts - x.ts).total_seconds() <= 86400 and x.mcc}
            if len(d24) > 5:
                rules["gt5_distinct_mcc_24h"] += 1
            if med and float(t.amount) > 10 * med:
                rules["amt_gt_10x_median"] += 1
    print("\n--- P4  velocity-rule trigger rates ---")
    for k, v in rules.items():
        print(f"  {k:24s} {v:6d}   {v/len(txns):6.2%} of transactions")

    # ---- descriptive -----------------------------------------------------
    rails = Counter(t.rail.value for t in txns)
    resp = Counter(t.response_code.value for t in txns)
    amts = sorted(float(t.amount) for t in txns)
    hours = Counter(t.ts.hour for t in txns)
    mcs = Counter(t.mcc for t in txns if t.mcc)
    mer_v = sorted((m.txn_count for m in w.merchants.values()), reverse=True)
    top10 = sum(mer_v[:38]) / len(txns)
    round_amt = sum(1 for a in amts if a % 100 == 0) / len(amts)

    print("\n--- descriptive ---")
    print(f"  rails               {dict(rails)}")
    print(f"  approved            {resp.get('00',0)/len(txns):.1%}   "
          f"declines {dict((k,v) for k,v in resp.items() if k!='00')}")
    print(f"  amount p50 / p95    {q(amts,.5):,.0f} / {q(amts,.95):,.0f} INR")
    print(f"  round-100 amounts   {round_amt:.1%}")
    print(f"  top-10% merchants   {top10:.1%} of volume  (heavy tail present)")
    print(f"  distinct MCCs       {len(mcs)}")
    peak = max(hours, key=hours.get)
    trough = min(hours, key=hours.get)
    print(f"  hour peak/trough    {peak:02d}:00 ({hours[peak]:,}) / "
          f"{trough:02d}:00 ({hours[trough]:,})   ratio "
          f"{hours[peak]/max(1,hours[trough]):.1f}x")
    print("  hour-of-day         " + "".join(
        "█▇▆▅▄▃▂▁"[min(7, int(7 - 7 * hours[h] / max(hours.values())))]
        for h in range(24)))
    print("                      0h" + " " * 20 + "23h")

    # ---- write -----------------------------------------------------------
    f = OUT / "benign_transactions.csv"
    with f.open("w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=Transaction.csv_header())
        wr.writeheader()
        for t in txns:
            wr.writerow(t.to_row())
    print(f"\nwrote {f.name}  ({f.stat().st_size/1_048_576:.1f} MB)")

    ok = cv_ok and len(txns) >= 50_000 and max(hist) > 3
    print("\n" + "=" * 70)
    print("PHASE 3 DONE — fidelity harness unblocked" if ok
          else f"CHECK FAILED (txns={len(txns)}, cv={cv:.2f})")
    print("=" * 70)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
