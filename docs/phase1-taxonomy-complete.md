# Chakra taxonomy — Phase 1 complete

*Generated from `taxonomy_build.py`. Every number below is computed from the data.*

## Headline counts

- **94 vectors total**
- **64 anchors** (N0 25 · N1 3 · N2 36) — none invented by us
- **30 derived** by crossing anchors against empty matrix cells
- **0 at N4** so far — the loop has not run yet

- 23 marked `implemented` (a generator will be built), 71 `taxonomy_only`

## The matrix — F3 tactic x rail

Counts are technique-rail pairs. A vector spanning two tactics and two rails appears four times, which follows F3's own multi-tactic convention.

| Tactic | R1 | R2 | R3 | R4 | R5 | R6 | R7 | **Σ** |
|---|---|---|---|---|---|---|---|---|
| **TA0043** Reconnaissance | · | · | 8 | 2 | 1 | · | · | **11** |
| **TA0042** Resource Dev | · | 5 | 10 | 2 | · | · | · | **17** |
| **TA0001** Initial Access | · | 2 | 7 | 4 | 1 | · | · | **14** |
| **FA0001** Positioning | · | 2 | 7 | 2 | · | 2 | 1 | **14** |
| **TA0002** Execution | · | 4 | 19 | 1 | 1 | 2 | · | **27** |
| **TA0005** Stealth | · | 4 | 18 | 3 | · | 2 | 1 | **28** |
| **TA0112** Defense Impairment | · | · | 9 | 6 | · | 1 | 2 | **18** |
| **FA0002** Monetization | · | 3 | 6 | 5 | · | · | 1 | **15** |
| **Σ** | **0** | **20** | **84** | **25** | **3** | **7** | **5** | **144** |

Rail key: **R1** Card present · **R2** CNP human · **R3** CNP agentic · **R4** UPI push · **R5** UPI collect · **R6** Tokenised recurring · **R7** Wallet / PPI

### The 23 cells that are still empty

Empty cells are a finding, not a gap. Grouped by why:

- **R1 Card present** — Reconnaissance, Resource Dev, Initial Access, Positioning, Execution, Stealth, Defense Impairment, Monetization
- **R2 CNP human** — Reconnaissance, Defense Impairment
- **R5 UPI collect** — Resource Dev, Positioning, Stealth, Defense Impairment, Monetization
- **R6 Tokenised recurring** — Reconnaissance, Resource Dev, Initial Access, Monetization
- **R7 Wallet / PPI** — Reconnaissance, Resource Dev, Initial Access, Execution

**R1 card-present is empty throughout.** That is the single clearest structural result in the taxonomy: GenAI barely touches card-present fraud because the attack requires physical presence at a terminal. No capability on our Axis 3 collapses that cost. Say this explicitly — a team that reports an empty region and explains the mechanism reads very differently from one that quietly pads it.

## Capability axis — the two-family split

| Code | Capability | Vectors |
|---|---|---|
| A1 | Synthetic voice, interactive | 6 |
| A2 | Synthetic face/video, interactive | 3 |
| A3 | Synthetic documents & identity | 4 |
| A4 | Personalised persuasion at scale | 12 |
| A5 | Semantic recon & targeting | 11 |
| A6 | Code generation & tooling | 11 |
| A7 | Attacker-side execution autonomy | 17 |
| B1 | The delegated agent | 17 |
| B2 | The mandate / intent artifact | 14 |
| B3 | Agent memory & retrieval context | 10 |
| B4 | Inter-agent channel | 11 |

| Set | A — cost collapse | B — surface creation |
|---|---|---|
| Anchors (N0–N2) | 36 | 36 |
| Derived (N3) | 28 | 16 |
| **All** | **64** | **52** |

**The two sets behave differently, and that is the finding.** Among the anchors — what the field has actually documented — the two families are dead even at 36:36. Among our derived entries, cost collapse leads 28:16.

The reading: the documented record splits evenly, so neither family can be dropped. But our derivation, working outward from those anchors into the empty cells, lands disproportionately on cost collapse — specifically on A5 semantic targeting and A7 autonomy. The empty cells are mostly reconnaissance, positioning and evasion, and those are the stages where an old technique becomes newly viable once it can be run at machine scale: directory enumeration, structuring under a threshold, reputation farming, rail-hopping.

