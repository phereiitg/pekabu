#!/usr/bin/env python3
"""Phase 7 — the loop. Produces F1 and F12.

Design choice worth stating: the benign world is generated ONCE and held
fixed. Only the attacker population evolves and only the defender retrains.
That isolates the loop dynamics from simulator variance — if the benign world
were regenerated each round, an escape-rate change could be the attacker
adapting or just a different sample, and the two would be inseparable.

Each iteration:
  1. the current attack population runs against the fixed world
  2. the defender trains on every label available so far, across all rounds
  3. attacks that get through are logged, with the parameters that did it
  4. fitness = escape rate x value / attacker cost
  5. the elite breed; mutants form the next population
"""
from __future__ import annotations
import csv, json, math, random, statistics as st, sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chakra.schema.enums import ResponseCode
from chakra.schema.labels import LabelHarness
from chakra.world.engine import EngineConfig, build, run, MANDATE_LOG
from chakra.attacks.base import AttackContext
from chakra.attacks.plugins import (MuleFarm, CardTesting, CollectRequestScam,
                             AgentCompromise, AuthorisationDrift,
                             MicroStructuring)
from chakra.detect.features import FeatureBuilder
from chakra.detect.heads import Head, Fusion
from chakra.detect.portfolio import Portfolio, route_of, ROUTE_ALPHA, ROUTE_HEADS
from chakra.detect.peer import build_index
from chakra.detect.semantic import SemanticMatcher
from chakra.detect.reservoir import TrainingReservoir
from chakra.redsearch.loop import RedSearch, Escape, IterationResult, coverage_error_by_route
from scripts.run_detect import pr_auc as pr_auc_local

OUT = Path(__file__).resolve().parents[1] / "outputs"
OUT.mkdir(exist_ok=True)
ITERATIONS = 8
TRAIN_FRAC = 0.55


def build_labels(txns, truth, cut, rng):
    """Same two-stream regime as Phase 6: a biased rules pre-filter feeding an
    investigator, plus delayed chargebacks. No random split anywhere."""
    label = {}
    for t in txns:
        g = truth.get(t.txn_id)
        y = int(bool(g and g.is_fraud))
        alert = (rng.random() < 0.10
                 if t.response_code is not ResponseCode.APPROVED
                 else (rng.random() < 0.22 if float(t.amount) > 20000
                       else rng.random() < 0.012))
        if alert and t.ts + timedelta(hours=6) <= cut:
            label[t.txn_id] = y
        if y and rng.random() < (0.85 if t.rail.has_chargeback else 0.55):
            if t.ts + timedelta(days=rng.lognormvariate(math.log(21), 0.5)) <= cut:
                label[t.txn_id] = 1
    return label


