<div align="center">

# Chakra

**A threat-informed adversarial range for payment security**

Mastercard Innovation Challenge @ GFF 2026 · AI Defense Lab

*Identify · Generate · Defend — wired into a loop*

[Solution walkthrough (.docx)](https://docs.google.com/document/d/1x7NO2jHm_xP8_yaayhpf4mervahnNpyR/edit?usp=sharing&ouid=113164720406108171368&rtpof=true&sd=true) · [Live prototype](https://agent-6a95b7ec466cb5101e--eclectic-haupia-ac817f.netlify.app/)

</div>

---

## The finding, first

We measured what AI-agent payment fraud looks like to a conventional fraud
system. This is the whole submission in one table:

| | Approved | Passed 3DS authentication | Tripped a velocity rule |
|---|---|---|---|
| **Legitimate traffic** | 93.6% | 26.8% | 3.2% |
| **Agent compromise (AGT-004)** | **99.1%** | **100.0%** | **0.0%** |
| **Authorisation drift (AGT-008)** | **98.4%** | **100.0%** | **0.0%** |
| Card testing (CRD-001) — control | 47.7% | 71.7% | 45.2% |

Agentic fraud is approved **more often than genuine customers**, authenticates
**every single time**, and **never** trips a velocity rule.

This is not an artefact of our simulator. It follows from the mechanism: the
agentic token *is* the authentication artefact so there is no step-up, the
mandate is genuinely signed by the customer, and the agent carries real history
at a real merchant. Nothing about the transaction is anomalous. The only thing
wrong is where the money went, and no field on an ISO 8583 authorisation
message records that.

Card testing is the control and behaves exactly as expected — conventional
detection works fine on conventional fraud.

**Consequence:** anomaly detection cannot address the fastest-growing fraud
surface in payments, and no amount of tuning changes that. Every production
fraud system asks *is this transaction unusual?* We built one that asks
**was the decision that produced this transaction manipulated?**

Three of our five detection heads exist only because of that reframing.

---

## The four questions the brief asks

### 1 · What novel attacks did you identify?

**94 vectors** across 7 payment rails and 8 MITRE F3 tactics. 64 trace to a
published source; 30 we derived from empty cells in the coverage matrix. Every
vector carries an evidence grade, so the count is checkable rather than
asserted.

| Grade | Meaning | Count |
|---|---|---|
| **N0** | Documented in the wild — incident, CVE, or regulator finding | 25 |
| **N1** | Proven in a laboratory against a real implementation | 3 |
| **N2** | Named as a threat by the protocol's own authors | 36 |
| **N3** | Derived here, from empty cells in the coverage matrix | 30 |
| **N4** | Discovered at runtime by the red-search loop | 0 |

A keyword scan of all 123 MITRE F3 v1.1 techniques for `ai`, `llm`, `model`,
`deepfake`, `synthetic media`, `voice cloning`, `generative`, `autonomous` and
`mandate` returned **zero matches**. All 28 of our `F3X-` techniques are
therefore genuine extensions to the framework, namespaced so they cannot be
confused with the standard.

Families: `AGT` agentic 39 · `DRV` derived 30 · `CRD` card 10 · `UPI` 9 ·
`HUM` human-targeted 6. Full listing in [`taxonomy/taxonomy.json`](taxonomy/)
and Appendix A of the walkthrough.

### 2 · How does the system generate and simulate them?

An agent-based world, **not a tabular generator**. 11,000 payers, 9,200
devices, 2,824 agents, 900 merchants and 120 mules carry state across 180
simulated days. Transactions are the exhaust, not the object.

Row-independent generators sample each row from a marginal, so a handset shared
by thirty mule accounts is impossible and a mule dormant for eleven days that
then moves ₹42,000 in six hours is impossible. Both of those *are* fraud. Six
attacks are implemented as world perturbations rather than row appends, each
exposing declared parameter ranges the red-search mutator can move.

Fidelity is measured against a denominator: we split 590,540 real IEEE-CIS
transactions in half **by entity**, measure how different real data is from
itself, and report our distance over that noise floor. Sequence fidelity
**7.48** against the strongest row-independent control's **12.45**.

### 3 · What is the detection model, and how well does it work?

Five heads, routed on observable fields only, fused as Platt-calibrated
log-likelihood ratios under a per-route conformal friction budget, with
expected-cost action selection and counterfactual reason codes.

| Head | Asks | Features |
|---|---|---|
| **A** behavioural | Does this look like this entity's own past? | 19 |
| **B** graph | Who is standing next to it, and how long were they quiet? | 10 |
| **C** intent | Did the agent do what it was authorised to do? | 19 |
| **P** peer | Where does this sit among comparable instructions? | 9 |
| **S** session | Is a standing delegation drifting? | 7 |

**ROC-AUC 0.9895 · PR-AUC 0.744** at a 1.02% test-period base rate.
Precision **61.5%**, recall **77.4%**, F1 **0.685** at the shipped 0.5%
friction budget — a conformal cut that holds a stated budget, not a threshold
tuned to flatter F1.

### 4 · Is it feasible in live payments?

Decision latency of **0.048 ms** against a 50 ms authorisation window, pure
Python, single-threaded. Node visibility is enforced in code: the feature
builder raises on any field the network position cannot observe, so the classic
error of mixing issuer-side balances with merchant-side device fingerprints is
impossible rather than discouraged. Every decision carries ranked evidence and
a counterfactual. And peer-relative intent is a control **only a network can
run** — a single issuer sees a fraction of the agent population.

---

## Headline results

| Figure | Result |
|---|---|
| **F6** Clean-fraud reveal | The table at the top of this file |
| **F1** Loop convergence | Frozen-attack escape 100% → 21% by round 3, rising to 43% by round 8 as the training reservoir drifts — reported, not hidden |
| **F4** Behavioural fidelity | **7.48** vs row-independent **12.45** on sequence metrics (1.0 = real-data noise floor) |
| **F7** External baselines | Same features, same temporal split, same labels, same conformal cut — only the model varies |
| **F8** Head ablation, agentic | Anomaly heads together **0.367**; intent **0.708**, peer **0.595** alone; all five **0.879** |
| **F9b** Routed portfolio | **98.8%** of fraud value recovered vs a monolith's **80.7%** at matched 1.15% friction |
| **F14** Latency | **0.048 ms** per decision, end to end |

Fraud base rate is **1.22%** in the corpus and 1.02% in the test period,
deliberately realistic. We could have reported a far higher PR-AUC at an
inflated base rate and chose not to.

**An external baseline told us we were wrong.** Our first run put the
weight-of-evidence scorecards at 0.429 PR-AUC against gradient boosting's
0.860. The scorecard bins every feature into twelve quantiles and damps
correlated terms, which discards a great deal of information for
interpretability. We changed the base learner to boosted trees and kept the
scorecards alongside, since they supply the reason codes and the additive
surface the counterfactual generator needs. PR-AUC moved 0.429 → **0.744** and
every implemented attack improved. The architecture was never the problem; the
base learner was.

---

## Layout

```
chakra/
  schema/       transaction, entity, mandate, labels, visibility enforcement
  world/        arrival processes, the tick engine
  rails/        ISO 8583 and UPI adapters
  attacks/      six plugins with declared mutable parameter ranges
  fidelity/     P1-P4 metrics, noise floor, dataset loaders
  detect/       features, heads, fusion, routing, peer, semantic,
                sequential, adversarial, counterfactual, baselines
  redsearch/    escape log, mutator, fitness, convergence
  genai/        Gemini client, cache-first, runs offline
scripts/        one runnable stage per pillar
taxonomy/       94 vectors as data, plus the renderer
figures/        PNG for the write-up, JSON for the UI
artifacts/      committed GenAI output so the repo runs without a key
docs/           figure spec, taxonomy, anchor sheet, defect register
```

---

## Reproduce

Nothing here needs an API key. Everything generative is pre-computed and
committed to `artifacts/genai/`.

```bash
git clone FILL_IN && cd chakra
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# optional: real-data fidelity floor (see data/README.md for sources)
#   data/train_transaction.csv, data/train_identity.csv   (IEEE-CIS)

python scripts/smoke.py           # contract tests
python scripts/run_benign.py      # the world      → benign transactions
python scripts/run_attacks.py     # attacks        → labelled corpus, F5, F6
python scripts/run_detect.py      # detector       → F7, F8, F9, F14
python scripts/run_portfolio.py   # routing + gate → F9b
python scripts/run_loop.py        # closed loop    → F1, F12
python scripts/run_fidelity.py    # needs IEEE-CIS → F4
python scripts/make_figures.py    # PNG + JSON for the document and the UI
```

Roughly 12 minutes end to end on a laptop. Python 3.11+. The world seed is
pinned, so a clean clone reproduces the numbers in `figures/data/`.

---

## Where generative AI is used

| Side | Purpose | Model |
|---|---|---|
| Attacker | Poisoned listings, scam text, novel vector proposals | `gemini-2.5-flash` |
| Defender | Head C's semantic term | embedding endpoint only |

The split is a finding, not a convenience. Published prompt-injection success
rates track alignment training rather than price tier, so a cheap
instruction-following model is the *correct* choice for the victim agent — it
is what a cost-conscious merchant would deploy and it is reliably exploitable.
It is the *wrong* choice for the defender, because the defender is itself a
target and an embedding endpoint has no instruction-following surface to
hijack. **The tier cheap enough to run on every checkout is the tier that gets
hijacked.**

---

## What is genuinely ours

Standard and well executed, which wins nothing alone: weight-of-evidence
scorecards, boosted trees, Platt calibration, several heads over different
feature families, split conformal prediction, expected-cost selection.

Ours:

1. **Intent divergence as a continuous detection signal.** AP2's signed
   mandates and zero-trust runtime verification treat intent binding as an
   *enforcement* control that fails closed on a rule violation. We score it and
   let a cost function decide — which covers the case those approaches state
   they cannot, a legitimate agent manipulated into a valid mandate for a
   malicious purpose.
2. **Peer-relative intent scoring.** Comparing an execution against other
   executions of the same instruction. Requires a corpus of comparable
   mandates, which our simulator produces and a public dataset cannot.
3. **Conformal coverage as a label-free drift alarm**, from noticing that the
   red-search loop violates the guarantee's own exchangeability assumption on
   purpose.
4. **A Stackelberg-corrected threshold** computed against a real escape log, so
   the loop sets the operating point rather than merely feeding the detector.
5. **A sequential test over an agentic mandate session**, redefined from
   browse-to-checkout to a standing delegation operating over weeks.
6. **The step-up discount**, where the attack taxonomy changes the decision
   rule, because a challenge is worthless against an attack that passes
   authentication.
7. **28 proposed extensions to MITRE F3**, from a scan proving the framework
   has zero agentic coverage.
8. **The defect register itself** — 30 tracked, 12 closed, each diagnosis kept.

---

## Honest limitations

The register in [`docs/defect-register.md`](docs/defect-register.md) is a
deliverable, not an apology.

**Weak results.** Mule-farm recall is 40%, our poorest figure, on only ten test
-period instances — noisy as well as low. Agent compromise sits at 88%, but it
stays inside every declared mandate bound, so all seven deterministic checks
pass and detection rests entirely on probabilistic evidence.

**Measurement gaps.** Graph-motif fidelity is not measurable on public data:
the attributes that link accounts into rings are exactly the attributes
stripped before a dataset can be published. There is no UPI-rail fidelity
reference, since both real corpora are US card data. The IEEE-CIS entity
partition is reconstructed, and we report the floor under three partitions.

**Scope.** The escape-rate curve measures our detector against our own red
team — internal loop health, not proof of real-world coverage. Agentic attacks
run against simulated protocol flows, not production Agent Pay; the
vulnerabilities reproduced are published and real, but the environment is ours.
The recurring route is defined and budgeted but not yet exercised by an
implemented attack.

**Three times we were wrong**, and once an experiment failed to support the
argument it was built to make. All recorded in §8.4 of the walkthrough with the
incorrect values retained beside their corrections.

---

## Sources

| | |
|---|---|
| MITRE Fight Fraud Framework v1.1 | `github.com/center-for-threat-informed-defense/fight-fraud-framework` |
| OWASP Top 10 for Agentic Applications 2026 | `genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/` |
| AP2 Security and Privacy Considerations | `ap2-protocol.org/ap2/security_and_privacy_considerations/` |
| RBI, Exploring Safeguards in Digital Payments | `rbi.org.in/Scripts/PublicationsView.aspx?id=23810` |
| EchoLeak, CVE-2025-32711 | `nvd.nist.gov/vuln/detail/CVE-2025-32711` |
| Debi, Zhu & Sen Gupta, Whispers of Wealth | `arxiv.org/abs/2601.22569` |
| IEEE-CIS Fraud Detection | Vesta Corporation, 590,540 transactions |
| Sparkov | Kaggle `kartik2112/fraud-detection` — cross-check corpus only |

Full reference list in the walkthrough.

---

*Every number in this repository is read from a run of this code. Where a
number was wrong and later corrected, both the wrong value and the correction
are recorded — here, in the walkthrough, and in `docs/defect-register.md`.*
