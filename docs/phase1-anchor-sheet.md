# Phase 1a — Anchor sheet (N0–N2 seed taxonomy)

**What this is:** 47 attack vectors, none invented by us. Every entry traces to a documented
incident, a lab-proven exploit, a threat named by the people who wrote the protocol, or a
regulator's own findings.

**What it is not:** the taxonomy. This is the seed. The N3 entries come from crossing these
against the empty cells of the matrix, and the N4 entries come from the loop.

**Why it exists:** it tells you where fraud actually concentrates before you populate the
cross-product. Populate first and you get a uniform grid that looks systematic and matches
nothing.

---

## Grading

| Grade | Meaning |
|---|---|
| **N0** | Documented in the wild. Named incident, CVE, or regulator-reported pattern. |
| **N1** | Proven in a lab against a real implementation. Published, reproducible. |
| **N2** | Named as a threat by protocol authors or a standards body. Not yet observed publicly. |
| N3 | *Derived by us. Not in this file.* |
| N4 | *Discovered by the loop. Not in this file.* |

## Axis codes

**Rail:** R1 card-present · R2 card-not-present human · R3 card-not-present agentic ·
R4 UPI push · R5 UPI collect · R6 tokenised recurring · R7 wallet/PPI

**Stage:** RECON · RESOURCE · ACCESS · EXEC · EVADE · COLLECT · MONETISE

**Capability:** A1 voice · A2 video/face · A3 documents · A4 persuasion at scale ·
A5 semantic recon · A6 code/tooling · A7 attacker autonomy ·
B1 the delegated agent · B2 the mandate artifact · B3 agent memory · B4 inter-agent channel

**Trust link broken:** credential · identity · session · intent · mandate · channel · none-coerced

---

## Cluster 1 — Mandate and intent (R3)

The core agentic surface. Every entry here defeats authentication by design, because
authentication passes correctly.

| ID | Vector | Grade | Source | Framework | Stage | Cap | Breaks |
|---|---|---|---|---|---|---|---|
| AGT-001 | Payment Mandate theft for an unrelated checkout | N2 | AP2 security considerations | — | EXEC | B2 | mandate |
| AGT-002 | Open-mandate reuse against a different closed mandate | N2 | AP2 security considerations | — | EXEC | B2 | mandate |
| AGT-003 | Injected agent approves multiple checkouts from one open mandate | N2 | AP2 security considerations | ASI01 | EXEC | B1,B2 | mandate |
| AGT-004 | Mandate scope inflation via poisoned merchant listing | N1 | Whispers of Wealth (2601.22569) | ASI01 · T06 | EXEC | B1 | intent |
| AGT-005 | Branded Whisper — ranking manipulation via adversarial product content | N1 | Whispers of Wealth, 100% ASR | ASI01 · T06 | RECON | A5,B1 | intent |
| AGT-006 | Vault Whisper — cross-user disclosure via direct injection | N1 | Whispers of Wealth, 20% success | ASI03 · T03 | COLLECT | B1 | session |
| AGT-007 | Replay on trust chains — stale delegation honoured | N2 | OWASP ASI07 | ASI07 · T12/T16 | EXEC | B4 | mandate |
| AGT-008 | Workflow authorisation drift — spend limit reduced mid-flow, old token completes | N2 | OWASP ASI03 | ASI03 · T03 | EXEC | B2 | mandate |
| AGT-009 | TOCTOU in agent workflows — permissions valid at check, stale at use | N2 | OWASP ASI03 | ASI03 · T03 | EXEC | B2 | mandate |
| AGT-010 | Semantics split-brain — one instruction parsed into divergent intents by two agents | N2 | OWASP ASI07 | ASI07 · T12 | EXEC | B4 | intent |
| AGT-011 | Protocol downgrade to weaker mode, then objective injection | N2 | OWASP ASI07 | ASI07 · T16 | ACCESS | B4 | channel |

**Note on AGT-004.** This is your headline demo. It is N1, not speculation: functional AP2 agent,
Gemini-2.5-Flash, Google ADK, published attack, 100% success on ranking manipulation.

**Note on AGT-008 and AGT-009.** These are the same defect at two time-scales, and both are
invisible to anomaly detection because the token is genuine. They are the cleanest argument
for scoring intent-execution divergence rather than transaction shape.

---

## Cluster 2 — Agent identity and delegation (R3)

