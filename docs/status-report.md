# Where we are — in plain words

---

## 1. What the thing actually is

A fake payments world that we attack on purpose, and a guard that tries to
catch the attacks. Both are real programs. The world runs for 45 simulated
days and produces about 58,000 transactions, roughly 4.5% of which are fraud.

Three parts, wired in a circle:

1. **A list of attacks.** 94 of them, written down properly.
2. **A fake world** where those attacks actually happen.
3. **A guard** that watches the world and flags what it thinks is fraud.

Then the circle: whatever gets past the guard tells us which attacks to try
harder, and those go back into the guard's training.

---

## 2. Where the fraud patterns come from

This is the part most teams get wrong, so it is worth being precise.

**We did not invent the attacks.** 64 of the 94 come from documents:

| Source | What it gave us |
|---|---|
| MITRE F3 (April 2026) | The industry-standard fraud vocabulary. 8 tactics, 123 techniques. |
| OWASP Agentic Top 10 | 10 categories of AI-agent attack, each with real incidents attached |
| Google's AP2 security docs | A threat list written by the engineers who built the protocol |
| Published red-team papers | Attacks proven to work against real code, with success rates |
| RBI's April 2026 paper | What India's regulator says is actually happening |
| Incident record | EchoLeak, the Arup deepfake call, malicious MCP servers |

The other 30 we **derived**, not imagined. We built a grid — 8 attack stages
across 7 payment rails — filled in what the documents cover, and looked at the
empty squares. An empty square either means nobody has thought of it yet, or
it is genuinely impossible. Working out which is how the new attacks appeared.

**Every attack carries an honesty grade:**

- **N0** — happened in the real world, here is the news story
- **N1** — proven in a lab against real code
- **N2** — the protocol's own authors listed it as a risk
- **N3** — we worked it out ourselves
- **N4** — our system discovered it while running

That grading is the point. Anyone can claim 90 attacks. We can show which ones
are documented and which are ours, which means the count is checkable instead
of a boast.

**A finding worth mentioning:** MITRE F3 has 123 techniques and *zero* of them
mention AI, agents, deepfakes, or mandates. We searched. So all 28 of our
agentic techniques are genuine additions to an industry standard, not
relabelled versions of something already there.

---

## 3. How we make the fake fraud

### The one decision everything rests on

**We do not generate fraudulent transactions. We build a world where fraud
happens, and write down what comes out.**

That sounds like wordplay. It is not, and there is a mathematical proof behind
it.

The standard approach is to train a model (CTGAN and similar) on real
transaction data and have it produce new rows that look statistically similar.
A 2026 paper proves this cannot work for fraud, because those models generate
each row independently. If every row is independent, then:

- A phone shared by 20 mule accounts is impossible. Each row picks a phone at
  random, so every phone ends up used by about one account.
- A mule that sits quiet for 200 days then moves money in an hour is
  impossible. That is a behaviour over time, and a row has no memory.

**Both of those are exactly what fraud looks like.** So the standard approach
throws away the signal and keeps the noise.

### What we do instead

We build things that have memory:

| Thing | What it remembers |
|---|---|
| **Person** | Their shops, their phone, their spending habits, their busy weeks |
| **Phone** | Which accounts use it — this is where fraud rings become visible |
| **Shop** | Its category, how it was signed up, whether its listing is poisoned |
| **AI agent** | Its token, its permissions, its history, its memory |
| **Mule account** | Where it is in its life: recruited → quiet → burst → burned |
| **Criminal** | Their budget, their skill level, what they are trying to steal |

Time moves forward. People shop. Agents buy things. Criminals run operations.
Transactions are the **exhaust** — the record of what happened, not the thing
we designed.

### Six attacks we actually built

| Attack | What it does | Can a normal system see it? |
|---|---|---|
| Mule farm | Recruits 14 accounts on 2 phones, waits 11 days, moves ₹42,000 through them in 6 hours | Yes — the shared phones give it away |
| Card testing | Tiny ₹18 probes across shops to find which stolen cards still work | Yes — most of them get declined |
| Collect-request scam | Tricks someone into approving a payment request | **No** — the victim genuinely approved it |
| Agent compromise | Poisons a shop listing so an AI shopper redirects the money | **No** — see below |
| Authorisation drift | The spending limit was cut, but the agent uses the old permission | **No** — the permission was genuinely signed |
| Micro-structuring | Splits ₹85,000 into chunks under ₹10,000 to dodge RBI's proposed delay | Partly |

### The demonstration that matters

We measured what these look like to a normal fraud system:

| | Approved | Passed authentication | Tripped a speed rule |
|---|---|---|---|
| **Normal traffic** | 93.6% | 26.8% | 3.2% |
| **AI agent fraud** | **99.1%** | **100%** | **0.0%** |
| Card testing | 47.7% | 71.7% | 45.2% |

Read the middle row. **AI agent fraud gets approved more often than real
customers, passes authentication every single time, and never trips a speed
rule.** By every signal a normal system looks at, it looks *better than
normal*.

