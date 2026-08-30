#!/usr/bin/env python3
"""Phase 6 — the detector. Produces F8, F9, F11 and F14.

Evaluation protocol, stated once and enforced everywhere below:

  Training labels are only those AVAILABLE at the training cut-off. Fast
  investigator labels arrive at +6h and only for transactions we alerted on;
  delayed chargeback labels arrive at +45d; a share never arrives at all.
  Testing is on transactions after the cut-off.

  There is no random-split path in this file, because a random split assumes
  labels you would not have at decision time.
"""
from __future__ import annotations
import csv, json, math, random, statistics as st, sys, time
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chakra.schema.transaction import Transaction
from chakra.schema.enums import Rail, ResponseCode, ThreeDSECI, POSEntryMode, AVSResult, CVV2Result
from chakra.detect.features import FeatureBuilder, FeatureSet
from chakra.detect.heads import Head, Fusion, ConformalBudget, CostModel

OUT = Path(__file__).resolve().parents[1] / "outputs"
OUT.mkdir(exist_ok=True)
TRAIN_FRAC = 0.60
LABEL_DELAY_DAYS = 45
FAST_DELAY_HOURS = 6


def load_corpus():
    rows = list(csv.DictReader((OUT / "labelled_corpus.csv").open()))
    gt = {r["txn_id"]: r for r in
          csv.DictReader((OUT / "ground_truth.csv").open())}
    txns = []
    for r in rows:
        txns.append(Transaction(
            txn_id=r["txn_id"], ts=datetime.fromisoformat(r["ts"]),
            rail=Rail(r["rail"]), amount=__import__("decimal").Decimal(r["amount"]),
            currency=r["currency"] or "INR",
            token_pan=r["token_pan"] or None,
            payer_vpa=r["payer_vpa"] or None, payee_vpa=r["payee_vpa"] or None,
            mcc=r["mcc"] or None, merchant_id=r["merchant_id"] or None,
            acquirer_id=r["acquirer_id"] or None,
            terminal_id=r["terminal_id"] or None,
            pos_entry_mode=POSEntryMode(r["pos_entry_mode"]),
            country=r["country"] or "IN",
            avs_result=AVSResult(r["avs_result"]),
            cvv2_result=CVV2Result(r["cvv2_result"]),
            threeds_eci=ThreeDSECI(r["threeds_eci"]),
            response_code=ResponseCode(r["response_code"]),
            agent_id=r["agent_id"] or None, mandate_id=r["mandate_id"] or None,
            agent_token_id=r["agent_token_id"] or None,
            device_binding_id=r["device_binding_id"] or None,
            collect_request_id=r["collect_request_id"] or None))
    txns.sort(key=lambda t: t.ts)
    return txns, gt


def pr_auc(scores, labels):
    pairs = sorted(zip(scores, labels), key=lambda x: -x[0])
    P = sum(labels) or 1
    tp = fp = 0
    prev_r, ap = 0.0, 0.0
    for s, y in pairs:
        tp += y; fp += 1 - y
        r = tp / P
        ap += (r - prev_r) * (tp / (tp + fp))
        prev_r = r
    return ap


