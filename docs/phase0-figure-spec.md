# Phase 0 — Figure specification

**Rule this document enforces:** nothing gets built unless it produces a numbered artifact below.
If a piece of work does not feed a figure, a table, or a screen, it is cut. No exceptions, including
for things that are interesting.

**Rule for the write-up:** every claim in the document points at a figure. Every figure points at a
file in the repo. A judge who wants to verify any sentence can follow that chain in two steps.

---

## 1. The sixteen artifacts

Ordered as they appear in the walkthrough document. `Cost` is build effort, `Tier` is what happens
if we fall behind.

### F1 — Escape-rate convergence
**Tier 1 · Cost: high · Depends on: Phase 7**

Escape rate on the vertical axis, loop iteration on the horizontal. Six or more iterations.
Annotated at the points where red search discovered a new attack family, so the line visibly jumps
before recovering.

- **Proves:** the loop is real and not a diagram. Attacks train the defence, gaps generate attacks.
- **Scores:** novelty, efficacy.
- **Good version:** monotone decline with two visible discovery spikes, plus a stated stopping
  criterion (converged, or attacker search stalled — and we can tell which by whether mutator fitness
  is still improving).
- **Bad version:** a smooth line with no annotations, which reads as a training curve, not a loop.
- **This is the single most important artifact in the submission.** It is also expensive.
  Protect its schedule above everything else.

### F2 — Attack taxonomy matrix
**Tier 1 · Cost: low (renderer) · Depends on: Phase 1**

Kill-chain stage (7 F3 tactics) × rail (7), rendered as a density grid. Cell contents are vector
counts, shaded by count. Third axis (GenAI capability) available as a filter.

- **Proves:** breadth was derived from structure, not brainstormed.
- **Scores:** diversity.
- **Good version:** uneven density that matches how fraud actually distributes, with the empty cells
  explained in prose. Empty cells are a finding, not a gap.
- **Bad version:** a uniformly filled grid. It looks systematic and reads as padding.

### F3 — Evidence-grade distribution
**Tier 1 · Cost: near zero · Depends on: Phase 1**

Table of vector counts by novelty grade.

| Grade | Meaning | Count |
|---|---|---|
| N0 | Documented in the wild, citable | |
| N1 | Proven in a lab against a real implementation | |
| N2 | Named by protocol authors, not yet observed | |
| N3 | Derived by us from the cross-product | |
| N4 | **Discovered by our red-search loop during execution** | |

- **Proves:** intellectual honesty, and that the system identifies attacks rather than only us.
- **Scores:** diversity, novelty.
- **The N4 row is the point.** It is the deepest available reading of "identifies novel emerging
  attacks" and no other team will be able to fill it in.

### F4 — Behavioural fidelity table
**Tier 1 · Cost: medium · Depends on: Phase 4**

Degradation ratios on the four behavioural patterns, three rows.

| Generator | P1 inter-event | P2 burst | P3 graph motif | P4 velocity trigger |
|---|---|---|---|---|
| Real data noise floor | 1.0 | 1.0 | 1.0 | 1.0 |
| CTGAN (the standard approach) | | | | |
| Ours (agent-based) | | | | |

- **Proves:** fidelity against a defensible reference point rather than against nothing.
- **Scores:** fidelity — the only one of the five criteria that is otherwise unmeasurable.
- **Good version:** ours in low single digits, CTGAN in the twenties or worse, noise floor stated
  and its derivation explained (split real data in half, score the halves against each other).

### F5 — The ring pair
**Tier 2 · Cost: low · Depends on: Phase 4**

Two graphs side by side. Left: a real fraud ring, devices shared across accounts, mules fanning out.
Right: what CTGAN produces from the same data — every device with fan-out of one, no ring.

- **Proves:** viscerally, in two seconds, why the approach most competitors will use cannot work.
- **Scores:** fidelity.
- **Caption carries the argument:** this is not a tuning failure, it is structural. Row-independent
  generators sample shared attributes from marginals, so the ring is impossible by construction.

### F6 — The clean-fraud reveal
**Tier 1 · Cost: low · Depends on: Phase 5**

Twenty transactions displayed as a normal authorisation log. Valid tokens, sensible amounts, correct
merchant categories, successful responses, no velocity spikes, no geography anomalies. A standard
detector scores every one low-risk. Then the reveal: eight of them stole money.

- **Proves:** agentic fraud has no anomaly signature, so anomaly detection cannot see it.
- **Scores:** novelty.
- **This is the attack-as-artifact.** It is the equivalent of the reconstructed-faces grid that won
  the PSB hackathon. Put it early, before any architecture diagram.

### F7 — Live injection
**Tier 2 in the doc, Tier 1 in the UI · Cost: medium · Depends on: Phase 5**

In the document: a three-panel sequence showing a poisoned merchant listing, the agent reading it,
and the payment destination changing — with valid signatures and a clean audit trail throughout.
In the UI: a text box the judge types into themselves.