This is not a trick of our simulation. It follows from how the technology
works: the agent's token *is* the proof of identity, the permission is
genuinely signed, and the agent has a real history. Nothing is wrong with the
transaction. The only thing wrong is where the money went, and no field on a
payment message records that.

That single table is the strongest thing we have.

---

## 4. How the guard works

### Three guards, not one

Different frauds are visible in different ways, so we built three detectors:

| Guard | What it looks at | Catches |
|---|---|---|
| **A — Behaviour** | How you normally spend, against how you just spent | Stolen cards, testing |
| **B — Network** | How many accounts share a phone, how money flows between them | Mule rings |
| **C — Intent** | What you *told* the AI to buy, versus what it *actually* bought | AI agent fraud |

**Guard C is the new one, and it is the whole argument.** Guards A and B both
look for something odd. AI agent fraud has nothing odd in it. So we compare
the instruction against the purchase instead:

- You said "buy running shoes under ₹6,000"
- The agent spent ₹4,200 at a shoe shop → fine
- The agent spent ₹4,200 at a shoe shop that was poisoned to redirect
  payment → *nothing in the transaction says so*

Some checks are simple arithmetic: is it over the limit, is it the wrong kind
of shop, has the permission expired. Those work, and they caught 97% of the
authorisation-drift attack.

### Sending each payment to the right guard

Rather than one score for everything, we **route**. A payment goes to whichever
guard suits its type:

| Route | How we recognise it | Which guard leads |
|---|---|---|
| AI agent | An agent ID is present | C — intent |
| UPI push/collect | The rail | B — network |
| Card | The rail | A — behaviour |
| Recurring | The rail | C — intent |

The routing uses only information that is genuinely on the payment message. It
never uses "is this fraud" or "what kind of attack is this," because those are
answers, not clues.

**This measurably beats one big model.** Same data, same guards, same amount
of customer friction: routing recovered **1.52× more money**. And each route
gets its own friction budget, because you should not spend the same amount of
customer annoyance on a ₹200 grocery tap as on a delegated AI purchase.

The full grid, every cell reported including the embarrassing ones:

| Route | Guard A | Guard B | Guard C | Routed |
|---|---|---|---|---|
| AI agent | 0.332 | 0.199 | **0.655** | **0.673** |
| UPI push | 0.123 | **0.246** | — | **0.281** |
| Card | **0.457** | 0.020 | — | 0.426 |

Guard B is nearly useless on cards (0.020) and the best available on UPI
(0.246). Guard C dominates AI agents. Three populations, three different
winners — which is the whole justification for routing.

---

## 5. The mathematics, and why each piece is there

Six pieces. Each was chosen for a property, not because it sounded clever.

### 5.1 Scorecards, because the reasons come free

Each guard scores by adding up evidence:

> score = starting point + (evidence 1) + (evidence 2) + …

Each piece of evidence is a number saying "this makes fraud N times more
likely." Because the score is a **sum**, the biggest terms *are* the reasons.
Explainability is not bolted on — it falls out of the arithmetic:

```
p=0.973   agent payment, ₹15,537
    permission expired  +1.70
    over the limit      +1.70
    token-based entry   +1.67
```

This is also the standard credit-scorecard construction that every Indian bank
risk team already knows how to check. That familiarity is deliberate.

**The honest caveat:** adding evidence assumes each piece is independent, and
they are not. "New phone" and "new shop" go together. So we group correlated
evidence into blocks and count the strongest in each block fully, damping the
rest. We state this rather than hoping nobody asks.

### 5.2 Why we do not simply pick a threshold

The naive approach: flag anything above 80% risk.

The problem: a ₹200,000 transfer at 40% risk is worth far more attention than
a ₹200 transfer at 90%. If your budget for annoying customers is fixed, you
should spend it where the money is.

Working through the constraint properly gives:

> act when **value × risk** exceeds a line, not when **risk** exceeds a line

At a 2% friction budget this nearly **doubles** the money recovered — 41.0%
of fraud value against 8.7% for the naive version, at exactly the same
customer annoyance. Almost every real implementation thresholds on risk alone.

There is also a theorem (Neyman-Pearson) saying that at a fixed false-alarm
rate, thresholding a likelihood ratio is the *most powerful* test possible. Our
score is a likelihood ratio. So this is not one reasonable design among many —
given a fixed friction budget it is the optimal shape.

### 5.3 Holding the friction budget with a guarantee

The bank says: "annoy at most 2% of genuine customers."

We take genuine transactions, sort their scores, and set the cut-off at the
98th percentile. There is a proof that this holds the 2% promise for new
customers, with no assumptions about the score's distribution and no need for
a large sample.

So we can say *"you set the budget, we hold it, with a guarantee"* rather than
*"we hope."*

### 5.4 A drift alarm that needs no labels

This is the most original piece and it comes from putting two things together.

The guarantee above only holds if the future resembles the past. Our attack
search is a machine for **deliberately** making the future not resemble the
past.

So when the guarantee starts breaking — when we are annoying 4% of customers
instead of 2% — that is a signal the threat has shifted. **And it fires before
any label arrives.**

That matters enormously. Chargebacks take weeks. About 30% of fraud never gets
reported at all, and on UPI it is worse because there is no chargeback to
force the issue. A warning that needs no labels is the only kind that can
arrive in time.