So the honest framing for the write-up is that published research favours novel surfaces because novel surfaces are what gets published, while systematic derivation surfaces the industrialisation of old techniques. A taxonomy built only from the literature would miss the second half entirely.

## What breaks, by trust link

| Link broken | Vectors |
|---|---|
| identity | 21 |
| none | 19 |
| intent | 15 |
| none-coerced | 14 |
| mandate | 13 |
| channel | 5 |
| credential | 4 |
| session | 3 |

**42 vectors defeat authentication by design** (`mandate`, `intent`, `none-coerced`) against **28 that break it** (`credential`, `session`, `identity`) — a 42:28 ratio.

In the first group every authentication factor is presented correctly by the legitimate party. A passkey, a PIN, a signed mandate: all valid. There is no anomaly to detect because nothing anomalous happened. That is the single sentence the whole defence architecture answers, and RBI states it independently — account-takeover fraud is now negligible and most fraud is authorised push payment.

It is also the direct justification for a third detection head. A behavioural model and a graph model are both anomaly detectors, so between them they address the smaller group. The larger group needs a detector that compares authorised intent against executed action, which is what Head C is.

## F3 extension register

**28 proposed extensions** covering 69 vectors, against **31 existing F3 techniques** reused.

F3 v1.1 contains 74 top-level techniques and 49 sub-techniques across 8 tactics. A keyword scan of all 123 returns zero hits for AI, LLM, model, deepfake, synthetic media, voice cloning, generative, autonomous or mandate. **F3 has no agentic or GenAI coverage at all**, so every extension below is genuinely new rather than a relabelling.

| Extension ID | Proposed name | Vectors | F3 tactics reached |
|---|---|---|---|
| `F3X-1001` | Agent Goal Hijack for Payment Redirection | 2 | TA0002 |
| `F3X-1002` | Mandate Replay and Scope Reuse | 3 | TA0002, TA0005 |
| `F3X-1003` | Approval Threshold Drift | 2 | TA0002, TA0005, TA0112 |
| `F3X-1004` | Agent Identity Forgery | 4 | FA0001, TA0001, TA0042 |
| `F3X-1005` | Cross-Agent Confused Deputy | 2 | TA0001, TA0002 |
| `F3X-1006` | Agent Memory Poisoning | 7 | FA0001, FA0002, TA0002, TA0005 |
| `F3X-1007` | Detector Saturation by Autonomous Agents | 4 | TA0005, TA0112 |
| `F3X-1008` | Agent Retrieval Poisoning | 3 | TA0042, TA0043 |
| `F3X-1009` | Cross-Principal Context Disclosure | 2 | TA0043 |
| `F3X-1010` | Authorisation Staleness Exploitation | 2 | TA0002, TA0005 |
| `F3X-1011` | Inter-Agent Semantic Divergence | 1 | TA0002 |
| `F3X-1012` | Agent Protocol Downgrade | 1 | TA0001, TA0005 |
| `F3X-1013` | Delegated Privilege Overreach | 3 | FA0002, TA0001, TA0002 |
| `F3X-1014` | Agent Behavioural Profiling | 1 | TA0043 |
| `F3X-1015` | Tool Interface Poisoning | 3 | TA0001, TA0002, TA0042 |
| `F3X-1016` | Agent-Mediated Human Manipulation | 4 | TA0002, TA0005 |
| `F3X-1017` | Collect Request Inversion | 1 | TA0002 |
| `F3X-1018` | Consumer Safeguard Circumvention | 4 | TA0112 |
| `F3X-1019` | Model Tier Fingerprinting | 1 | TA0043 |
| `F3X-1020` | Agent Policy Enumeration | 3 | TA0043 |
| `F3X-1021` | Agent Reputation Positioning | 3 | FA0001, TA0005 |
| `F3X-1022` | In-Mandate Stored Value Conversion | 1 | FA0002 |
| `F3X-1023` | Intent Detector Evasion | 3 | TA0005, TA0112 |
| `F3X-1024` | Instant Rail Directory Enumeration | 2 | TA0043 |
| `F3X-1025` | Recurring Mandate Abuse | 3 | FA0001, TA0002, TA0005, TA0112 |
| `F3X-1026` | Prepaid Instrument Chaining | 2 | FA0001, FA0002, TA0005, TA0112 |
| `F3X-1027` | Agent Framework Laundering | 1 | FA0001, TA0005 |
| `F3X-1028` | Cross-Rail Visibility Evasion | 1 | FA0002, TA0005 |

