#!/usr/bin/env python3
"""F9b — the routed detector portfolio.

Answers the brief's phrase "detection algorithms and their efficacy" as a
plural. Reports a complete route x head matrix, then compares the routed
portfolio against a single monolithic fusion AT MATCHED FRICTION, which is the
only comparison that means anything.
"""
from __future__ import annotations
import csv, json, math, random, sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chakra.detect.features import FeatureBuilder, FeatureSet
from chakra.detect.heads import Head, Fusion, ConformalBudget, CostModel
from chakra.detect.portfolio import (Portfolio, route_of, ROUTE_HEADS, ROUTE_ALPHA,
                              ROUTE_RATIONALE)
from scripts.run_detect import load_corpus, pr_auc, TRAIN_FRAC, FAST_DELAY_HOURS
from chakra.schema.enums import ResponseCode

OUT = Path(__file__).resolve().parents[1] / "outputs"
OUT.mkdir(exist_ok=True)


def main() -> int:
    rng = random.Random(37)
    txns, gt = load_corpus()

    mand = {}
    for r in csv.DictReader((OUT / "mandates.csv").open()):
        mand[r["mandate_id"]] = {
            "ceiling": float(r["ceiling"]),
            "allowed_mccs": [x for x in r["allowed_mccs"].split("|") if x],
            "expiry": (datetime.fromisoformat(r["expiry_ts"]).timestamp()
                       if r["expiry_ts"] else None),
            "issued": (datetime.fromisoformat(r["issued_ts"]).timestamp()
                       if r["issued_ts"] else None),
            "hint": r["category_hint"] or None}

    fb = FeatureBuilder(node="network", mandates=mand)
    feats = [fb.build(t) for t in txns]
    has_agent = {t.txn_id: bool(t.agent_id) for t in txns}
    has_mand = {t.txn_id: bool(t.mandate_id) for t in txns}

    def rfn(fs: FeatureSet) -> str:
        return route_of(fs, has_agent.get(fs.txn_id, False),
                        has_mand.get(fs.txn_id, False))

    cut = txns[int(len(txns) * TRAIN_FRAC)].ts

    # same two-stream label construction as Phase 6
    label = {}
    for t in txns:
        y = int(gt[t.txn_id]["is_fraud"] == "1")
        alert = (rng.random() < 0.10 if t.response_code is not ResponseCode.APPROVED
                 else (rng.random() < 0.22 if float(t.amount) > 20000
                       else rng.random() < 0.012))
        if alert and t.ts + timedelta(hours=FAST_DELAY_HOURS) <= cut:
            label[t.txn_id] = y
        if y and rng.random() < (0.85 if t.rail.has_chargeback else 0.55):
            if t.ts + timedelta(days=rng.lognormvariate(math.log(21), 0.5)) <= cut:
                label[t.txn_id] = 1

    Xtr = [f for f in feats if f.ts <= cut and f.txn_id in label]
    ytr = [label[f.txn_id] for f in Xtr]
    Xte = [f for f in feats if f.ts > cut]
    yte = [int(gt[f.txn_id]["is_fraud"] == "1") for f in Xte]
    vec = {f.txn_id: gt[f.txn_id]["vector_id"] for f in Xte}
    val = {f.txn_id: float(gt[f.txn_id]["value_at_risk"] or 0) for f in Xte}

    print("=" * 80)
    print("F9b — ROUTED DETECTOR PORTFOLIO")
    print("=" * 80)
    print(f"train {len(Xtr):,} labelled ({sum(ytr):,} fraud)   test {len(Xte):,}")

    print("\n--- routes, and why they exist ---")
    print("Keyed on observable fields only. No route depends on a label, an")
    print("attack family, or anything unavailable at decision time.\n")
    for rn, (key, why) in ROUTE_RATIONALE.items():
        print(f"  {rn:10s} [{key}]  budget alpha={ROUTE_ALPHA[rn]:.1%}")
        print(f"             heads: {', '.join(ROUTE_HEADS[rn])}")
        for line in [why[i:i+66] for i in range(0, len(why), 66)]:
            print(f"             {line}")
        print()

    # ---- shared heads, then routed specialists -----------------------
    heads = {
        "A_behavioural": Head("A_behavioural", "A").fit(Xtr, ytr),
        "B_graph":       Head("B_graph", "B").fit(Xtr, ytr),
        "C_intent":      Head("C_intent", "C").fit(
            [x for x in Xtr if x.C], [y for x, y in zip(Xtr, ytr) if x.C])
        if any(x.C for x in Xtr) else Head("C_intent", "C"),
    }
    pf = Portfolio().fit(Xtr, ytr, heads, rfn)

    # ---- the complete matrix -----------------------------------------
    print("=" * 80)
    print("ROUTE x HEAD MATRIX  (PR-AUC on the held-out period)")
    print("Every cell reported. Bad cells are findings, not omissions.")
    print("=" * 80)
    te_by = defaultdict(list)
    for i, f in enumerate(Xte):
        te_by[rfn(f)].append(i)

    hn = ["A_behavioural", "B_graph", "C_intent"]
    print(f"{'route':11s} {'n test':>8s} {'fraud':>6s} " +
          "".join(f"{h.split('_')[0]:>8s}" for h in hn) +
          f"{'routed':>9s}{'used':>18s}")
    print("-" * 80)
    matrix = {}
    for rn in ("agentic", "push", "card", "recurring"):
        idx = te_by.get(rn, [])
        if not idx:
            continue
        sub = [Xte[i] for i in idx]
        suby = [yte[i] for i in idx]
        row = {}
        cells = ""
        for h in hn:
            hd = heads[h]
            if not hd.trained or not any(hd.applicable(x) for x in sub):
                cells += f"{'--':>8s}"
                row[h] = None
                continue
            fu = Fusion([hd]).fit_prior(ytr).calibrate(Xtr, ytr)
            a = pr_auc([fu.prob(x) for x in sub], suby)
            row[h] = a
            cells += f"{a:8.3f}"
        m = pf.routes.get(rn)
        ra = (pr_auc([m.score(x) for x in sub], suby)
              if m and m.trained else float("nan"))
        row["routed"] = ra
        matrix[rn] = row
        print(f"{rn:11s} {len(idx):8,} {sum(suby):6,} {cells}"
              f"{ra:9.3f}  {','.join(h.split('_')[0] for h in ROUTE_HEADS[rn]):>16s}")

    # ---- per-vector recall by route ----------------------------------
    print("\n" + "=" * 80)
    print("PER-VECTOR RECALL AT EACH ROUTE'S OWN BUDGET")
    print("=" * 80)
    print(f"{'vector':11s} {'route':11s} {'n':>5s} {'recall':>8s} "
          f"{'value recall':>13s}")
    per = defaultdict(list)
    for i, f in enumerate(Xte):
        if yte[i]:
            per[vec[f.txn_id]].append(i)
    port_caught, port_value, tot_value = 0, 0.0, 0.0
    for v in sorted(per):
        idx = per[v]
        rn = Counter(rfn(Xte[i]) for i in idx).most_common(1)[0][0]
        m = pf.routes.get(rn)
        caught = [i for i in idx if m and m.trained and m.flags(Xte[i])]
        vv = sum(val[Xte[i].txn_id] for i in idx) or 1.0
        cv = sum(val[Xte[i].txn_id] for i in caught)
        port_caught += len(caught); port_value += cv; tot_value += vv
        print(f"{v:11s} {rn:11s} {len(idx):5d} {len(caught)/len(idx):7.1%} "
              f"{cv/vv:12.1%}")

    # ---- portfolio vs monolith AT MATCHED FRICTION -------------------
    print("\n" + "=" * 80)
    print("ROUTED PORTFOLIO vs MONOLITHIC FUSION, AT MATCHED FRICTION")
    print("=" * 80)
    friction = pf.total_friction(Xte, yte, rfn)
    mono = Fusion(list(heads.values())).fit_prior(ytr).calibrate(Xtr, ytr)
    mono_scores = [mono.prob(x) for x in Xte]
    gen = sorted((s for s, y in zip(mono_scores, yte) if not y), reverse=True)
    k = max(1, int(friction * len(gen)))
    tau = gen[min(k - 1, len(gen) - 1)]
    mono_caught = sum(1 for s, y in zip(mono_scores, yte) if y and s > tau)
    mono_value = sum(val[Xte[i].txn_id] for i in range(len(Xte))
                     if yte[i] and mono_scores[i] > tau)
    nf = sum(yte) or 1

    print(f"  friction (step-up rate on genuine traffic)   {friction:.2%}")
    print(f"  {'':44s} {'routed':>10s} {'monolith':>10s}")
    print(f"  {'transaction recall':44s} {port_caught/nf:9.1%} "
          f"{mono_caught/nf:10.1%}")
    print(f"  {'value recall':44s} {port_value/max(1.0,tot_value):9.1%} "
          f"{mono_value/max(1.0,tot_value):10.1%}")
    lift = ((port_value/max(1.0,tot_value)) /
            max(1e-9, mono_value/max(1.0,tot_value)))
    print(f"  {'value-recall lift from routing':44s} {lift:9.2f}x")
    print("\n  Same data, same heads, same total friction. The only difference")
    print("  is that the portfolio lets each route spend its budget where that")
    print("  route's signal actually lives, instead of one threshold over a")
    print("  mixture of four populations that hold the budget for none of them.")

    json.dump({"matrix": matrix,
               "friction": friction,
               "routed_txn_recall": port_caught / nf,
               "routed_value_recall": port_value / max(1.0, tot_value),
               "mono_txn_recall": mono_caught / nf,
               "mono_value_recall": mono_value / max(1.0, tot_value),
               "route_alpha": ROUTE_ALPHA,
               "route_heads": ROUTE_HEADS},
              (OUT / "F9b_portfolio.json").open("w"), indent=2)
    print("\nwrote F9b_portfolio.json")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