def main() -> int:
    rng = random.Random(41)
    cfg = EngineConfig()

    print("=" * 80)
    print("PHASE 7 — THE LOOP")
    print("=" * 80)
    w = build(cfg)
    harness = LabelHarness()
    benign, _ = run(w, cfg, harness)
    print(f"benign world fixed: {len(benign):,} transactions, "
          f"{len(w.payers):,} payers, {len(w.agents):,} agents")
    print(f"{ITERATIONS} iterations, elite=3 offspring=3\n")

    population = [MuleFarm(), CardTesting(), CollectRequestScam(),
                  AgentCompromise(), AuthorisationDrift(), MicroStructuring()]
    # A FROZEN benchmark: the six default configurations, never mutated, run
    # every iteration. Without it the escape rate confounds two things — the
    # defender getting better and the attacker population changing size and
    # shape. Measured on the first run, attack volume swung from 210 to 3,161
    # between iterations, which makes a raw rate unreadable.
    #
    #   BENCHMARK escape rate  = defender progress, attacker held constant
    #   ADAPTIVE  escape rate  = attacker progress against the current defender
    #
    # The pair is the actual story: the defence closes on known attacks while
    # the red team opens new ground.
    benchmark = [MuleFarm(), CardTesting(), CollectRequestScam(),
                 AgentCompromise(), AuthorisationDrift(), MicroStructuring()]
    search = RedSearch(population, rng)
    bench_hist = []
    diag = []

    # D-27 fix: bounded, class-balanced memory with prior correction.
    # The unbounded list this replaces let the training base rate climb
    # 15.5% -> 40.4% across six rounds and collapsed PR-AUC 0.256 -> 0.026.
    # D-29: 6% starved learning (only ~30 fraud labels admitted per
    # round). 15% keeps both classes well represented in the WOE bins
    # while admitting enough new attack evidence to matter.
    reservoir = TrainingReservoir(target_base_rate=0.15,
                                  rng=random.Random(97))
    all_escapes: List[Escape] = []
    rows_out = []

    for it in range(1, ITERATIONS + 1):
        ctx = AttackContext(world=w, origin=cfg.origin, days=cfg.days,
                            rng=rng, harness=harness)
        ctx.counter[0] = 900_000_000 + it * 2_000_000

        per_attack = {}
        fraud = []
        for a in search.population:
            rowsA = a.run(ctx)
            per_attack[id(a)] = (a, rowsA)
            fraud += rowsA
        bench_rows = {}
        for a in benchmark:
            rowsB = a.run(ctx)
            bench_rows[a.vector_id] = rowsB
            fraud += rowsB

        allt = sorted(benign + fraud, key=lambda t: t.ts)
        cut = allt[int(len(allt) * TRAIN_FRAC)].ts

        mand = {m.mandate_id: {
            "ceiling": float(m.ceiling),
            "allowed_mccs": list(m.allowed_mccs),
            "expiry": m.expiry.timestamp() if m.expiry else None,
            "issued": (m.capsule.issued_at.timestamp()
                       if m.capsule.issued_at else None),
            "hint": m.capsule.category_hint}
            for m, _b, _a2, _t, _it in MANDATE_LOG}

        # Same peer index and semantic matcher the single-shot run uses, fitted
        # per round on what was known before this round's attacks happened.
        mrows = [{"mandate_id": m.mandate_id,
                  "stated_intent": m.capsule.stated_intent,
                  "category_hint": m.capsule.category_hint or "",
                  "ceiling": str(m.ceiling),
                  "allowed_mccs": "|".join(m.allowed_mccs),
                  "issued_ts": (m.capsule.issued_at.timestamp()
                                if m.capsule.issued_at else 0.0),
                  "exec_beneficiary": _b, "exec_amount": str(_a),
                  "exec_ts": _t.timestamp(), "exec_item": _i}
                 for m, _b, _a, _t, _i in MANDATE_LOG]
        peers = build_index(mrows, cutoff_ts=cut.timestamp(), min_cluster=25)
        sem = SemanticMatcher().fit(sorted(
            {r["stated_intent"] for r in mrows} | {r["exec_item"] for r in mrows}))
        for k, v in mand.items():
            src = next((r for r in mrows if r["mandate_id"] == k), None)
            if src:
                v["intent"] = src["stated_intent"]
                v["item"] = src["exec_item"]

        fb = FeatureBuilder(node="network", mandates=mand, peers=peers, semantic=sem)
        feats = [fb.build(t) for t in allt]
        agent_flag = {t.txn_id: bool(t.agent_id) for t in allt}
        mand_flag = {t.txn_id: bool(t.mandate_id) for t in allt}

        def rfn(fs):
            return route_of(fs, agent_flag.get(fs.txn_id, False),
                            mand_flag.get(fs.txn_id, False))

        label = build_labels(allt, harness.truth, cut, rng)

        # the defender remembers every round, which is what makes it a loop
        # D-28: the defender trains on what it knew BEFORE this round's
        # attacks happened. You cannot hold labels for an attack that is
        # occurring now — the whole point of verification latency is that you
        # find out afterwards.
        #
        # Round 1 therefore starts with an empty reservoir and no attack
        # knowledge at all, which is both realistic and the only way the
        # escape-rate curve can show learning. The previous version admitted
        # this round's labels before training, so the defender saturated in
        # round 1 and the curve was flat at 69-77% by construction.
        Xtr, ytr = reservoir.dataset()
        # A held-out calibration slice, immediately before the cut and never
        # trained on, so the conformal threshold is set on data exchangeable
        # with what it will face.
        cal_start = allt[int(len(allt) * (TRAIN_FRAC - 0.14))].ts
        Xcal = [f for f in feats if cal_start < f.ts <= cut]
        _tr = harness.truth
        ycal = [1 if (_tr.get(f.txn_id) and _tr[f.txn_id].is_fraud) else 0
                for f in Xcal]
        new_rows = [f for f in feats if f.ts <= cut and f.txn_id in label]
        new_y = [label[f.txn_id] for f in new_rows]

        if len(set(ytr)) < 2 or len(ytr) < 40:
            # cold start: no usable labels yet. Report it rather than fitting
            # noise, and let the escape rate say 100% honestly.
            print(f"iter {it}  COLD START — no attack labels yet, "
                  f"defender is untrained")
            reservoir.add([f for f in feats if f.ts <= cut and f.txn_id in label],
                          [label[f.txn_id] for f in feats
                           if f.ts <= cut and f.txn_id in label])
            bench_hist.append({"i": it, "att": 1, "esc": 1, "rate": 1.0,
                               "by_vector": {}})
            diag.append({"i": it, "train_base_rate": 0.0, "train_n": 0,
                         "pr_auc_benchmark": float("nan"),
                         "genuine_mean": 0.0, "fraud_mean": 0.0, "tau": {}})
            search.history.append(IterationResult(
                index=it, n_attacks=1, n_escaped=1, value_total=1.0,
                value_escaped=1.0, escape_by_vector={}, escape_by_route={},
                coverage_error={}, mean_fitness=0.0))
            search.population = search.evolve(
                [(a, 1.0) for a, _ in per_attack.values()])
            continue

        heads = {
            "A_behavioural": Head("A_behavioural", "A").fit(Xtr, ytr),
            "B_graph": Head("B_graph", "B").fit(Xtr, ytr),
            "P_peer": (Head("P_peer", "P").fit(
                [x for x in Xtr if x.P], [y for x, y in zip(Xtr, ytr) if x.P])
                if sum(1 for x in Xtr if x.P) > 40 else Head("P_peer", "P")),
            "C_intent": (Head("C_intent", "C").fit(
                [x for x in Xtr if x.C], [y for x, y in zip(Xtr, ytr) if x.C])
                if sum(1 for x in Xtr if x.C) > 60 else Head("C_intent", "C")),
        }
        pf = Portfolio().fit(Xtr, ytr, heads, rfn, cal_rows=Xcal, cal_y=ycal)
        # NOTE on prior correction: it does NOT belong here.
        #
        # Overriding the intercept with the deployment base rate
        # (logit 0.005 = -5.29) crushed every probability toward zero and the
        # conformal threshold landed on a mass of underflowed genuine scores,
        # so nothing flagged and escape went to 100%. Measured, not guessed.
        #
        # The reason is structural: conformal thresholding is RANK-based, and
        # a prior shift is monotone, so it cannot change what gets flagged. It
        # only changes the number. Prior correction therefore belongs in the
        # COST path, where a probability is multiplied by a rupee amount and
        # has to mean what it says — not in the ranking path, where it is at
        # best a no-op and at worst numerically destructive.

        # --- evaluate on the held-out period -------------------------
        fs_by_id = {f.txn_id: f for f in feats}
        truth = harness.truth
        n_att = n_esc = 0
        v_tot = v_esc = 0.0
        esc_by_vec = defaultdict(lambda: [0, 0])
        esc_by_route = defaultdict(lambda: [0, 0])
        scored_attacks = []

        for a, rowsA in per_attack.values():
            att = esc = 0
            vesc = 0.0
            for t in rowsA:
                f = fs_by_id.get(t.txn_id)
                if f is None or f.ts <= cut:
                    continue
                r = rfn(f)
                m = pf.routes.get(r)
                flagged = bool(m and m.trained and m.flags(f))
                att += 1
                v = float(t.amount)
                v_tot += v
                esc_by_vec[a.vector_id][1] += 1
                esc_by_route[r][1] += 1
                if not flagged:
                    esc += 1
                    vesc += v
                    v_esc += v
                    esc_by_vec[a.vector_id][0] += 1
                    esc_by_route[r][0] += 1
                    tau = m.budget.threshold(f.rail) if (m and m.budget) else 1.0
                    all_escapes.append(Escape(
                        txn_id=t.txn_id, vector_id=a.vector_id, route=r,
                        signature=a.signature(), params=dict(a.params),
                        value=v, score=(m.score(f) if m and m.trained else 0.0),
                        threshold=tau))
            n_att += att
            n_esc += esc
            fit = RedSearch.fitness(esc, att, vesc, a.attacker_cost())
            scored_attacks.append((a, fit))

        # --- frozen benchmark: defender progress ---------------------
        b_att = b_esc = 0
        b_by_vec = {}
        for vid, rowsB in bench_rows.items():
            att = esc = 0
            for t in rowsB:
                f = fs_by_id.get(t.txn_id)
                if f is None or f.ts <= cut:
                    continue
                r = rfn(f)
                m = pf.routes.get(r)
                att += 1
                if not (m and m.trained and m.flags(f)):
                    esc += 1
            b_att += att; b_esc += esc
            if att:
                b_by_vec[vid] = esc / att
        bench_hist.append({"i": it, "att": b_att, "esc": b_esc,
                           "rate": b_esc / max(1, b_att),
                           "by_vector": b_by_vec})

        # --- DIAGNOSTIC: is the model degrading, or is the threshold moving?
        # Decisive test. If ranking quality (AUC) holds while recall falls,
        # the problem is the threshold. If AUC falls, the model itself is
        # degrading and the threshold is innocent.
        bench_ids = {t.txn_id for rows in bench_rows.values() for t in rows}
        bs, by = [], []
        for f in feats:
            if f.ts <= cut:
                continue
            m = pf.routes.get(rfn(f))
            if not (m and m.trained):
                continue
            g = truth.get(f.txn_id)
            isb = f.txn_id in bench_ids
            if isb or not (g and g.is_fraud):
                bs.append(m.score(f)); by.append(1 if isb else 0)
        auc = pr_auc_local(bs, by) if len(set(by)) > 1 else float("nan")
        gsc = [s2 for s2, y2 in zip(bs, by) if not y2]
        fsc = [s2 for s2, y2 in zip(bs, by) if y2]
        taus = {r: m.budget.threshold("R2")
                for r, m in pf.routes.items() if m.trained and m.budget}
        diag.append({"i": it,
                     "train_base_rate": sum(ytr) / max(1, len(ytr)),
                     "train_n": len(ytr),
                     "pr_auc_benchmark": auc,
                     "genuine_mean": st.fmean(gsc) if gsc else 0.0,
                     "fraud_mean": st.fmean(fsc) if fsc else 0.0,
                     "tau": taus})

        # --- F12: coverage error on genuine traffic ------------------
        gen_by_route = defaultdict(list)
        for f in feats:
            if f.ts <= cut:
                continue
            g = truth.get(f.txn_id)
            if g and g.is_fraud:
                continue
            r = rfn(f)
            m = pf.routes.get(r)
            if m and m.trained:
                gen_by_route[r].append(m.score(f))
        thr = {r: m.budget.threshold("R2")
               for r, m in pf.routes.items() if m.trained and m.budget}
        cov = coverage_error_by_route(gen_by_route, thr, ROUTE_ALPHA)

        res = IterationResult(
            index=it, n_attacks=n_att, n_escaped=n_esc,
            value_total=v_tot, value_escaped=v_esc,
            escape_by_vector={k: v[0] / max(1, v[1])
                              for k, v in esc_by_vec.items()},
            escape_by_route={k: v[0] / max(1, v[1])
                             for k, v in esc_by_route.items()},
            coverage_error=cov,
            mean_fitness=st.fmean([f for _, f in scored_attacks])
            if scored_attacks else 0.0)
        search.history.append(res)

        print(f"iter {it}  benchmark {b_esc:4,}/{b_att:<5,} = "
              f"{b_esc/max(1,b_att):6.1%}   adaptive {n_esc:5,}/{n_att:<6,} = "
              f"{res.escape_rate:6.1%}   fitness {res.mean_fitness:.4f}")
        if it == 1 or it == ITERATIONS:
            print(f"         {reservoir.summary()}")

        # only now does the defender learn from this round
        reservoir.add(new_rows, new_y)
        search.population = search.evolve(scored_attacks)


    # ---- F1 -------------------------------------------------------
    print("\n" + "=" * 80)
    print("F1 — ESCAPE RATE BY LOOP ITERATION")
    print("=" * 80)
    h = search.history
    print("Two curves, because they answer different questions.\n")
    print(f"{'iter':>5s} {'BENCHMARK':>10s}  {'defender progress':38s}")
    mb = max(b['rate'] for b in bench_hist) or 1.0
    for b in bench_hist:
        print(f"{b['i']:5d} {b['rate']:9.1%}  " + "#" * int(36 * b['rate'] / mb))
    print(f"\n  frozen attacks, first -> last: {bench_hist[0]['rate']:.1%} -> "
          f"{bench_hist[-1]['rate']:.1%}  "
          f"({(bench_hist[-1]['rate']-bench_hist[0]['rate'])*100:+.1f} pts)")
    print("  The six default configurations never change. Every point of")
    print("  improvement here is the defender learning.\n")
    print(f"{'iter':>5s} {'ADAPTIVE':>10s} {'value-esc':>10s} {'fitness':>9s}  attacker progress")
    mx = max(x.escape_rate for x in h) or 1.0
    for x in h:
        print(f"{x.index:5d} {x.escape_rate:9.1%} {x.value_escape_rate:9.1%} "
              f"{x.mean_fitness:9.4f}  " + "#" * int(28 * x.escape_rate / mx))
    print(f"\n  mutated population, first -> last: {h[0].escape_rate:.1%} -> "
          f"{h[-1].escape_rate:.1%}   fitness {h[0].mean_fitness:.3f} -> "
          f"{h[-1].mean_fitness:.3f}")
    print("  Rising adaptive escape against falling benchmark escape is the")
    print("  loop working: the defence closes on what it has seen while the")
    print("  red team opens ground it has not.")
    print(f"  stopping signal: {search.stopping_signal()}")

    print("\n--- escape rate by route ---")
    routes = sorted({r for x in h for r in x.escape_by_route})
    print(f"{'iter':>5s} " + "".join(f"{r:>12s}" for r in routes))
    for x in h:
        print(f"{x.index:5d} " + "".join(
            f"{x.escape_by_route.get(r, float('nan')):11.1%} " for r in routes))
    print("\n  Watch where the pressure moves. A red team that keeps attacking")
    print("  the route the defender just hardened is not adapting; one that")
    print("  shifts to the weakest remaining route is.")

    print("\n--- escape rate by vector ---")
    vecs = sorted({v for x in h for v in x.escape_by_vector})
    print(f"{'iter':>5s} " + "".join(f"{v:>10s}" for v in vecs))
    for x in h:
        print(f"{x.index:5d} " + "".join(
            f"{x.escape_by_vector.get(v, float('nan')):9.0%} " for v in vecs))

    # ---- F12 ------------------------------------------------------
    print("\n" + "=" * 80)
    print("F12 — CONFORMAL COVERAGE ERROR ACROSS ITERATIONS")
    print("=" * 80)
    print("Observed step-up rate on GENUINE traffic minus the promised budget.")
    print("No labels are used to compute this. Positive means the guarantee is")
    print("breaking, and it breaks before any chargeback lands.\n")
    croutes = sorted({r for x in h for r in x.coverage_error})
    print(f"{'iter':>5s} " + "".join(f"{r:>12s}" for r in croutes))
    for x in h:
        print(f"{x.index:5d} " + "".join(
            f"{x.coverage_error.get(r, float('nan')):+11.2%} " for r in croutes))

    # ---- escape log ------------------------------------------------
    print("\n" + "=" * 80)
    print("ESCAPE LOG — what the mutator learned from")
    print("=" * 80)
    by_sig = Counter(e.signature.split("(")[0] for e in all_escapes)
    print(f"  {len(all_escapes):,} escaped transactions logged")
    for v, c in by_sig.most_common():
        print(f"    {v:10s} {c:5,}")
    near = sorted(all_escapes, key=lambda e: e.margin)[:3]
    print("\n  closest near-misses (smallest margin under threshold):")
    for e in near:
        print(f"    {e.vector_id} route={e.route} margin={e.margin:.4f} "
              f"value={e.value:,.0f}")

    json.dump({
        "iterations": [{
            "i": x.index, "escape_rate": x.escape_rate,
            "value_escape_rate": x.value_escape_rate,
            "fitness": x.mean_fitness,
            "by_route": x.escape_by_route,
            "by_vector": x.escape_by_vector,
            "coverage_error": x.coverage_error} for x in h],
        "benchmark": bench_hist,
        "stopping_signal": search.stopping_signal(),
        "n_escapes_logged": len(all_escapes)},
        (OUT / "F1_F12_loop.json").open("w"), indent=2)
    print("\n" + "=" * 80)
    print("DIAGNOSTIC — model quality vs threshold placement")
    print("=" * 80)
    print(f"{'it':>3s} {'train n':>8s} {'base rate':>10s} {'PR-AUC':>8s} "
          f"{'genuine mu':>11s} {'fraud mu':>9s} {'sep':>7s}  tau(card/push/agentic)")
    for d in diag:
        t = d["tau"]
        print(f"{d['i']:3d} {d['train_n']:8,} {d['train_base_rate']:9.1%} "
              f"{d['pr_auc_benchmark']:8.3f} {d['genuine_mean']:11.4f} "
              f"{d['fraud_mean']:9.4f} {d['fraud_mean']-d['genuine_mean']:7.4f}  "
              f"{t.get('card',0):.3f}/{t.get('push',0):.3f}/{t.get('agentic',0):.3f}")
    print("\n  If PR-AUC holds while escape rate rises -> threshold problem.")
    print("  If PR-AUC falls -> the model itself is degrading.")

    print("\nwrote F1_F12_loop.json")
    print("=" * 80)
    return 0


if __name__ == "__main__":

    raise SystemExit(main())