- **Proves:** the attack is real, reproducible, and not a story.
- **Scores:** novelty, feasibility.
- **Stretch:** run it against the public AP2 reference implementation rather than a mock. That
  converts it from a simulation into an exploit against real published code.

### F8 — Value detection at fixed friction budget
**Tier 1 · Cost: medium · Depends on: Phase 6**

Rupees of fraud prevented against step-up rate on genuine users. Our operating point marked, with a
naive probability-threshold baseline plotted alongside.

- **Proves:** we answered the brief's "keep false positives low" clause correctly.
- **Scores:** efficacy, feasibility.
- **The claim underneath:** thresholding on value-weighted likelihood ratio rather than raw
  probability, which follows from the Lagrangian of the budget constraint, and is optimal at fixed
  false-positive rate by Neyman-Pearson. Almost every implementation thresholds probability and
  provably misallocates the budget.

### F9 — Head ablation
**Tier 2 · Cost: low · Depends on: Phase 6**

Detection rate per attack family, by head. Behavioural, graph, intent, and fused.

- **Proves:** the intent head is necessary rather than decorative — heads A and B miss agentic
  compromise almost entirely, because there is no anomaly for them to find.
- **Scores:** efficacy, novelty.
- **This is the table that justifies the whole architecture.** Without it, three heads looks like
  three models bolted together.

### F10 — Synthetic-to-real transfer
**Tier 2 · Cost: medium · Depends on: Phase 6**

Train purely on our synthetic data, test on held-out real public data. Report the gap honestly.

- **Proves:** we escaped the circularity trap that will sink most submissions.
- **Scores:** efficacy credibility.
- **Report the gap even if it is large.** A stated transfer gap reads as rigour; an unstated one
  reads as a 0.99 that means nothing.

### F11 — Evaluation under delayed labels
**Tier 2 · Cost: medium · Depends on: Phase 6**

Performance under a two-stream label regime (small fast investigator feedback, large delayed
chargeback stream at δ) against the same model scored on a random split.

- **Proves:** we understand that you decide in milliseconds and learn weeks later.
- **Scores:** efficacy credibility, feasibility.
- **The sentence:** we do not report accuracy on a random split, because a random split assumes
  labels you would not have at decision time.

### F12 — Conformal coverage error across loop iterations
**Tier 2 · Cost: low once F1 exists · Depends on: Phase 7**

Observed step-up rate on genuine traffic against the calibrated budget, plotted per loop iteration.

- **Proves:** the coverage guarantee breaks *before any label arrives* when red search finds a
  genuinely new family, which makes it a label-free early warning that the threat distribution moved.
- **Scores:** novelty, feasibility.
- **This is the strongest original result available to us** and it costs almost nothing once F1
  exists. The conformal guarantee assumes exchangeability; the loop is a machine for deliberately
  violating exchangeability. Nobody else is holding both pieces.

### F13 — RBI control survival
**Tier 1 · Cost: low · Depends on: Phase 5**

Each proposed safeguard from the April 2026 discussion paper encoded as a rule, attacked, and scored.

| Proposed control | Attack that defeats it | Attacker cost | Survives? |
|---|---|---|---|
| One-hour cancellation window above ₹10,000 | | | |
| Trusted-person approval above ₹50,000 | | | |
| Annual credit cap without enhanced due diligence | | | |

- **Proves:** feasibility, in the specific regulatory environment the judges live in.
- **Scores:** feasibility, harder than anything else in the submission.
- **Cheap to build, disproportionate return.** Judging happens in Mumbai.

### F14 — Latency budget
**Tier 2 · Cost: low · Depends on: Phase 6**

p50 and p99 per head, plus fusion and response selection, against the sub-50ms industry reference.

- **Proves:** this could sit in an authorisation path, or an honest statement of where it sits if it
  cannot.
- **Scores:** feasibility.
- **If we miss the budget, say so and say where we sit instead** (near-real-time scoring rather than
  in-auth). Honesty scores better than silence and far better than a fabricated number.

### F15 — Node and feature declaration
**Tier 2 · Cost: near zero · Depends on: Phase 2**

Which position in the four-party model we occupy (network), which fields that position can see,
and which commonly-used features we deliberately excluded because that node cannot see them.

- **Proves:** we know how payments actually work.
- **Scores:** feasibility.
- **The tell we are avoiding:** models that use merchant-side device fingerprints alongside
  issuer-side balance history, data that never coexists in one place. Naming the trap and showing we
  avoided it is worth more than avoiding it silently.

### F16 — Limitations register
**Tier 1 · Cost: near zero · Depends on: nothing**

Every known weakness, each paired with what would close it in a real deployment.

Minimum entries: fidelity is calibrated against public data, not real network traffic, so our
numbers are relative improvements not absolute guarantees. Agentic attacks run against reference
implementations, not production Agent Pay. The intent head assumes a mandate schema that is not yet
a public standard. The escape-rate curve measures our detector against our own red team, which is
internal loop health, not proof of real-world coverage.

