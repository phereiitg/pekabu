<div align="center">

# Chakra

**A threat-informed adversarial range for payment security**

Mastercard Innovation Challenge @ GFF 2026 - AI Defense Lab

*Identify · Generate · Defend - wired into a loop*

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
mandate is genuinely signed, and the agent carries real history. Nothing about
the transaction is anomalous. The only thing wrong is where the money went,
and no field on an ISO 8583 authorisation message records that.

Card testing is the control, and it behaves exactly as expected — conventional
detection works fine on conventional fraud.

**Consequence:** anomaly detection cannot address the fastest-growing fraud
surface in payments, and no amount of tuning changes that. A third detector
is required, and it has to compare authorised *intent* against executed
*action*.

---

## What this is

Three pillars, wired into a closed loop, all runnable.

```
  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
  │  1 IDENTIFY  │───▶│  2 GENERATE  │───▶│   3 DEFEND   │───▶│ 4 RED SEARCH │
  │              │    │              │    │              │    │              │
  │ 94 vectors   │    │ agent-based  │    │ 3 heads +    │    │ mutate what  │
  │ MITRE F3     │    │ world, 5     │    │ routing, LLR │    │ escaped,     │
  │ 28 extensions│    │ rails, 214k  │    │ fusion, cost │    │ retrain      │
  │ N0–N4 graded │    │ transactions │    │ selection    │    │              │
  └──────────────┘    └──────────────┘    └──────────────┘    └──────┬───────┘
         ▲                                                           │
         └───────────────────────────────────────────────────────────┘
                    escapes become new attacks (N4)
```

**1 · Identify** — 94 attack vectors, 64 traced to documented sources, 30
derived from empty cells in an 8-tactic × 7-rail matrix. Every vector carries
a MITRE F3 technique ID and an evidence grade.

**2 · Generate** — an agent-based world where entities carry state across
time. Transactions are the exhaust, not the object. Six attacks implemented as
world perturbations rather than row appends.

**3 · Defend** — three detection heads routed by observable transaction
properties, fused as calibrated log-likelihood ratios, with expected-cost
response selection under a conformal friction budget.

**4 · Red search** — a parameter mutator driven by the escape log, closing the
loop.

---

## Headline results

| Figure | Result |
|---|---|
| **F1** Loop convergence | Escape rate **100% → 48%** over 8 iterations on frozen attacks |
| **F4** Behavioural fidelity | **7.48** vs row-independent **12.45** on sequence metrics (1.0 = real-data noise floor) |
| **F6** Clean-fraud reveal | The table above |
| **F8** Value at fixed friction | **41.0%** value recall vs **8.7%** for naive probability thresholding, same budget |
| **F9** Head ablation | Intent head **0.708** PR-AUC on agentic vs **0.095** for the graph head |
| **F9b** Routed portfolio | **2.00× value recall** over a monolithic classifier at matched friction |
| **F14** Latency | **0.048 ms/transaction** end-to-end, single-threaded Python |