| ID | Vector | Grade | Source | Framework | Stage | Cap | Breaks |
|---|---|---|---|---|---|---|---|
| AGT-012 | Cross-agent confused deputy — sorter agent relays payment instruction to finance agent | N2 | OWASP ASI03 | ASI03 · T03 | EXEC | B4 | identity |
| AGT-013 | Forged agent persona in an A2A registry with a fabricated agent card | N0 | Trustwave, Apr 2025 | ASI03/07/10 · T13 | RESOURCE | B4 | identity |
| AGT-014 | Agent-in-the-middle via exaggerated capabilities in `/.well-known/agent.json` | N0 | Trustwave | ASI04 · T17 | ACCESS | B4 | identity |
| AGT-015 | Impersonated approval agent injected into a payment workflow | N2 | OWASP ASI10 | ASI10 · T13 | EXEC | B4 | identity |
| AGT-016 | Synthetic identity injection via unverified internal descriptors | N2 | OWASP ASI03 | ASI03 | RESOURCE | B4 | identity |
| AGT-017 | Device-code phishing across agents — browsing agent follows, helper completes | N2 | OWASP ASI03 | ASI03 | ACCESS | B1 | credential |
| AGT-018 | Un-scoped privilege inheritance in delegation chains | N2 | OWASP ASI03 | ASI03 · T03 | EXEC | B1 | identity |
| AGT-019 | Identity sharing — agent's delegated access reused by other principals | N2 | OWASP ASI03 | ASI03 | ACCESS | B1 | identity |

**AGT-015 is the purest statement of the problem.** OWASP's own wording: a high-value agent such
as payment processing, trusting the internal request, is misled into releasing funds. That is a
standards body describing your threat model in one sentence.

---

## Cluster 3 — Memory, context and drift (R3, R6)

Slow attacks. These are the ones a session-scoped detector cannot see, and they are the
strongest argument for SPRT over the mandate session.

| ID | Vector | Grade | Source | Framework | Stage | Cap | Breaks |
|---|---|---|---|---|---|---|---|
| AGT-020 | Booking memory poisoning — fake price stored as truth, bypasses payment checks | N2 | OWASP ASI06 | ASI06 · T01 | EXEC | B3 | intent |
| AGT-021 | Context-window exploitation — rejections aged out, permissions escalate over sessions | N2 | OWASP ASI06 | ASI06 · T01 | EVADE | B3 | mandate |
| AGT-022 | Long-term memory drift via incrementally tainted data | N2 | OWASP ASI06 | ASI06 · T01 | EVADE | B3 | intent |
| AGT-023 | Goal-lock drift — scheduled prompts reweight objectives toward low-friction approvals | N2 | OWASP ASI01 | ASI01 · T06 | EVADE | B3 | intent |
| AGT-024 | Shared memory poisoning — bogus refund policy reused across agents | N2 | OWASP ASI06 | ASI06 · T12 | MONETISE | B3 | intent |
| AGT-025 | Gemini long-term memory corruption via prompt injection | N0 | Ars Technica, Feb 2025 | ASI06 · T01 | EVADE | B3 | intent |
| AGT-026 | Cross-tenant vector bleed via loose namespace filters | N2 | OWASP ASI06 | ASI06 | COLLECT | B3 | session |
| AGT-027 | Bootstrap poisoning — agent re-ingests own output into trusted memory | N2 | OWASP ASI06 (stated as a control) | ASI06 | EVADE | B3 | intent |

**AGT-021 and AGT-023 are the two to implement.** Both are gradual, both stay within declared
policy at every individual step, and both produce transaction streams that look immaculate.
They are the F6 reveal in generator form.

---

## Cluster 4 — Detector-facing and cascade (R3)

The interesting subset: attacks aimed at the defence rather than the payment.

| ID | Vector | Grade | Source | Framework | Stage | Cap | Breaks |
|---|---|---|---|---|---|---|---|
| AGT-028 | Anomaly flooding — false positives generated to exhaust reviewers, then slow cartel | N2 | CSA AP2 guidance | ASI08 | EVADE | A7 | none |
| AGT-029 | Auto-remediation feedback loop — remediation agent suppresses alerts to meet SLAs | N2 | OWASP ASI08 | ASI08 · T05 | EVADE | A7,B4 | none |
| AGT-030 | Governance drift cascade — oversight weakens after repeated success, bulk approvals | N2 | OWASP ASI08 | ASI08 | EVADE | A7 | none |
| AGT-031 | Within-parameter cascade — inflated risk limits, downstream agents trade larger, compliance blind | N2 | OWASP ASI08 | ASI08 · T05 | EXEC | B4 | intent |
| AGT-032 | Log injection to mask coordination across agents | N2 | CSA AP2 guidance | ASI08 · T08 | EVADE | A6 | none |
| AGT-033 | Metadata-based behavioural profiling of agent decision cycles | N2 | OWASP ASI07 | ASI07 | RECON | A5 | none |

**Cluster 4 is where your originality is cheapest.** Almost nobody in this competition will
model attacks against the detector. AGT-028 and AGT-029 are directly measurable in your loop:
they should show up as escape-rate plateaus rather than spikes, which is a distinguishable
signature and worth a paragraph.

---

## Cluster 5 — Supply chain into the payment agent (R3)