- **Proves:** judgement.
- **Scores:** all five, indirectly, because it changes how every other number is read.
- **Free to produce and disproportionately effective.** A team that names its own limits precisely
  reads as one that understands the problem.

---

## 2. Cost-tier summary — what to protect

| Cost | Artifacts | Scheduling note |
|---|---|---|
| Near zero (writing only) | F3, F15, F16 | Do these during any blocked period |
| Low | F2, F5, F6, F9, F13, F14 | Safe |
| Medium | F4, F7, F8, F10, F11 | Watch these |
| High | **F1, F12** | **Protect above all else** |

F1 and F12 are simultaneously the most valuable and the most expensive, and F12 is nearly free once
F1 exists. Everything in Phase 7 exists to produce them. If Phase 6 overruns, cut detector polish
before cutting loop iterations.

---

## 3. Document skeleton

The brief names four required contents. Mapped:

**0. Opening — the problem in one page**
F6 (the clean-fraud reveal) goes here, before any architecture. Lead with the attack, not the system.

**1. The novel fraud attacks we identified**
F2 taxonomy matrix · F3 evidence grades · F7 live injection sequence
Prose: the three-axis derivation method, the novelty ladder, the F3 extension claim.

**2. How our system generates and simulates those attacks**
F4 fidelity table · F5 ring pair
Prose: entities with histories rather than rows, and why that choice was forced rather than
preferred.

**3. Our detection and mitigation model, with efficacy results**
F8 budget curve · F9 head ablation · F10 transfer · F11 delayed labels
Prose: three heads, LLR fusion with stated independence violation, expected-cost response selection
conditional on attack class, SPRT over the agent mandate session.

**4. Real-world feasibility in live payments**
F13 RBI controls · F14 latency · F15 node declaration
Prose: label latency, drift and retraining cadence, explainability via evidence terms, PCI posture.

**5. The loop**
F1 escape-rate convergence · F12 coverage error
Prose: iterated best-response framing, stopping criterion, and the label-free drift result.

**6. What we know is wrong**
F16.

---

## 4. UI screens, mapped

| Screen | Renders | Purpose |
|---|---|---|
| Threat map | F2, F3 | Breadth, made clickable |
| Range | F5, live world ticking | Fidelity, made watchable |
| Detector | F6, F8, F9, running cost ledger | The reveal, and the budget made visible |
| Loop | F1, F12, with a "run next iteration" button | The thesis, turnable by a judge |
| Injection box | F7 | The punch |

The UI computes nothing new. It reads logs the pipeline already wrote. Build it last, but reserve
real time for it.

**Ninety-second path a judge should be able to take unaided:** injection box → detector reveal →
loop chart → run one iteration → watch escape rate drop.

---

## 5. Headline claims — the sentences the whole submission must support

If we cannot say all six of these truthfully at the end, something failed.

1. N vectors across the kill-chain × rail matrix, mapped to MITRE F3, of which M extend the framework
   with GenAI-native techniques.
2. Our simulator scores within single-digit degradation of the real-data noise floor on behavioural
   patterns that the standard tabular approach provably cannot reproduce.
3. Agentic compromise defeats our behavioural and graph heads almost entirely, and the intent head
   catches it — so the third head is necessary, and here is the ablation.
4. We evaluate under delayed labels and report the synthetic-to-real transfer gap, because a random
   split assumes labels you would not have.
5. Our loop discovered K attack variants that were not in the seed taxonomy.
6. The coverage guarantee breaks before any label arrives when the attacker finds new ground, which
   makes it a label-free drift alarm.

---

## 6. Explicit cut list

Not building, and saying so in the document where relevant:

- **Deepfake audio or video generation.** High cost, and the taxonomy covers the vector more cheaply.
- **Fine-tuning any language model.** Costs days, improves nothing that gets scored. Detection heads
  are trained from scratch, which is ordinary supervised learning, not fine-tuning. State the
  reasoning — it reads as judgement, and silence reads as oversight.
- **Auth, accounts, or persistence in the web app.** It is a demo.
- **More than two rails at depth.** UPI and agentic card-not-present. Everything else is taxonomy
  coverage only.
- **k-NN transaction typicality.** Carried from prior work, but the graph head does the same job
  better here. Cut without regret if Phase 6 runs long.
- **Real-time streaming infrastructure.** Batch is fine; the latency table is measured per-decision,
  not end-to-end throughput.
- **A fifth or sixth detection head.** Three, with an ablation proving each earns its place.

---

## 7. Definition of done for Phase 0

- [x] Figure list written and frozen
- [ ] Every team member has read it and agreed the cut list
- [ ] Document skeleton created as an empty .docx with section headers and figure placeholders
- [ ] Repo scaffolded with a `figures/` directory containing one stub file per artifact, named F01–F16

That last item is the enforcement mechanism. A figure with no file is visible immediately, and at the
end the directory listing is the completion checklist.