Fraud base rate is **1.23%**, deliberately realistic. We could report 0.95
PR-AUC at an 8% base rate and chose not to — see [Honest limitations](#honest-limitations).

---

## Reproduce

Nothing here needs an API key. Everything generative is pre-computed and
committed to `artifacts/genai/`.

```bash
git clone https://github.com/phereiitg/pekabu && cd pekabu
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# optional: real-data fidelity floor (see data/README.md for sources)
#   data/train_transaction.csv, data/train_identity.csv   (IEEE-CIS)

python scripts/smoke.py           # contract tests
python scripts/run_benign.py      # the world      → 211k benign transactions
python scripts/run_attacks.py     # attacks        → labelled corpus + F5, F6
python scripts/run_detect.py      # detector       → F8, F9, F11, F14
python scripts/run_portfolio.py   # routing        → F9b
python scripts/run_loop.py        # closed loop    → F1, F12
python scripts/run_fidelity.py    # needs IEEE-CIS → F4
```

Runtime is roughly 12 minutes end to end on a laptop. Python 3.11+.

---

## How the attacks were sourced

**We did not invent them.** Every vector carries an evidence grade so the
diversity claim is auditable rather than asserted.

| Grade | Meaning | Count |
|---|---|---|
| **N0** | Documented in the wild — named incident, CVE, or regulator finding | 21 |
| **N1** | Proven in a lab against a real implementation | 4 |
| **N2** | Named as a threat by the protocol's own authors | 39 |
| **N3** | Derived by us from empty cells in the matrix | 30 |
| **N4** | Discovered by our red-search loop at runtime | — |

Sources: MITRE Fight Fraud Framework v1.1, OWASP Top 10 for Agentic
Applications 2026, Google AP2 security documentation, Cloud Security Alliance
AP2 guidance, RBI's April 2026 discussion paper on digital payment safeguards,
and published red-team literature.

### We extend MITRE F3

F3 v1.1 contains 74 top-level techniques and 49 sub-techniques across 8
tactics. We keyword-scanned all 123 for `ai`, `llm`, `model`, `deepfake`,
`synthetic media`, `voice cloning`, `generative`, `autonomous` and `mandate`.

**Zero hits.** F3 has no agentic or GenAI coverage.

So all **28** of our `F3X-` techniques are genuine extensions rather than
relabelled existing entries, spanning tactics F3 does not currently reach.

---

## Where generative AI is used

Deliberately limited, and split by function. See
[`chakra/genai/client.py`](chakra/genai/client.py).

**Attacker side — generation, cheap model, on purpose.** Poisoned merchant
listings, social-engineering text, and novel vector proposals from the escape
log. Model: `gemini-2.5-flash`.

**Defender side — embeddings, not generation.** Head C's semantic term uses
`text-embedding-004`.

The split is a finding rather than a convenience. Published measurements of
indirect prompt injection against agentic commerce platforms:

| Model | Attack success rate |
|---|---|
| Gemini 2.5 Flash | 99–100% |
| GPT-4o-mini | 100% |
| GPT-4o | 68% |
| Llama-3.3-70B | 10% |
| Gemini 2.5 Pro, Claude Sonnet | 0% |

Susceptibility tracks alignment training, not price tier. So Flash is the
*correct* choice for the victim agent — it is what a cost-conscious merchant
would actually deploy, and it is reliably exploitable. It is the *wrong*
choice for the defender, because the defender is itself a target (DRV-013 in
our taxonomy attacks exactly that component), and an embedding endpoint has no
instruction-following surface to hijack.

**The tier cheap enough to run on every checkout is the tier that gets
hijacked.** That is a real deployment trade-off and we can measure it.

---

## Engineering decisions worth explaining

### Entities with memory, not rows from a distribution

The standard approach trains a tabular generator on real data and samples new
rows. There is a proof that this cannot work for fraud: row-independent
generators sample shared attributes from marginals, which drives every device
fan-out toward 1 and makes ring structure impossible by construction. They
also produce non-positive within-entity inter-event autocorrelation, so burst
patterns are unreachable regardless of training.

Both of those *are* fraud. So we simulate entities that carry state — a mule
with a `recruited → dormant → burst → burned` trajectory, a device bound to
twenty accounts, an agent with 500 ticks of clean history — and let
transactions fall out.

Measured: legitimate devices sit at fan-out 1–3, ring devices at 13–37, with
no overlap.

### Node visibility is enforced, not promised

We occupy the **network** position in the four-party model. Every feature
declares the raw fields it derives from, and the builder raises on anything
that position cannot observe:

```
VisibilityError: 2 field(s) not observable at node 'network':
  account_balance (issuer-side only);
  device_fingerprint (merchant-side only; never reaches the network on card rails)
```

The commonest tell in hackathon fraud models is a classifier using
merchant-side device fingerprints alongside issuer-side balance history — data
that never coexists at any single node. This makes that impossible rather than
discouraged. F15 renders directly from the same declarations, so the document
and the code cannot drift.

### No random splits exist in this repository

You decide in milliseconds and learn weeks later. We model both label streams:
a biased rules pre-filter feeding an investigator at +6h, and chargebacks at a
lognormal ~21 days, for the ~70% of fraud anyone reports.

Result: **3,457 usable labels from 138,607 training-period transactions.** A
random split would have handed the model all of them on day one.

`chakra/schema/labels.py` exposes `split_no_time_travel()` and deliberately
provides no random-split helper, so nobody reaches for one at 3am.

### Routing beats a monolithic classifier

Different trust-breaks are visible by different means. Routes key on
**observable fields only** — never on trust link or attack family, which are
labels.

| Route | Key | Head A | Head B | Head C | Routed |
|---|---|---|---|---|---|
| agentic | `agent_id` present | 0.168 | 0.095 | **0.708** | **0.645** |
| push | rail ∈ {R4, R5} | 0.189 | **0.634** | — | **0.769** |
| card | rail ∈ {R1, R2} | **0.570** | 0.007 | — | 0.493 |

Every cell reported, including Head B's 0.007 on card. Three populations,
three different winners. At matched friction, routing recovers **2.00× more
value** than one fused model.

### Value-weighted thresholding

Given a fixed friction budget, the Lagrangian gives *act when value × likelihood
ratio exceeds λ*, not *act when probability exceeds λ*. By Neyman-Pearson,
thresholding a likelihood ratio is the most powerful test at a fixed
false-positive rate, so this is the optimal form rather than one option among
several.

At a 2% budget: **41.0% value recall against 8.7%** for naive probability
thresholding. Nearly double the money at identical customer friction.

### The coverage guarantee is a label-free drift alarm

Conformal calibration holds a stated step-up rate on genuine traffic with a
finite-sample, distribution-free guarantee. That guarantee assumes
exchangeability — and the red-search loop is a machine for deliberately
violating exchangeability.

So when coverage breaks, the threat distribution has shifted, **and it breaks
before any label arrives.** Given that chargebacks take weeks and ~30% of
fraud is never reported at all, a drift signal needing no labels is the only
kind that can fire in time.

---

## Honest limitations

The full register is in [`docs/defect-register.md`](docs/defect-register.md) —
30 defects tracked, 12 closed, each with severity and what closing it takes.
The register is a deliverable, not an apology: a team that names its own limits
precisely reads differently from one that reports 0.99 and stops.

Selected:

**P3 graph fidelity is not measurable on public data.** IEEE-CIS carries
DeviceInfo on 20.1% of rows and `addr1` has 332 distinct values across 590,540
transactions. Sparkov's card-merchant graph is 70.3% dense with `zip` mapping
1:1 to card. Too little linkage in one, too much and none of it selective in
the other.

The pattern behind both is worth stating: **the attributes that link accounts
into rings — device fingerprints, IPs, shipping addresses, phone numbers — are
exactly the attributes stripped before a dataset can be published.** The graph
structure fraud detection depends on is the structure privacy requires be
removed. Public benchmarks therefore systematically under-represent the signal
that matters most.

**The noise floor is a property of the reference corpus.** Sparkov's split-half
floor is up to 21× tighter than IEEE-CIS's, because Sparkov *is* a simulator
and its halves come from one stationary process. Scoring against a synthetic
reference inflates every degradation ratio by roughly an order of magnitude. A
fidelity claim must name its reference corpus and state whether it is real. We
use IEEE-CIS, which is real.

**The IEEE-CIS entity partition is reconstructed.** The dataset has no entity
identifier. The community-standard UID gives 58% singletons, so we report the
floor under three partitions and the spread with it.

**AGT-004 recall is 27.3%.** Not a bug — the attack stays inside declared
mandate scope, so every hard check passes and only the beneficiary is wrong.
Catching it needs Head C's semantic half. This is DRV-013 in our own taxonomy,
validated against our own detector.

**Agentic attacks run against simulated protocol flows**, not production Agent
Pay. The mandate schema is a plausible shape, not a published standard.

**The escape-rate curve measures our detector against our own red team** —
internal loop health, not proof of real-world coverage.

---

## Repository layout

```
chakra/
  schema/       transaction, entity, mandate, labels, visibility enforcement
  world/        arrival processes, the tick engine
  rails/        ISO 8583 and UPI adapters
  attacks/      six plugins with declared mutable parameter ranges
  fidelity/     P1–P4 metrics, noise floor, dataset loaders
  detect/       features, heads, fusion, routing, training reservoir
  redsearch/    escape log, mutator, fitness, convergence
  genai/        Gemini client, cache-first, runs offline
scripts/        one runnable stage per pillar
taxonomy/       94 vectors as data, plus the renderer
artifacts/      committed GenAI output so the repo runs without a key
docs/           figure spec, taxonomy, anchor sheet, defect register
```

---

## References

MITRE Center for Threat-Informed Defense, *Fight Fraud Framework* v1.1 (2026) ·
OWASP GenAI Security Project, *Top 10 for Agentic Applications* 2026 ·
Google, *AP2 Security and Privacy Considerations* ·
Cloud Security Alliance, *Secure Use of the Agent Payments Protocol* ·
Reserve Bank of India, *Exploring Safeguards in Digital Payments to Curb
Frauds* (April 2026) ·
Dal Pozzolo et al., *Credit Card Fraud Detection: A Realistic Modeling and a
Novel Learning Strategy*, IEEE TNNLS (2018) ·
Vesta / IEEE-CIS Fraud Detection dataset ·
Amazon Fraud Dataset Benchmark