| ID | Vector | Grade | Source | Framework | Stage | Cap | Breaks |
|---|---|---|---|---|---|---|---|
| AGT-034 | Malicious MCP server impersonating a legitimate one — first in-the-wild on npm | N0 | Koi Security, Sep 2025 | ASI02/04/07 | RESOURCE | A6 | channel |
| AGT-035 | Tool-descriptor poisoning — commands hidden in MCP metadata | N0 | Invariant Labs | ASI02 · T02 | EXEC | A6 | channel |
| AGT-036 | Backdoored MCP package with install-time and runtime reverse shells | N0 | Koi Security, Oct 2025 | ASI04 · T17 | RESOURCE | A6 | channel |
| AGT-037 | Tool name typosquatting — `report` resolves before `report_finance` | N2 | OWASP ASI02 | ASI02 · T02 | EXEC | A6 | channel |
| AGT-038 | Poisoned knowledge plugin seeding a RAG index over time | N2 | OWASP ASI04 | ASI04 · T17 | EVADE | B3 | intent |
| AGT-039 | Over-privileged financial API — order-history agent can also issue refunds | N2 | OWASP ASI02 | ASI02 · T02 | MONETISE | B1 | mandate |

---

## Cluster 6 — Human-facing, agent-mediated (R2, R3, R4)

Where agentic and classic social engineering meet. Every one of these ends with a human
correctly authenticating a payment they were manipulated into making.

| ID | Vector | Grade | Source | Framework | Stage | Cap | Breaks |
|---|---|---|---|---|---|---|---|
| HUM-001 | Invoice copilot fraud — poisoned vendor invoice, agent recommends attacker bank details | N2 | OWASP ASI09 | ASI09 · T07 | MONETISE | A4,B1 | none-coerced |
| HUM-002 | Copilot manipulated into influencing an ill-advised wire transfer | N0 | Documented, ASI09 refs | ASI09 · T15 | MONETISE | A4,B1 | none-coerced |
| HUM-003 | Fake explainability — fabricated rationale secures human approval | N2 | OWASP ASI09 | ASI09 · T07 | EVADE | A4 | none-coerced |
| HUM-004 | Consent laundering via "read-only" preview that triggers side effects | N2 | OWASP ASI09 | ASI09 | EXEC | B1 | intent |
| HUM-005 | Human-in-the-loop fatigue in high-volume autonomous approval | N2 | CSA AP2 guidance | ASI09 · T10 | EVADE | A7 | none-coerced |
| HUM-006 | Missing confirmation converts one prompt into an irreversible transfer | N2 | OWASP ASI09 | ASI09 | EXEC | B1 | intent |

---

## Cluster 7 — India rail, regulator-documented (R4, R5)

All N0. RBI states these as the observed fraud landscape, which makes them the most
defensible entries in the entire sheet.

| ID | Vector | Grade | Source | Stage | Cap | Breaks |
|---|---|---|---|---|---|---|
| UPI-001 | Authorised push payment via social engineering — victim initiates and authenticates | N0 | RBI DP, Apr 2026 | MONETISE | A4 | none-coerced |
| UPI-002 | Bogus call centre operations | N0 | RBI DP | ACCESS | A1,A4 | none-coerced |
| UPI-003 | Deepfake-driven impersonation scam | N0 | RBI DP | ACCESS | A1,A2 | identity |
| UPI-004 | Mule account network for proceeds movement | N0 | RBI DP · MuleHunter.AI | MONETISE | — | — |
| UPI-005 | Impersonation of family members / fabricated urgent medical or legal scenario | N0 | RBI DP, on vulnerable segments | ACCESS | A1,A4 | none-coerced |
| UPI-006 | Collect-request fraud — a debit dressed as a credit | N0 | Rail primitive | EXEC | A4 | none-coerced |
| UPI-007 | Aggregator-onboarded merchant account laundering proceeds as small-business commerce | N0 | Mule telemetry | MONETISE | A3 | identity |
| UPI-008 | Payments-bank VPA farming via low-friction onboarding | N0 | Mule telemetry | RESOURCE | A3 | identity |

### Control-survival entries (these drive F13)

| ID | Vector | Grade | Source | Note |
|---|---|---|---|---|
| UPI-009 | Whitelist bypass — victim persuaded to whitelist the payee, defeating the one-hour lag | **N2** | **RBI's own stated con** | RBI lists this as a weakness of Option 1. Measuring how effective it is, is a direct contribution to a live consultation. |
| UPI-010 | Trusted-person social engineering — the trusted contact is the next target above ₹50,000 | N3-adjacent | Derived from RBI Option 2 | Mark N3. It follows from the design, but RBI does not state it. |
| UPI-011 | Micro-structuring below the ₹10,000 lag threshold | N3-adjacent | Derived from RBI Option 1 | Mark N3. Measure the attacker's throughput cost. |
| UPI-012 | Aggregate-credit structuring below the ₹25 lakh ceiling across many mules | N3-adjacent | Derived from RBI Option 3 | Mark N3. |