### 5.5 Measuring whether the fake world is realistic

The obvious question: how do you know your fake data is any good?

Most teams say "it looks right." We measure it:

1. Take real data (IEEE-CIS, 590,540 real transactions)
2. **Split it in half and compare the halves to each other.** That difference
   is the *noise floor* — how different real data is from itself.
3. Compare our fake data to the real data, on the same measures
4. Divide

A score of 1.0 means our data differs from reality no more than reality
differs from itself. A score of 25 means twenty-five times worse.

Four things measured: gaps between payments, burst patterns, network shape,
how often speed rules fire.

**Our results**, against a competing generator built from the real data:

| Kind of measure | Row-based generator | Ours |
|---|---|---|
| **Sequence** (does the order look right) | 12.45 | **7.48** |
| Marginal (do the totals look right) | 12.95 | 7.51* |

*We lose on marginals, and that is fair: our comparison generator was built by
shuffling **real** timestamps and **real** amounts, so it has the true totals
by cheating. A trained model like CTGAN has to approximate them and would do
much worse. We built the strongest possible opponent deliberately.

Where we win is **sequence** — the order of events — which is exactly what the
proof says row-based generators cannot do.

### 5.6 Training with labels that arrive late

Real fraud detection has a problem people ignore: **you decide in
milliseconds, and you find out weeks later.**

We modelled it properly. Two streams:

- **Fast**: a crude rules filter flags about 2% of payments, an investigator
  reviews them within 6 hours. Small, quick, and biased by the filter itself.
- **Slow**: chargebacks, around 21 days later, and only for the ~70% of fraud
  anyone reports.

Result: at training time we had **974 labels** out of 35,000 payments. Under a
normal random split we would have had all 35,000 on day one.

There is deliberately **no random-split function anywhere in the code**, so
nobody reaches for one at 3am.

---

## 6. The strategy — why this wins

Most teams will submit: train CTGAN on a Kaggle dataset, generate fake fraud,
train a classifier on it, report 99% accuracy.

That number is meaningless, because you tested on data you made up. Judges
know this. Everyone will report 99%.

Our position is different:

1. **Our attacks come from documents**, with an honesty grade on each one, so
   the diversity claim is checkable.
2. **We can prove their generator cannot work** — the proof exists, and we
   measured it ourselves against the strongest possible version.
3. **We show an attack no normal system can see** — the 99.1% approval table.
4. **We measure ourselves on what escapes**, not what we catch.
5. **We report our own failures**, which changes how every other number reads.

The differentiation is not that our classifier is better. It is that we can
explain precisely why theirs is unmeasurable, and we have the numbers.

---

## 7. Where we actually stand

### Working

| | |
|---|---|
| Attack taxonomy | 94 vectors, 28 additions to MITRE F3, honesty-graded |
| Fake world | 58,743 transactions, 5 rails, calibrated against real data |
| Fidelity measurement | Real noise floor, sequence measures beat the competitor |
| Six attacks | Both kinds — visible and invisible |
| Three guards + routing | Complete grid, 1.52× improvement over one big model |
| Late-label training | Two streams, 974 labels, no random split |
| Speed | 0.048 ms per payment (industry reference: under 50 ms) |
| Honesty | Every field checked against what our position can actually see |

**11 of 16 planned figures exist and are usable.**

### The blocker

**Detection is weak in absolute terms.** About 20% of fraud caught at a 2%
friction budget. Honest — 974 training labels under realistic delay will do
that — but weak.

This blocks the most important figure. The loop is supposed to show escape
rate falling as the guard learns. We fixed three real bugs in it this session:

- Training memory filled with fraud until it was 40% fraud, and the model
  collapsed → fixed with a balanced memory
- The defender was being shown attacks before they happened → fixed
- The memory was too restrictive to learn from → fixed

After all three, escape rate still sits at 72–97%. And the reason is now
clear: **the guard is not strong enough for the curve to have room to fall.**
Round 2 has already seen round 1's attacks and still lets 72.6% through.

The loop machinery is correct. It is faithfully reporting a weak detector.

### Not built yet

| | |
|---|---|
| Web prototype | Required deliverable. Nothing started. Reads existing logs. |
| Word document | Required deliverable. Structure defined, figures exist. |
| GitHub repo | Required deliverable. Code exists, not published. |
| F10 transfer test | One script; data already loaded |
| F13 RBI control test | Parameter sweep; the attack already supports it |

### What I would do next

**Make the guard stronger.** Everything else is downstream of it — F1 needs it,
and the detection-efficacy score needs it. Three specific things, in order of
expected return:

1. **More labels.** 974 is very few. A wider alert filter, or a longer
   simulated history so more chargebacks land, would help most.
2. **Finer evidence bins.** Currently 8 buckets per feature. With more labels,
   more buckets means sharper evidence.
3. **The semantic half of Guard C.** Currently the intent check is arithmetic
   only. Comparing *what you asked for* against *what was bought* using
   meaning, not just category codes, is what catches the poisoned-listing
   attack — currently at 28%.

That third one is where an LLM genuinely earns its place in the system.
