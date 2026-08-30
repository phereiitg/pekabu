# Defect register

**This is F16.** Logging problems is not overhead here — the limitations section
is a Tier-1 artifact, and it changes how every other number in the document is
read. A team that names its own limits precisely reads as one that understands
the problem.

Severity: **P0** blocks submission · **P1** materially weakens a scored
criterion · **P2** worth fixing · **P3** note in the document, do not fix.

Status: `open` · `accepted` (won't fix, stated in doc) · `closed`

---

## P0 — blocks submission

| ID | Defect | Notes |
|---|---|---|
| D-01 | **No web prototype exists.** Explicit deliverable in the brief. | Five screens over artifacts that already exist. Nothing new is computed. |
| D-02 | **No .docx walkthrough exists.** Explicit deliverable. | Skeleton was specified in Phase 0; figures now exist to drop in. |
| D-03 | **Repo is not on GitHub.** Explicit deliverable. | Needs README, requirements, one-command reproduction. |
| D-30 | **F1 has no room to fall.** After fixing D-27 and D-28, benchmark escape still sits at 72–97%. Round 2 has seen round-1 attacks and still lets 72.6% through. | Not a loop defect. The loop is faithfully reporting the detector's ceiling: PR-AUC 0.14–0.28 and ~20% recall predict exactly this escape rate. **F1 cannot descend until D-05 is fixed.** The loop machinery is correct and will produce the figure the moment detection improves. |
| ~~D-28~~ | ~~**Loop shows no defender improvement.**~~ Benchmark escape is now FLAT at 69–77% across six iterations instead of falling. | Not the same bug as D-27, and arguably correct behaviour: the frozen benchmark is the same six configurations every round, all of them already in memory after round 1, so there is nothing new to learn about them. The defender saturates immediately. To show convergence, round 1 must start with no attack knowledge — the detector should train on benign labels only, then acquire attack knowledge as labels arrive. That is also more realistic, since a deployed model does not begin knowing the attacks. |
| D-29 | Reservoir admits only ~30 new fraud labels per round; after six rounds memory holds 216 fraud against 3,393 genuine. | Follows from the 6% target base rate against a genuine pool the alert filter fills slowly. Probably too conservative — the balance fixed the collapse but may now starve learning. Worth sweeping the target rate. |
| ~~D-27~~ | ~~**Loop convergence is INVERTED.**~~ Escape rate on frozen benchmark attacks rises 67.9% -> 97.1% over six iterations. The defender gets worse, not better. | Diagnosed, not yet fixed. The conformal budget is refit each iteration on that round's genuine score distribution. Accumulated fraud in the training memory raises the prior, every score rises, the genuine quantile rises with it, and the threshold chases the scores upward. Coverage error stays comfortably negative (-0.3% to -3.2%) the whole time — **the budget is held perfectly while catching less each round.** The guarantee is being satisfied against a moving target. Fix: freeze the calibration slice, or recalibrate probabilities to a fixed reference base rate before setting the threshold. Shares a root cause with D-17 and D-24. |
| D-04 | ~~The loop has not run.~~ Mechanically complete: escape log, mutator, fitness, per-route tracking, both curves and F12 all produced. Convergence is wrong — see D-27. | Phase 7 built. The figure is not yet usable. |

---

## P1 — materially weakens a scored criterion

| ID | Defect | Detail | Fix |
|---|---|---|---|
| D-05 | **Absolute detection numbers look weak.** PR-AUC 0.308 fused; 18.5% transaction recall at a 2% budget. | Honest given 974 training labels under real delay, but a judge skimming "detection efficacy" may not read the caveat. | Report alongside a random-split number so the *gap* is the finding, not the level. Lead with value recall (41.0%) and the 4.7× advantage over naive thresholding. |
| D-06 | **AGT-004 recall is 6.6%.** | Not a bug — the attack stays inside declared scope, so every hard check passes. Only the beneficiary is wrong. | Needs the semantic half of Head C (embedding comparison of stated intent vs item). Currently unbuilt. This is DRV-013 validated against our own detector. |
| D-07 | **Head B contributes almost nothing.** PR-AUC 0.063 alone; A+B+C (0.308) scores *below* C alone (0.383). | 45-day window with one mule ring gives sparse graph structure. | Longer horizon, more rings, or drop B and say why. Do not quietly delete it. |
| D-08 | **P3 graph fidelity is unmeasurable on public data.** | IEEE-CIS: DeviceInfo on 20.1% of rows, addr1 has 332 values. Sparkov: card-merchant graph 70.3% dense, zip maps 1:1 to card. | Accepted. The finding — that linkage attributes are stripped for privacy, so public benchmarks under-represent the signal that matters most — is stronger than the missing row. |
| D-09 | **No UPI-rail fidelity reference.** IEEE-CIS and Sparkov are both US card data. | R4/R5 are a deep rail with no floor. | PaySim would give a push-rail reference. Not yet loaded. |
| D-10 | **Corpus fraud rate is 4.49%.** Real payment base rates are 0.1–1%. | Chosen for training tractability. | Reweight for the F8 operating point, or state the base-rate assumption explicitly. |

---

## P2 — worth fixing

| ID | Defect | Detail |
|---|---|---|
| D-11 | Lag-1 IET ordering signal is ~0 after bias correction, not positive. | Reported, not gated. Whether it *should* be positive for benign traffic is unverified — the literature's claim is about fraud sequences. Needs a target from real data before it means anything. |
| D-12 | Attack parameter defaults were hand-chosen, not fitted. | Six campaigns per vector with mutation covers some of this, but the mutator has not run against an escape log yet. Phase 7 addresses it. |
| D-13 | Head C's semantic term is a category-match proxy, not an embedding. | `category_matches_intent` is a binary MCC comparison. The real version compares the stated intent to the item description. |
| D-14 | 24 devices in the world are bound to nobody. | Artifact of random allocation. Harmless, cosmetic. |
| D-15 | No transfer test (F10) has been run. | Train on synthetic, test on real held-out IEEE-CIS. The circularity-trap answer. Data is loaded; the run is not written. |
| D-16 | Response selection is implemented but never exercised end to end. | `CostModel.choose()` works and is latency-tested, but no run reports the money ledger the demo needs. |
| D-17 | Conformal budget is fitted on test-period genuine scores. | Should use a held-out calibration slice disjoint from both train and test. Currently mildly optimistic. |
| D-24 | **Push route badly under-detects.** UPI-004 mule farm 0.0% recall, DRV-019 0.4%, despite B_graph scoring 0.246 PR-AUC on that route. | Ranking works, thresholding does not. Budget is fitted on training-period genuine scores and the test-period distribution has shifted, so the threshold sits too high. Same root cause as D-17. |
| D-25 | **Aggregate friction is dominated by the largest route.** Overall step-up rate came out 0.50% when card (alpha=0.5%) is 43% of volume, so the push and agentic budgets are effectively unspent. | Either report friction per route rather than pooled, or set budgets to hit a target aggregate. The pooled number currently understates what the portfolio is allowed to spend. |
| D-26 | Card route recall collapsed to 2.7% on CRD-001 under the portfolio, against 9.3% under the monolith. | The alpha=0.5% card budget is far tighter than the monolith's effective threshold. Defensible as a design choice but must be stated, not buried. |

---

## P3 — state in the document, do not fix

| ID | Item |
|---|---|
| D-18 | Fidelity is calibrated against public datasets, not network traffic. Our ratios are relative improvements, not absolute guarantees. |
| D-19 | Agentic attacks run against a simulated protocol flow, not production Agent Pay. |
| D-20 | The mandate schema is a plausible shape, not a published standard. |
| D-21 | The escape-rate curve measures our detector against our own red team — internal loop health, not real-world coverage. |
| D-22 | The IEEE-CIS entity partition is reconstructed, so the noise floor is itself an estimate. Reported under three partitions. |
| D-23 | Sparkov is simulator output. Used as a cross-check corpus, never as a real-data floor. |

---

## Closed

| ID | Defect | How it closed |
|---|---|---|
| C-01 | Benign arrivals were Poisson; lag-1 IET came out at −0.117. | Session bursts plus day-scale activity states. Then found most of the residual was estimator bias, and switched to a permutation control. |
| C-02 | Entity activity was 15 events/45 days against a real median of 2. | Entity churn windows and category loyalty; then scaled population rather than rate. |
| C-03 | Zero training labels existed at the cut-off. | Modelled only the delayed stream. Added the fast investigator stream with a biased pre-filter, which is the actual operating condition. |
| C-04 | Adding heads made the fused score worse (0.196 → 0.134). | Heads were summed on raw WOE scale. Platt-calibrated each to an LLR first: 0.134 → 0.308. |
| C-05 | Head C could not see mandate contents. | Mandates were built and discarded at the CSV boundary. Now persisted to `mandates.csv` and joined. AGT-008 recall 9.6% → 85.6%. |
| C-06 | F5 compared fan-out before/after attacks, but positioning happened at build. | Now compares legitimate devices against ring devices. |
| C-11 | **D-28, defender saturated in round 1.** | The reservoir was fed this round's labels before training, so the defender always knew the current attacks. Reordered: train on what was known before this round, then learn from it afterwards. Round 1 now cold-starts with no attack knowledge, which is both realistic and the only way a learning curve can exist. |
| C-12 | **D-29, reservoir starved learning at a 6% target base rate** (~30 fraud labels admitted per round). | Raised to 15%. Reservoir now holds 723 fraud against 4,101 genuine after eight rounds, with both classes well represented in the WOE bins. |
| C-09 | **D-27, loop convergence inverted.** Benchmark escape rose 67.9% → 97.1% over six iterations. | Hypothesis was threshold chasing. Instrumenting ranking quality separately from threshold placement disproved it: PR-AUC collapsed 0.256 → 0.026, so the model was degrading. Cause was an accumulation asymmetry — every round added hundreds of fraud labels while labelled genuine traffic arrived only through a 1.2% alert filter, driving the training base rate from 15.5% to 40.4%. Fixed with a bounded class-balanced reservoir. Base rate now holds at 6.0%, PR-AUC stable at 0.14–0.28, benchmark escape flat instead of climbing. |
| C-10 | Prior correction applied to the ranking path crushed all probabilities toward zero; the conformal threshold landed on underflowed genuine scores and nothing flagged, sending escape to 100%. | Conformal thresholding is rank-based and a prior shift is monotone, so the correction cannot change what gets flagged — only what the number means. Moved to the cost path, where a probability multiplies a rupee amount and has to be honest. |
| C-08 | Fused score was worse than its best component on agentic fraud (0.475 vs 0.677). Logged as defect D-07. | Reclassified as a finding. Routing to per-population specialists recovers it: agentic route scores 0.673, and the portfolio beats the monolith 1.52x on value recall at matched friction. |
| C-07 | Anchor sheet was reported as 47 vectors; the real count was 64. | Counts now computed by script, never by hand. |