### Existing F3 techniques reused

`F1001`(1), `F1005.003`(1), `F1005.006`(1), `F1009`(3), `F1009.002`(1), `F1012`(2), `F1017`(1), `F1020.001`(3), `F1020.002`(1), `F1021`(2), `F1023`(1), `F1024`(2), `F1025.001`(1), `F1025.002`(1), `F1027`(1), `F1028`(2), `F1031`(4), `F1032`(1), `F1036`(1), `F1039`(1), `F1040.001`(1), `F1042`(1), `F1045`(3), `F1046`(1), `T1070`(1), `T1195`(3), `T1550.001`(1), `T1557`(1), `T1583.001`(1), `T1585`(2), `T1608.006`(1)

## Generator shortlist

Vectors marked `implemented` get a plugin. Everything else is taxonomy coverage, declared as such.

| ID | Vector | Grade | Rails |
|---|---|---|---|
| AGT-004 | Mandate scope inflation via poisoned merchant listing | N1 | R3 |
| AGT-008 | Workflow authorisation drift — old token completes after limit cut | N2 | R3, R6 |
| AGT-021 | Context-window exploitation — permissions escalate across sessions | N2 | R3 |
| AGT-028 | Anomaly flooding to exhaust reviewers, then slow cartel | N2 | R3 |
| UPI-001 | APP fraud — victim initiates and authenticates under deception | N0 | R4 |
| UPI-004 | Mule account network for proceeds movement | N0 | R4 |
| UPI-006 | Collect-request fraud — a debit dressed as a credit | N0 | R5 |
| UPI-009 | Whitelist bypass — victim persuaded to whitelist the payee | N2 | R4 |
| CRD-001 | Card testing — micro-probes to validate a BIN range | N0 | R2 |
| DRV-001 | Model-tier fingerprinting of a payment agent | N3 | R3 |
| DRV-002 | Mandate policy enumeration via boundary probing | N3 | R3 |
| DRV-008 | Mule-controlled agent holding a legitimately delegated token | N3 | R3 |
| DRV-009 | Dormant agent aging — clean history built before compromise | N3 | R3 |
| DRV-013 | Intent-schema ambiguity exploitation | N3 | R3 |
| DRV-016 | VPA liveness enumeration abusing beneficiary name look-up | N3 | R4, R5 |
| DRV-017 | Vulnerable-segment disclosure via the trusted-person requirement | N3 | R4 |
| DRV-018 | Trusted-person social engineering above Rs 50,000 | N3 | R4 |
| DRV-019 | Micro-structuring below the Rs 10,000 lag threshold | N3 | R4 |
| DRV-020 | Aggregate-credit structuring below the Rs 25 lakh ceiling | N3 | R4 |
| DRV-021 | Cancellation-window exhaustion — sustained contact through the lag hour | N3 | R4 |
| DRV-023 | Recurring mandate as control evasion | N3 | R6 |
| DRV-028 | Agent-assisted card testing under a legitimate agent framework | N3 | R2, R3 |
| DRV-029 | Rail-hopping to defeat position-limited detection | N3 | R2, R4 |

## Full register