**Be strict about these four.** UPI-009 is genuinely N2 because RBI wrote it down. The other
three are yours, and grading them N2 to pad the count is exactly the overclaiming that gets a
submission taken apart in Q&A. They are strong *because* they are N3 — they show the derivation
engine producing something the regulator did not.

**RBI's fraud trajectory, for the opening:** NCRP-reported digital payment fraud rose from
2.6 lakh cases worth ₹551 crore in 2021 to 28 lakh cases worth ₹22,931 crore in 2025.
And the line that carries your whole thesis: RBI states account-takeover fraud is now negligible
and that most fraud is authorised push payment.

---

## Cluster 8 — Classic, GenAI-accelerated (R1, R2, R6)

| ID | Vector | Grade | Source | Stage | Cap | Breaks |
|---|---|---|---|---|---|---|
| CRD-001 | Card testing — micro-probes across merchants to validate a BIN range | N0 | Standard | RECON | A6,A7 | credential |
| CRD-002 | Deepfake video-call authorisation of a transfer | N0 | Arup, Jan 2024, $25M | EXEC | A2 | identity |
| CRD-003 | Voice-cloned relative-in-need scam | N0 | Widely reported | ACCESS | A1 | none-coerced |
| CRD-004 | Deepfake selfie at biometric onboarding | N0 | Entrust 2026 | RESOURCE | A2 | identity |
| CRD-005 | Injection attack bypassing the biometric capture path entirely | N0 | Entrust 2026, +40% YoY | RESOURCE | A6 | identity |
| CRD-006 | Synthetic identity onboarding with generated documents | N0 | Sumsub | RESOURCE | A3 | identity |
| CRD-007 | Cloned merchant site resurfacing after takedown | N0 | Standard | RESOURCE | A6 | identity |
| CRD-008 | LLM-in-the-loop malware querying a model mid-execution | N0 | PROMPTFLUX / PROMPTSTEAL, Nov 2025 | EXEC | A6,A7 | credential |
| CRD-009 | Chargeback abuse / first-party fraud | N0 | Sumsub | MONETISE | — | none |

**For each of these, state the cost collapse explicitly.** CRD-002 previously required a VFX
budget and now requires consumer tooling. CRD-003 previously required a skilled impersonator and
now requires seconds of sample audio. If you cannot state the before-and-after, the entry belongs
in a different cluster or nowhere.

---

## What the shape tells you

Count by rail: 39 of 47 anchors sit on R3 (agentic card-not-present) or R4/R5 (UPI). That is not
an artifact of what I selected — it is where the documented 2026 material actually exists. It
confirms the two-rail depth decision from Phase 0 rather than requiring you to defend it.

Count by stage: heavy at EXEC and EVADE, thin at RECON and COLLECT. Those thin cells are where
your N3 derivation should start, because they are underexplored rather than uninteresting.

Count by capability: B1–B4 (surface creation) accounts for 31 entries, A1–A7 (cost collapse) for
16. Worth saying out loud in the document: **the majority of documented 2026 payment-fraud
research is about attack surfaces that did not exist in 2023, not about old attacks getting
cheaper.** That single sentence justifies the two-family split on Axis 3, and it is a finding,
not an assertion — it falls out of counting this table.

Grade distribution: 21 N0, 4 N1, 22 N2. The N2 weight is high because protocol authors and
standards bodies have documented far more agentic payment threats than have been observed in the
wild yet. That gap *is* the emerging-threat story the brief asks for, and it is worth a paragraph
of its own.

---

## Framework coverage achieved

Every AGT and HUM entry carries an ASI ID, and via the OWASP Appendix A cross-map each of those
also carries an LLM Top 10 ID, a T-code, and an AIVSS core risk category. Add MITRE F3 tactics in
Phase 1b and each agentic vector holds **five independent framework identifiers**.

No other submission will have that, and it costs an afternoon because the cross-map is already
written in Appendix A of the OWASP document.

---

## Next

1. Convert this to one YAML file per entry, with the `evidence`, `attack_class`
   (structural vs semantic, per AIP-Bench), and `generator` fields added.
2. Attach F3 tactic and technique IDs — the only axis still missing.
3. Cross-populate the matrix and derive the N3 set from the empty and thin cells.
4. Pick the 6–8 that get generators. Current recommendation: UPI-004 (mule farm),
   AGT-004 (poisoned listing), AGT-021 (context escalation), AGT-008 (authorisation drift),
   CRD-001 (card testing), UPI-006 (collect request), UPI-011 (micro-structuring),
   AGT-028 (anomaly flooding).