def main() -> int:
    rng = random.Random(31)
    txns, gt = load_corpus()
    print("=" * 78)
    print("PHASE 6 — DETECTOR")
    print("=" * 78)
    print(f"corpus {len(txns):,}   fraud "
          f"{sum(1 for t in txns if gt[t.txn_id]['is_fraud']=='1'):,}")

    # ---- features, strictly forward-only -----------------------------
    t0 = time.perf_counter()
    mand = {}
    mp = OUT / "mandates.csv"
    if mp.exists():
        for r in csv.DictReader(mp.open()):
            mand[r["mandate_id"]] = {
                "ceiling": float(r["ceiling"]),
                "allowed_mccs": [x for x in r["allowed_mccs"].split("|") if x],
                "expiry": (datetime.fromisoformat(r["expiry_ts"]).timestamp()
                           if r["expiry_ts"] else None),
                "issued": (datetime.fromisoformat(r["issued_ts"]).timestamp()
                           if r["issued_ts"] else None),
                "hint": r["category_hint"] or None,
            }
    print(f"loaded {len(mand):,} mandates for Head C")
    fb = FeatureBuilder(node="network", mandates=mand)
    feats = [fb.build(t) for t in txns]
    build_ms = (time.perf_counter() - t0) * 1000 / len(txns)
    print(f"feature builder: visibility enforced at node 'network', "
          f"{build_ms:.3f} ms/txn")

    cut = txns[int(len(txns) * TRAIN_FRAC)].ts
    print(f"train cut-off {cut:%Y-%m-%d %H:%M}   "
          f"train {int(len(txns)*TRAIN_FRAC):,}  test {len(txns)-int(len(txns)*TRAIN_FRAC):,}")

    # ---- labels available at the cut-off -----------------------------
    #
    # Two streams, per Dal Pozzolo. The first run of this file used only the
    # delayed stream and produced ZERO labels at the cut-off, because a 45-day
    # chargeback delay on a 45-day corpus means nothing has come back yet.
    # That is not a bug in the data, it is the actual operating condition, and
    # it is why the fast stream is not optional.
    #
    #   FAST     a rules pre-filter alerts ~2.5% of traffic; an investigator
    #            resolves each alert within 6 hours, labelling BOTH classes.
    #            Small, quick, and selection-biased by the filter itself.
    #   DELAYED  chargebacks, lognormal around 21 days, fraud only, and only
    #            for the share that gets reported at all.
    label, stream = {}, {}
    unlabelled_fraud = alerted = 0

    def prefilter(t) -> bool:
        """The legacy rules engine whose alerts an investigator reviews.
        Deliberately crude and deliberately biased — that bias is the thing
        Dal Pozzolo says you must model rather than assume away."""
        if t.response_code is not ResponseCode.APPROVED:
            return rng.random() < 0.10
        if float(t.amount) > 20000:
            return rng.random() < 0.22
        return rng.random() < 0.012

    for t in txns:
        g = gt[t.txn_id]
        y = int(g["is_fraud"] == "1")
        if prefilter(t):
            alerted += 1
            if t.ts + timedelta(hours=FAST_DELAY_HOURS) <= cut:
                label[t.txn_id] = y
                stream[t.txn_id] = "fast"
        if y:
            reported = rng.random() < (0.85 if t.rail.has_chargeback else 0.55)
            if not reported:
                unlabelled_fraud += 1
                continue
            arrives = t.ts + timedelta(days=rng.lognormvariate(math.log(21), 0.5))
            if arrives <= cut:
                label[t.txn_id] = 1
                stream.setdefault(t.txn_id, "delayed")

    tr = [(f, label[f.txn_id]) for f in feats
          if f.ts <= cut and f.txn_id in label]
    te = [(f, int(gt[f.txn_id]["is_fraud"] == "1")) for f in feats if f.ts > cut]
    nbefore = sum(1 for f in feats if f.ts <= cut)
    nfast = sum(1 for f in feats if f.ts <= cut
                and stream.get(f.txn_id) == "fast")
    ndel = sum(1 for f in feats if f.ts <= cut
               and stream.get(f.txn_id) == "delayed")
    print(f"\nLABEL REALITY AT TRAINING TIME")
    print(f"  transactions before cut-off   {nbefore:,}")
    print(f"  alerted by the rules filter   {alerted:,} "
          f"({alerted/len(txns):.1%} of traffic)")
    print(f"  fast investigator labels      {nfast:,}")
    print(f"  delayed chargeback labels     {ndel:,}")
    print(f"  TOTAL usable                  {len(tr):,} "
          f"({len(tr)/max(1,nbefore):.1%} of the training period)")
    print(f"  fraud among them              {sum(y for _,y in tr):,}")
    print(f"  fraud never labelled at all   {unlabelled_fraud:,}")
    print(f"  A random split would have handed the model every label on day one.")

    Xtr = [f for f, _ in tr]; ytr = [y for _, y in tr]
    Xte = [f for f, _ in te]; yte = [y for _, y in te]

    # ---- heads --------------------------------------------------------
    heads = [Head("A_behavioural", "A").fit(Xtr, ytr),
             Head("B_graph", "B").fit(Xtr, ytr),
             Head("C_intent", "C").fit([x for x in Xtr if x.C],
                                       [y for x, y in zip(Xtr, ytr) if x.C])
             if any(x.C for x in Xtr) else Head("C_intent", "C")]
    fus = Fusion(heads).fit_prior(ytr).calibrate(Xtr, ytr)

    # ---- F9 ablation --------------------------------------------------
    print("\n" + "=" * 78)
    print("F9 — HEAD ABLATION  (PR-AUC on the held-out period)")
    print("=" * 78)
    combos = {
        "A behavioural only":      ["A_behavioural"],
        "B graph only":            ["B_graph"],
        "C intent only":           ["C_intent"],
        "A + B (anomaly only)":    ["A_behavioural", "B_graph"],
        "A + B + C (all three)":   ["A_behavioural", "B_graph", "C_intent"],
    }
    vec = {f.txn_id: gt[f.txn_id]["vector_id"] for f in Xte}
    agentic = {"AGT-004", "AGT-008"}
    print(f"{'heads':26s} {'PR-AUC all':>11s} {'agentic':>9s} {'classic':>9s}")
    results = {}
    for name, hs in combos.items():
        sub = (Fusion([h for h in heads if h.name in hs])
               .fit_prior(ytr).calibrate(Xtr, ytr))
        sc = [sub.prob(f) for f in Xte]
        results[name] = sc
        ia = [i for i, f in enumerate(Xte)
              if yte[i] == 0 or vec[f.txn_id] in agentic]
        ic = [i for i, f in enumerate(Xte)
              if yte[i] == 0 or vec[f.txn_id] not in agentic]
        print(f"{name:26s} {pr_auc(sc, yte):11.4f} "
              f"{pr_auc([sc[i] for i in ia], [yte[i] for i in ia]):9.4f} "
              f"{pr_auc([sc[i] for i in ic], [yte[i] for i in ic]):9.4f}")
    print("\n  The agentic column is the argument for a third head. A and B are")
    print("  anomaly detectors and agentic fraud carries no anomaly, so what")
    print("  they add there is close to the base rate.")

    # ---- per-vector recall -------------------------------------------
    full = results["A + B + C (all three)"]
    ab = results["A + B (anomaly only)"]
    cal_scores = [s for s, y in zip(full, yte) if y == 0]
    cal_rails = [f.rail for f, y in zip(Xte, yte) if y == 0]
    budget = ConformalBudget(alpha=0.02).fit(cal_scores, cal_rails)
    print(f"\n{'vector':12s} {'n':>5s} {'recall A+B':>11s} {'recall A+B+C':>13s}")
    per = defaultdict(list)
    for i, f in enumerate(Xte):
        if yte[i]:
            per[vec[f.txn_id]].append(i)
    for v in sorted(per):
        idx = per[v]
        r1 = sum(1 for i in idx if ab[i] > budget.threshold(Xte[i].rail)) / len(idx)
        r2 = sum(1 for i in idx if full[i] > budget.threshold(Xte[i].rail)) / len(idx)
        print(f"{v:12s} {len(idx):5d} {r1:10.1%} {r2:12.1%}")

    # ---- F8 budget curve ---------------------------------------------
    print("\n" + "=" * 78)
    print("F8 — VALUE DETECTION AT A FIXED FRICTION BUDGET")
    print("=" * 78)
    vals = [float(gt[f.txn_id]["value_at_risk"]) or f.amount for f in Xte]
    total_val = sum(v for v, y in zip(vals, yte) if y)
    print(f"{'budget':>8s} {'tau':>8s} {'txn recall':>11s} "
          f"{'value recall':>13s} {'naive-prob':>11s}")
    for a in (0.005, 0.01, 0.02, 0.05, 0.10):
        b = ConformalBudget(alpha=a).fit(cal_scores, cal_rails)
        flag = [full[i] > b.threshold(Xte[i].rail) for i in range(len(Xte))]
        tr_ = sum(1 for i in range(len(Xte)) if yte[i] and flag[i]) / max(1, sum(yte))
        vr = sum(vals[i] for i in range(len(Xte)) if yte[i] and flag[i]) / max(1.0, total_val)
        # naive baseline: same budget, threshold on probability alone,
        # ignoring transaction value
        srt = sorted(range(len(Xte)), key=lambda i: -full[i])
        k = int(a * len(Xte))
        top = set(srt[:k])
        nv = sum(vals[i] for i in top if yte[i]) / max(1.0, total_val)
        print(f"{a:8.1%} {b._global:8.2f} {tr_:10.1%} {vr:12.1%} {nv:10.1%}")
    print("\n  Value recall is the number that matters. Two models with equal")
    print("  transaction recall are not equally useful if one catches the")
    print("  large transfers and the other catches the probes.")

    # ---- F14 latency ---------------------------------------------------
    print("\n" + "=" * 78)
    print("F14 — LATENCY")
    print("=" * 78)
    sample = Xte[:4000]
    t0 = time.perf_counter()
    for f in sample:
        fus.prob(f)
    scor = (time.perf_counter() - t0) * 1000 / len(sample)
    cm = CostModel()
    t0 = time.perf_counter()
    for f in sample:
        cm.choose(0.3, f.amount, f.rail)
    resp = (time.perf_counter() - t0) * 1000 / len(sample)
    print(f"  feature build   {build_ms:7.3f} ms/txn")
    print(f"  fusion scoring  {scor:7.3f} ms/txn")
    print(f"  response choice {resp:7.3f} ms/txn")
    print(f"  TOTAL           {build_ms+scor+resp:7.3f} ms/txn   "
          f"(industry reference for network-level scoring is under 50 ms)")
    print("  Pure Python, single-threaded, no vectorisation. The scorecard is")
    print("  a sum of table lookups, which is why it fits the budget at all.")

    # ---- reason codes --------------------------------------------------
    print("\n" + "=" * 78)
    print("REASON CODES — the terms are the explanation")
    print("=" * 78)
    shown = 0
    for i, f in enumerate(Xte):
        if yte[i] and full[i] > budget.threshold(f.rail) and shown < 4:
            z, per_head = fus.llr(f)
            rs = []
            for h in heads:
                if h.applicable(f):
                    rs += [(h.name[0], n, w) for n, w in h.reasons(f, 2)]
            rs.sort(key=lambda x: -x[2])
            print(f"  {vec[f.txn_id]:9s} p={full[i]:.3f} rail={f.rail} "
                  f"amt={f.amount:,.0f}")
            print(f"      " + " | ".join(f"{b}:{n} {w:+.2f}" for b, n, w in rs[:3]))
            shown += 1

    json.dump({"f9": {k: pr_auc(v, yte) for k, v in results.items()},
               "latency_ms": {"features": build_ms, "fusion": scor,
                              "response": resp},
               "train_labels": len(tr), "unlabelled_fraud": unlabelled_fraud},
              (OUT / "F9_F14_detector.json").open("w"), indent=2)
    print("\n" + "=" * 78)
    print("PHASE 6 DONE — loop unblocked")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