| ID | Vector | Grade | F3 / F3X | Tactics | Rails | Caps | Breaks |
|---|---|---|---|---|---|---|---|
| AGT-001 | Payment Mandate theft for an unrelated checkout | N2 | F3X-1002 | TA0002 | R3 | B2 | mandate |
| AGT-002 | Open-mandate reuse against a different closed mandate | N2 | F3X-1002 | TA0002, TA0005 | R3 | B2 | mandate |
| AGT-003 | Injected agent approves multiple checkouts from one open mandate | N2 | F3X-1001 | TA0002 | R3 | B1, B2 | mandate |
| AGT-004 | Mandate scope inflation via poisoned merchant listing | N1 | F3X-1001 | TA0002 | R3 | B1 | intent |
| AGT-005 | Branded Whisper — agent ranking manipulation | N1 | F3X-1008 | TA0043, TA0042 | R3 | A5, B1 | intent |
| AGT-006 | Vault Whisper — cross-user disclosure via direct injection | N1 | F3X-1009 | TA0043 | R3 | B1 | session |
| AGT-007 | Replay on trust chains — stale delegation honoured | N2 | F3X-1002 | TA0002 | R3 | B4 | mandate |
| AGT-008 | Workflow authorisation drift — old token completes after limit cut | N2 | F1005.003, F3X-1010 | TA0002, TA0005 | R3, R6 | B2 | mandate |
| AGT-009 | TOCTOU in agent workflows | N2 | F3X-1010 | TA0002 | R3 | B2 | mandate |
| AGT-010 | Semantics split-brain across two agents | N2 | F3X-1011 | TA0002 | R3 | B4 | intent |
| AGT-011 | Protocol downgrade then objective injection | N2 | F3X-1012 | TA0001, TA0005 | R3 | B4 | channel |
| AGT-012 | Cross-agent confused deputy relaying a payment instruction | N2 | F3X-1005 | TA0001, TA0002 | R3 | B4 | identity |
| AGT-013 | Forged agent persona in an A2A registry | N0 | F3X-1004 | TA0042, TA0001 | R3 | B4 | identity |
| AGT-014 | Agent-in-the-middle via exaggerated agent card | N0 | F3X-1004, T1557 | TA0001, FA0001 | R3 | B4 | identity |
| AGT-015 | Impersonated approval agent injected into a payment workflow | N2 | F3X-1005 | TA0002 | R3 | B4 | identity |
| AGT-016 | Synthetic identity injection via unverified descriptors | N2 | F3X-1004 | TA0042 | R3 | B4 | identity |
| AGT-017 | Device-code phishing across agents | N2 | T1550.001 | TA0001 | R3 | B1 | credential |
| AGT-018 | Un-scoped privilege inheritance in delegation chains | N2 | F3X-1013 | TA0002 | R3 | B1 | identity |
| AGT-019 | Identity sharing — delegated access reused by other principals | N2 | F3X-1013 | TA0001 | R3 | B1 | identity |
| AGT-020 | Booking memory poisoning bypasses payment checks | N2 | F3X-1006 | FA0001, TA0002 | R3 | B3 | intent |
| AGT-021 | Context-window exploitation — permissions escalate across sessions | N2 | F3X-1006 | FA0001, TA0005 | R3 | B3 | mandate |
| AGT-022 | Long-term memory drift via incrementally tainted data | N2 | F3X-1006 | TA0005 | R3 | B3 | intent |
| AGT-023 | Goal-lock drift — scheduled prompts reweight toward low-friction approval | N2 | F3X-1003 | TA0005, TA0112 | R3 | B3 | intent |
| AGT-024 | Shared memory poisoning — bogus refund policy reused | N2 | F3X-1006 | FA0002 | R3 | B3 | intent |
| AGT-025 | Gemini long-term memory corruption via prompt injection | N0 | F3X-1006 | TA0005 | R3 | B3 | intent |
| AGT-026 | Cross-tenant vector bleed via loose namespace filters | N2 | F3X-1009 | TA0043 | R3 | B3 | session |
| AGT-027 | Bootstrap poisoning — agent re-ingests own output as trusted | N2 | F3X-1006 | TA0005 | R3 | B3 | intent |
| AGT-028 | Anomaly flooding to exhaust reviewers, then slow cartel | N2 | F3X-1007 | TA0112 | R3 | A7 | none |
| AGT-029 | Auto-remediation loop suppresses alerts to meet SLAs | N2 | F3X-1007 | TA0112 | R3 | A7, B4 | none |
| AGT-030 | Governance drift cascade — bulk approval after repeated success | N2 | F3X-1007 | TA0112, TA0005 | R3 | A7 | none |
| AGT-031 | Within-parameter cascade — inflated limits, compliance blind | N2 | F3X-1003 | TA0002, TA0005 | R3 | B4 | intent |
| AGT-032 | Log injection to mask cross-agent coordination | N2 | T1070 | TA0005, TA0112 | R3 | A6 | none |
| AGT-033 | Metadata profiling of agent decision cycles | N2 | F3X-1014 | TA0043 | R3 | A5 | none |
| AGT-034 | Malicious MCP server impersonating a legitimate one | N0 | T1195, F3X-1015 | TA0042, TA0001 | R3 | A6 | channel |
| AGT-035 | Tool-descriptor poisoning via MCP metadata | N0 | F3X-1015 | TA0002 | R3 | A6 | channel |
| AGT-036 | Backdoored MCP package, install-time and runtime shells | N0 | T1195 | TA0042 | R3 | A6 | channel |
| AGT-037 | Tool name typosquatting resolves before the real tool | N2 | F3X-1015 | TA0042, TA0002 | R3 | A6 | channel |
| AGT-038 | Poisoned knowledge plugin seeding a RAG index over time | N2 | F3X-1006 | TA0005 | R3 | B3 | intent |
| AGT-039 | Over-privileged financial API — order agent can also refund | N2 | F3X-1013 | FA0002 | R3 | B1 | mandate |
| HUM-001 | Invoice copilot fraud — poisoned invoice, attacker bank details | N2 | F1036, F1005.006 | TA0042, FA0002 | R2, R3 | A4, B1 | none-coerced |
| HUM-002 | Copilot manipulated into influencing a wire transfer | N0 | F3X-1016 | TA0002 | R2, R3 | A4, B1 | none-coerced |
| HUM-003 | Fake explainability secures human approval | N2 | F3X-1016 | TA0005 | R3 | A4 | none-coerced |
| HUM-004 | Consent laundering via read-only preview with side effects | N2 | F3X-1016 | TA0002 | R3 | B1 | intent |
| HUM-005 | Human-in-the-loop fatigue at autonomous approval volume | N2 | F3X-1007 | TA0112 | R3 | A7 | none-coerced |
| HUM-006 | Missing confirmation turns one prompt into an irreversible transfer | N2 | F3X-1016 | TA0002 | R3 | B1 | intent |
| UPI-001 | APP fraud — victim initiates and authenticates under deception | N0 | F1025.001, F1025.002 | TA0002, FA0002 | R4 | A4 | none-coerced |
| UPI-002 | Bogus call centre operations | N0 | F1032 | TA0001 | R4, R5 | A1, A4 | none-coerced |
| UPI-003 | Deepfake-driven impersonation scam | N0 | F1031 | TA0001, TA0005 | R4 | A1, A2 | identity |
| UPI-004 | Mule account network for proceeds movement | N0 | F1009, F1009.002 | FA0001, FA0002 | R4 | A3 | identity |
| UPI-005 | Impersonation of family, fabricated medical or legal urgency | N0 | F1031 | TA0001 | R4 | A1, A4 | none-coerced |
| UPI-006 | Collect-request fraud — a debit dressed as a credit | N0 | F3X-1017 | TA0002 | R5 | A4 | none-coerced |
| UPI-007 | Aggregator-onboarded merchant laundering as small-business commerce | N0 | F1021 | TA0042, FA0002 | R4 | A3 | identity |
| UPI-008 | Payments-bank VPA farming via low-friction onboarding | N0 | T1585, F1020.001 | TA0042, FA0001 | R4 | A3 | identity |
| UPI-009 | Whitelist bypass — victim persuaded to whitelist the payee | N2 | F3X-1018 | TA0112 | R4 | A4 | none-coerced |
| CRD-001 | Card testing — micro-probes to validate a BIN range | N0 | F1012, F1046 | FA0001 | R2 | A6, A7 | credential |
| CRD-002 | Deepfake video-call authorisation of a transfer | N0 | F1031 | TA0001 | R2 | A2 | identity |
| CRD-003 | Voice-cloned relative-in-need scam | N0 | F1031, F1040.001 | TA0001 | R2, R4 | A1 | none-coerced |
| CRD-004 | Deepfake selfie at biometric onboarding | N0 | F1020.001 | TA0042 | R2 | A2 | identity |
| CRD-005 | Injection attack bypassing the biometric capture path | N0 | F1023 | TA0042, TA0005 | R2 | A6 | identity |
| CRD-006 | Synthetic identity onboarding with generated documents | N0 | F1020.001, F1027 | TA0042 | R2 | A3 | identity |
| CRD-007 | Cloned merchant site resurfacing after takedown | N0 | F1020.002, T1583.001 | TA0042 | R2 | A6 | identity |
| CRD-008 | LLM-in-the-loop malware querying a model mid-execution | N0 | T1195 | TA0002 | R2 | A6, A7 | credential |
| CRD-009 | Chargeback abuse / first-party fraud | N0 | F1024 | TA0002 | R2 | — | none |
| CRD-010 | 3DS bypass via deliberate authentication failure | N0 | F1001, F1039 | TA0005 | R2 | — | session |
| DRV-001 | Model-tier fingerprinting of a payment agent | N3 | F3X-1019 | TA0043 | R3 | A5, B1 | none |
| DRV-002 | Mandate policy enumeration via boundary probing | N3 | F3X-1020 | TA0043 | R3 | A5, B2 | none |
| DRV-003 | Agent card harvesting across a merchant population | N3 | F3X-1020 | TA0043 | R3 | A5, B4 | none |
| DRV-004 | Agent liveness and capability probing via benign orders | N3 | F3X-1020 | TA0043 | R3 | A5 | none |
| DRV-005 | SEO poisoning tuned for agent retrieval, not human search | N3 | T1608.006, F3X-1008 | TA0042 | R3 | A5, A6 | intent |
| DRV-006 | Shell merchant optimised for agent discovery rather than clicks | N3 | F1021, F3X-1008 | TA0042 | R3 | A5 | identity |
| DRV-007 | Disposable agent identity farming below per-agent velocity limits | N3 | T1585, F3X-1004 | TA0042 | R3 | A7, B1 | identity |
| DRV-008 | Mule-controlled agent holding a legitimately delegated token | N3 | F1009, F3X-1021 | FA0001 | R3 | B1, B2 | identity |
| DRV-009 | Dormant agent aging — clean history built before compromise | N3 | F3X-1021 | FA0001, TA0005 | R3 | B1 | identity |
| DRV-010 | Agent reputation laundering via low-value legitimate volume | N3 | F3X-1021 | FA0001, TA0005 | R3 | A7, B1 | none |
| DRV-011 | In-scope resale laundering — liquid goods to a drop address | N3 | F1028 | FA0002 | R3 | B2 | none |
| DRV-012 | Stored-value purchase inside an MCC allowlist | N3 | F1028, F3X-1022 | FA0002 | R3 | B2 | mandate |
| DRV-013 | Intent-schema ambiguity exploitation | N3 | F3X-1023 | TA0112, TA0005 | R3 | A5, B2 | intent |
| DRV-014 | Mandate expiry extension via memory poisoning | N3 | F3X-1023 | TA0112 | R3 | B2, B3 | mandate |
| DRV-015 | Velocity-window straddling across agent identities | N3 | F1045, F3X-1023 | TA0112, TA0005 | R3 | A7 | none |
| DRV-016 | VPA liveness enumeration abusing beneficiary name look-up | N3 | F3X-1024 | TA0043 | R4, R5 | A5, A7 | none |
| DRV-017 | Vulnerable-segment disclosure via the trusted-person requirement | N3 | F3X-1024 | TA0043 | R4 | A5 | none |
| DRV-018 | Trusted-person social engineering above Rs 50,000 | N3 | F3X-1018 | TA0112 | R4 | A1, A4 | none-coerced |
| DRV-019 | Micro-structuring below the Rs 10,000 lag threshold | N3 | F1045 | TA0112, TA0005 | R4 | A7 | none-coerced |
| DRV-020 | Aggregate-credit structuring below the Rs 25 lakh ceiling | N3 | F1045, F1009 | TA0112, FA0002 | R4 | A7 | identity |
| DRV-021 | Cancellation-window exhaustion — sustained contact through the lag hour | N3 | F3X-1018 | TA0112 | R4 | A1, A4 | none-coerced |
| DRV-022 | Kill-switch social engineering and malicious activation | N3 | F3X-1018 | TA0112 | R4, R7 | A4 | none-coerced |
| DRV-023 | Recurring mandate as control evasion | N3 | F3X-1025 | TA0112, FA0001 | R6 | B2 | mandate |
| DRV-024 | E-mandate amount creep on variable recurring authorisations | N3 | F3X-1025 | TA0005, TA0002 | R6 | B2 | mandate |
| DRV-025 | Dormant mandate reactivation after the relationship lapses | N3 | F1042, F3X-1025 | FA0001 | R6 | B2 | mandate |
| DRV-026 | Wallet top-up as a lag-free intermediate hop | N3 | F3X-1026 | TA0112, FA0001 | R7 | A7 | none |
| DRV-027 | PPI chaining to break the payer-payee link before cash-out | N3 | F3X-1026, F1017 | FA0002, TA0005 | R7 | A7 | none |
| DRV-028 | Agent-assisted card testing under a legitimate agent framework | N3 | F1012, F3X-1027 | FA0001, TA0005 | R2, R3 | A6, A7 | credential |
| DRV-029 | Rail-hopping to defeat position-limited detection | N3 | F3X-1028 | TA0005, FA0002 | R2, R4 | A7 | none |
| DRV-030 | Agent-mediated dispute abuse at scale | N3 | F1024 | TA0002, FA0002 | R2, R3 | A7, A4 | none |

