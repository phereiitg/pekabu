#!/usr/bin/env python3
"""Phase 4 — the fidelity harness. Produces F4.

Three things happen here:

  1. The noise floor: how different real data is from itself, computed by
     splitting IEEE-CIS in half by entity, five times over.
  2. A row-independent baseline built from the real data itself, which is the
     ceiling on what any marginal-fitting generator can achieve.
  3. Our simulator, scored on the same axes against the same floor.

Everything is a ratio. 1.0 means indistinguishable from real variability.
"""
from __future__ import annotations
import json, math, random, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chakra.fidelity import metrics as M
from chakra.fidelity.loaders import (load_ieee, load_chakra, load_sparkov,
                              shuffled_control, PARTITIONS)

DATA = Path(__file__).resolve().parents[1] / "data"
OUT = Path(__file__).resolve().parents[1] / "outputs"
OUT.mkdir(exist_ok=True)
CROP_DAYS = 45.0          # match our simulator's observation window


def fmt(x):
    if x is None or not math.isfinite(x):
        return "   n/a"
    return f"{x:6.2f}" if x < 1000 else f"{x:6.0f}"


def main() -> int:
    rng = random.Random(17)
    print("=" * 78)
    print("PHASE 4 — BEHAVIOURAL FIDELITY")
    print("=" * 78)

    # ---- 1. the floor, under each partition ---------------------------
    print("\n--- 1. Real-data noise floor (IEEE-CIS, split by entity x5) ---")
    print("The UID has to be reconstructed, and the reconstruction moves the")
    print("floor. Reporting one partition and calling it 'the' floor would be")
    print("a choice disguised as a fact.\n")

    floors, reals = {}, {}
    for part in PARTITIONS:
        log = load_ieee(str(DATA / "train_transaction.csv"),
                        str(DATA / "train_identity.csv"),
                        partition=part, crop_days=CROP_DAYS)
        ents = len({e.entity for e in log.events})
        per = log.by_entity()
        multi = sum(1 for v in per.values() if len(v) > 1)
        f = M.noise_floor(log, rng, repeats=5, graph_attr="device")
        floors[part], reals[part] = f, log
        print(f"  {part:14s} events {len(log.events):7,}  entities {ents:7,}  "
              f"multi-event {multi/ents:5.1%}")
        print(f"                 floor  P1_gap {fmt(f.get('P1_gap_dist'))}  "
              f"P1_cv {fmt(f.get('P1_cv'))}  "
              f"P2_count {fmt(f.get('P2_count_dist'))}  "
              f"P3_fanout {fmt(f.get('P3_fanout_dist'))}")

    part = "card1_addr1"
    real, floor = reals[part], floors[part]
    print(f"\n  Using '{part}' for the headline table: it is the coarsest key")
    print(f"  that still separates cardholders, and the only one with enough")
    print(f"  multi-event entities to estimate inter-event timing.")

    # ---- 2. the row-independent ceiling -------------------------------
    print("\n--- 2. Row-independent baseline ---")
    print("Built from the real data by reassigning entities and resampling")
    print("shared attributes from their marginals. This IS a perfectly-fitted")
    print("marginal generator, so no trained model of that family beats it.\n")
    rowindep = shuffled_control(real, rng)
    dr_row = M.degradation(rowindep, real, floor, rng, "device")

    # ---- 3. ours ------------------------------------------------------
    print("--- 3. Chakra ---")
    ours = load_chakra(str(OUT / "benign_transactions.csv")).crop(CROP_DAYS)
    # our world now runs 180 days; the reference is cropped to 45, and burst
    # and lifetime statistics are window-dependent, so both must match
    dr_ours = M.degradation(ours, real, floor, rng, "device")
    print(f"  events {len(ours.events):,}  "
          f"entities {len({e.entity for e in ours.events}):,}  "
          f"span {ours.span_days():.0f} days\n")

    # ---- F4 -----------------------------------------------------------
    # Two groupings, because one composite number hides the whole result.
    #
    # SEQUENCE metrics depend on the ORDER of events within an entity. These
    # are what the fidelity paper proves row-independent generators cannot
    # reproduce, and they are the honest test.
    #
    # MARGINAL metrics depend only on pooled distributions. Our control is
    # built by resampling REAL timestamps and REAL amounts, so it carries the
    # true marginals exactly. That is an oracle no trained generator has.
    # Losing to it here is expected and means nothing; CTGAN, which must
    # approximate those marginals, would do far worse.
    SEQUENCE = {"P1_cv", "P1_frac_1h", "P1_lag1", "P2_burst_density",
                "P4_ge3_in_1h", "P4_ge5_in_24h"}
    MARGINAL = {"P1_gap_dist", "P2_count_dist", "P2_span_dist",
                "P4_amt_gt_5x_median", "P4_ge4_distinct_cat_24h"}
    EXCLUDED = {"P3_fanout_dist", "P3_degree_dist", "P3_shared_frac",
                "P3_motif_rate"}

    def block(title, keys, note):
        print("\n" + title)
        print(f"  {'metric':26s} {'floor':>7s} {'row-indep':>11s} {'chakra':>9s}   ")
        w = l = 0
        for k in sorted(keys):
            a, b = dr_row.get(k), dr_ours.get(k)
            if a is None or b is None:
                continue
            mark = "chakra" if b < a else "row-indep"
            if b < a: w += 1
            else: l += 1
            print(f"  {k:26s} {'1.00':>7s} {fmt(a):>11s} {fmt(b):>9s}   {mark}")
        print(f"  {note}")
        return w, l

    def gm(d, keys):
        v = [d[k] for k in keys if k in d and math.isfinite(d[k]) and d[k] > 0]
        return math.exp(sum(math.log(x) for x in v) / len(v)) if v else float("nan")

    print("=" * 78)
    print("F4 — DEGRADATION RATIOS   (1.0 = indistinguishable from real "
          "variability)")
    print("=" * 78)

    ws, ls = block("SEQUENCE METRICS — what row-independence provably cannot do",
                   SEQUENCE, "")
    print(f"  {'geometric mean':26s} {'1.00':>7s} "
          f"{fmt(gm(dr_row,SEQUENCE)):>11s} {fmt(gm(dr_ours,SEQUENCE)):>9s}   "
          f"chakra wins {ws}/{ws+ls}")

    wm, lm = block("MARGINAL METRICS — control holds the real marginals by "
                   "construction", MARGINAL, "")
    print(f"  {'geometric mean':26s} {'1.00':>7s} "
          f"{fmt(gm(dr_row,MARGINAL)):>11s} {fmt(gm(dr_ours,MARGINAL)):>9s}   "
          f"chakra wins {wm}/{wm+lm}")

    # ---- second reference: Sparkov ------------------------------------
    print("\n" + "=" * 78)
    print("FLOOR COMPARISON — why the reference corpus matters")
    print("=" * 78)
    sp = load_sparkov(str(DATA / "fraudTrain.csv"),
                      crop_days=CROP_DAYS)
    sp_floor = M.noise_floor(sp, rng, repeats=5, graph_attr="merchant")
    print(f"  {'metric':26s} {'IEEE-CIS':>12s} {'Sparkov':>12s} {'ratio':>8s}")
    print(f"  {'':26s} {'(real)':>12s} {'(simulated)':>12s}")
    rat = []
    for k in sorted(floor):
        if k.startswith("P3") or k not in sp_floor:
            continue
        a, b = floor[k], sp_floor[k]
        r = a / b if b > 1e-9 else float("nan")
        if math.isfinite(r):
            rat.append(r)
        print(f"  {k:26s} {a:12.4f} {b:12.4f} {r:8.1f}x")
    if rat:
        rat.sort()
        print(f"\n  Sparkov's floor is {rat[len(rat)//2]:.0f}x tighter at the median.")
    print("""
  This is not a defect in either dataset. Sparkov IS a simulator, so its two
  halves are drawn from one stationary process and differ only by sampling
  noise. Real populations are heterogeneous: two halves of IEEE-CIS contain
  genuinely different people.

  The consequence for anyone reporting degradation ratios: THE FLOOR IS A
  PROPERTY OF THE REFERENCE CORPUS. Scoring against a synthetic reference
  inflates every ratio by roughly an order of magnitude, and two teams using
  different references are not reporting comparable numbers. A fidelity claim
  has to name its reference corpus and state whether that corpus is real.

  We use IEEE-CIS, which is real, and report Sparkov only as a cross-check.""")

    print("\nP3 GRAPH MOTIFS — NOT REPORTED on either dataset")
    print("""  IEEE-CIS: DeviceInfo covers 20.1% of rows; addr1 has 332 distinct values
  across 590,540 transactions. Too little linkage.

  Sparkov:  the card-merchant bipartite graph is 70.3% dense, a median card
  touches 524 of 693 merchants, and zip and street map to exactly one card
  98.7% of the time. Too much linkage, and none of it selective. Those are
  identity fields, not shared attributes.

  The pattern behind both failures is worth stating in the write-up: the
  attributes that link accounts into rings — device fingerprints, IP
  addresses, shipping addresses, phone numbers — are exactly the attributes
  that must be stripped before a dataset can be published. The graph
  structure fraud detection depends on is the structure privacy requires be
  removed. Public benchmarks therefore systematically under-represent the
  signal that matters most, and any team reporting a graph-fidelity number
  from public data should be asked which attribute they used.

  Our own simulator does not have this problem: it emits the linkage because
  it constructed it. That asymmetry is a limitation of the EVALUATION, not
  of the generator, and it belongs in F16 stated in those terms.""")

    json.dump({"floor": floor,
               "row_independent": dr_row,
               "chakra": dr_ours,
               "partition": part,
               "crop_days": CROP_DAYS,
               "floors_by_partition": floors},
              (OUT / "F4_fidelity.json").open("w"), indent=2)
    print(f"\nwrote F4_fidelity.json")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