## Vectors carrying design notes

**AGT-004 — Mandate scope inflation via poisoned merchant listing**  
Headline demo. 100% ASR published.

**UPI-009 — Whitelist bypass — victim persuaded to whitelist the payee**  
RBI names this weakness in Option 1 themselves.

**DRV-001 — Model-tier fingerprinting of a payment agent**  
Probe with graded payloads to identify the model, then pick structural vs semantic attack. Exists only because published ASR ranges 0-100% by model.

**DRV-002 — Mandate policy enumeration via boundary probing**  
Learn ceiling, MCC allowlist and expiry without triggering a decline. F1046 Test Payment Thresholds, but against a policy object rather than a rail.

**DRV-005 — SEO poisoning tuned for agent retrieval, not human search**  
Agents rank on structured data and description text, so the poisoning differs from human SEO.

**DRV-008 — Mule-controlled agent holding a legitimately delegated token**  
Fraud acquires genuine delegation provenance. Defeats provenance-based defences by construction.

**DRV-009 — Dormant agent aging — clean history built before compromise**  
Direct analogue of mule dormancy. Produces the burst-after-quiet signature in agent form.

**DRV-012 — Stored-value purchase inside an MCC allowlist**  
MCC allowlists rarely exclude stored value, so gift cards sit inside most mandates.

**DRV-013 — Intent-schema ambiguity exploitation**  
Craft purchases semantically defensible against the stated intent. Targets a semantic-consistency detector specifically. This is the attack on our own defence and belongs in F16.

**DRV-016 — VPA liveness enumeration abusing beneficiary name look-up**  
Turns a security feature into a reconnaissance oracle.

**DRV-017 — Vulnerable-segment disclosure via the trusted-person requirement**  
Once the control ships, an account requiring trusted-person approval reveals the holder is 70+ or a person with disability. The protective control leaks the vulnerability it protects.

**DRV-019 — Micro-structuring below the Rs 10,000 lag threshold**  
F3 already has Structuring. The derivation is the specific threshold and the throughput cost.

**DRV-021 — Cancellation-window exhaustion — sustained contact through the lag hour**  
The lag only works if the victim disengages. RBI names sustained psychological pressure as the fraudster's core method, which is precisely what defeats it.

**DRV-023 — Recurring mandate as control evasion**  
RBI exempts e-mandates and NACH from BOTH the one-hour lag and the trusted-person requirement. Converting a one-off fraud into a recurring mandate escapes both proposed controls. An exemption written for convenience is an evasion path.

**DRV-026 — Wallet top-up as a lag-free intermediate hop**  
If the lag binds A2A transfers but wallet loads route differently, wallets are the bypass.

**DRV-028 — Agent-assisted card testing under a legitimate agent framework**  
The attacker runs card testing through a real browsing-agent stack, so bot fingerprinting fails because the traffic genuinely is an agent.

**DRV-029 — Rail-hopping to defeat position-limited detection**  
Acquire on cards, cash out on UPI. No single node in the four-party model sees both halves.
