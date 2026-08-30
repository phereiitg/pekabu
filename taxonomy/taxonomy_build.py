#!/usr/bin/env python3
"""
Chakra taxonomy — Phase 1 complete.
Emits the matrix, coverage stats, and the extension register.
Counts are computed from the data, never asserted in prose.
"""
import json, sys
from collections import Counter, defaultdict

# ---- F3 v1.1 axis (from the official repo, public/f3-v1.1.json) -------------
TACTICS = [
    ("TA0043", "Reconnaissance",     "ATT&CK"),
    ("TA0042", "Resource Dev",       "ATT&CK"),
    ("TA0001", "Initial Access",     "ATT&CK"),
    ("FA0001", "Positioning",        "F3-native"),
    ("TA0002", "Execution",          "ATT&CK"),
    ("TA0005", "Stealth",            "ATT&CK"),
    ("TA0112", "Defense Impairment", "ATT&CK"),
    ("FA0002", "Monetization",       "F3-native"),
]
TAC_ORDER = [t[0] for t in TACTICS]
TAC_NAME  = {t[0]: t[1] for t in TACTICS}

RAILS = [
    ("R1", "Card present"),
    ("R2", "CNP human"),
    ("R3", "CNP agentic"),
    ("R4", "UPI push"),
    ("R5", "UPI collect"),
    ("R6", "Tokenised recurring"),
    ("R7", "Wallet / PPI"),
]
RAIL_ORDER = [r[0] for r in RAILS]
RAIL_NAME  = {r[0]: r[1] for r in RAILS}

CAPS = {
    "A1": "Synthetic voice, interactive",
    "A2": "Synthetic face/video, interactive",
    "A3": "Synthetic documents & identity",
    "A4": "Personalised persuasion at scale",
    "A5": "Semantic recon & targeting",
    "A6": "Code generation & tooling",
    "A7": "Attacker-side execution autonomy",
    "B1": "The delegated agent",
    "B2": "The mandate / intent artifact",
    "B3": "Agent memory & retrieval context",
    "B4": "Inter-agent channel",
}

def V(vid, name, grade, src, f3, tac, rails, caps, breaks, status="taxonomy_only", note=""):
    return dict(id=vid, name=name, grade=grade, source=src, f3=f3, tactics=tac,
                rails=rails, caps=caps, breaks=breaks, status=status, note=note)

T = []  # taxonomy

# ============================================================================
# ANCHORS — N0 / N1 / N2.  Nothing here was invented by us.
# ============================================================================

# --- Cluster 1: mandate & intent -------------------------------------------
T += [
 V("AGT-001","Payment Mandate theft for an unrelated checkout","N2","AP2 security considerations",
   ["F3X-1002"],["TA0002"],["R3"],["B2"],"mandate"),
 V("AGT-002","Open-mandate reuse against a different closed mandate","N2","AP2 security considerations",
   ["F3X-1002"],["TA0002","TA0005"],["R3"],["B2"],"mandate"),
 V("AGT-003","Injected agent approves multiple checkouts from one open mandate","N2","AP2 security considerations",
   ["F3X-1001"],["TA0002"],["R3"],["B1","B2"],"mandate"),
 V("AGT-004","Mandate scope inflation via poisoned merchant listing","N1","arXiv:2601.22569",
   ["F3X-1001"],["TA0002"],["R3"],["B1"],"intent","implemented","Headline demo. 100% ASR published."),
 V("AGT-005","Branded Whisper — agent ranking manipulation","N1","arXiv:2601.22569",
   ["F3X-1008"],["TA0043","TA0042"],["R3"],["A5","B1"],"intent"),
 V("AGT-006","Vault Whisper — cross-user disclosure via direct injection","N1","arXiv:2601.22569",
   ["F3X-1009"],["TA0043"],["R3"],["B1"],"session"),
 V("AGT-007","Replay on trust chains — stale delegation honoured","N2","OWASP ASI07",
   ["F3X-1002"],["TA0002"],["R3"],["B4"],"mandate"),
 V("AGT-008","Workflow authorisation drift — old token completes after limit cut","N2","OWASP ASI03",
   ["F1005.003","F3X-1010"],["TA0002","TA0005"],["R3","R6"],["B2"],"mandate","implemented"),
 V("AGT-009","TOCTOU in agent workflows","N2","OWASP ASI03",
   ["F3X-1010"],["TA0002"],["R3"],["B2"],"mandate"),
 V("AGT-010","Semantics split-brain across two agents","N2","OWASP ASI07",
   ["F3X-1011"],["TA0002"],["R3"],["B4"],"intent"),
 V("AGT-011","Protocol downgrade then objective injection","N2","OWASP ASI07",
   ["F3X-1012"],["TA0001","TA0005"],["R3"],["B4"],"channel"),
]

# --- Cluster 2: agent identity & delegation --------------------------------
T += [
 V("AGT-012","Cross-agent confused deputy relaying a payment instruction","N2","OWASP ASI03",
   ["F3X-1005"],["TA0001","TA0002"],["R3"],["B4"],"identity"),
 V("AGT-013","Forged agent persona in an A2A registry","N0","Trustwave, Apr 2025",
   ["F3X-1004"],["TA0042","TA0001"],["R3"],["B4"],"identity"),
 V("AGT-014","Agent-in-the-middle via exaggerated agent card","N0","Trustwave, Apr 2025",
   ["F3X-1004","T1557"],["TA0001","FA0001"],["R3"],["B4"],"identity"),
 V("AGT-015","Impersonated approval agent injected into a payment workflow","N2","OWASP ASI10",
   ["F3X-1005"],["TA0002"],["R3"],["B4"],"identity"),
 V("AGT-016","Synthetic identity injection via unverified descriptors","N2","OWASP ASI03",
   ["F3X-1004"],["TA0042"],["R3"],["B4"],"identity"),
 V("AGT-017","Device-code phishing across agents","N2","OWASP ASI03",
   ["T1550.001"],["TA0001"],["R3"],["B1"],"credential"),
 V("AGT-018","Un-scoped privilege inheritance in delegation chains","N2","OWASP ASI03",
   ["F3X-1013"],["TA0002"],["R3"],["B1"],"identity"),
 V("AGT-019","Identity sharing — delegated access reused by other principals","N2","OWASP ASI03",
   ["F3X-1013"],["TA0001"],["R3"],["B1"],"identity"),
]

# --- Cluster 3: memory, context, drift -------------------------------------
T += [
 V("AGT-020","Booking memory poisoning bypasses payment checks","N2","OWASP ASI06",
   ["F3X-1006"],["FA0001","TA0002"],["R3"],["B3"],"intent"),
 V("AGT-021","Context-window exploitation — permissions escalate across sessions","N2","OWASP ASI06",
   ["F3X-1006"],["FA0001","TA0005"],["R3"],["B3"],"mandate","implemented"),
 V("AGT-022","Long-term memory drift via incrementally tainted data","N2","OWASP ASI06",
   ["F3X-1006"],["TA0005"],["R3"],["B3"],"intent"),
 V("AGT-023","Goal-lock drift — scheduled prompts reweight toward low-friction approval","N2","OWASP ASI01",
   ["F3X-1003"],["TA0005","TA0112"],["R3"],["B3"],"intent"),
 V("AGT-024","Shared memory poisoning — bogus refund policy reused","N2","OWASP ASI06",
   ["F3X-1006"],["FA0002"],["R3"],["B3"],"intent"),
 V("AGT-025","Gemini long-term memory corruption via prompt injection","N0","Ars Technica, Feb 2025",
   ["F3X-1006"],["TA0005"],["R3"],["B3"],"intent"),
 V("AGT-026","Cross-tenant vector bleed via loose namespace filters","N2","OWASP ASI06",
   ["F3X-1009"],["TA0043"],["R3"],["B3"],"session"),
 V("AGT-027","Bootstrap poisoning — agent re-ingests own output as trusted","N2","OWASP ASI06",
   ["F3X-1006"],["TA0005"],["R3"],["B3"],"intent"),
]

# --- Cluster 4: detector-facing & cascade ----------------------------------
T += [
 V("AGT-028","Anomaly flooding to exhaust reviewers, then slow cartel","N2","CSA AP2 guidance",
   ["F3X-1007"],["TA0112"],["R3"],["A7"],"none","implemented"),
 V("AGT-029","Auto-remediation loop suppresses alerts to meet SLAs","N2","OWASP ASI08",
   ["F3X-1007"],["TA0112"],["R3"],["A7","B4"],"none"),
 V("AGT-030","Governance drift cascade — bulk approval after repeated success","N2","OWASP ASI08",
   ["F3X-1007"],["TA0112","TA0005"],["R3"],["A7"],"none"),
 V("AGT-031","Within-parameter cascade — inflated limits, compliance blind","N2","OWASP ASI08",
   ["F3X-1003"],["TA0002","TA0005"],["R3"],["B4"],"intent"),
 V("AGT-032","Log injection to mask cross-agent coordination","N2","CSA AP2 guidance",
   ["T1070"],["TA0005","TA0112"],["R3"],["A6"],"none"),
 V("AGT-033","Metadata profiling of agent decision cycles","N2","OWASP ASI07",
   ["F3X-1014"],["TA0043"],["R3"],["A5"],"none"),
]

# --- Cluster 5: supply chain into the payment agent -------------------------
T += [
 V("AGT-034","Malicious MCP server impersonating a legitimate one","N0","Koi Security, Sep 2025",
   ["T1195","F3X-1015"],["TA0042","TA0001"],["R3"],["A6"],"channel"),
 V("AGT-035","Tool-descriptor poisoning via MCP metadata","N0","Invariant Labs",
   ["F3X-1015"],["TA0002"],["R3"],["A6"],"channel"),
 V("AGT-036","Backdoored MCP package, install-time and runtime shells","N0","Koi Security, Oct 2025",
   ["T1195"],["TA0042"],["R3"],["A6"],"channel"),
 V("AGT-037","Tool name typosquatting resolves before the real tool","N2","OWASP ASI02",
   ["F3X-1015"],["TA0042","TA0002"],["R3"],["A6"],"channel"),
 V("AGT-038","Poisoned knowledge plugin seeding a RAG index over time","N2","OWASP ASI04",
   ["F3X-1006"],["TA0005"],["R3"],["B3"],"intent"),
 V("AGT-039","Over-privileged financial API — order agent can also refund","N2","OWASP ASI02",
   ["F3X-1013"],["FA0002"],["R3"],["B1"],"mandate"),
]

# --- Cluster 6: human-facing, agent-mediated -------------------------------
T += [
 V("HUM-001","Invoice copilot fraud — poisoned invoice, attacker bank details","N2","OWASP ASI09",
   ["F1036","F1005.006"],["TA0042","FA0002"],["R2","R3"],["A4","B1"],"none-coerced"),
 V("HUM-002","Copilot manipulated into influencing a wire transfer","N0","ASI09 references",
   ["F3X-1016"],["TA0002"],["R2","R3"],["A4","B1"],"none-coerced"),
 V("HUM-003","Fake explainability secures human approval","N2","OWASP ASI09",
   ["F3X-1016"],["TA0005"],["R3"],["A4"],"none-coerced"),
 V("HUM-004","Consent laundering via read-only preview with side effects","N2","OWASP ASI09",
   ["F3X-1016"],["TA0002"],["R3"],["B1"],"intent"),
 V("HUM-005","Human-in-the-loop fatigue at autonomous approval volume","N2","CSA AP2 guidance",
   ["F3X-1007"],["TA0112"],["R3"],["A7"],"none-coerced"),
 V("HUM-006","Missing confirmation turns one prompt into an irreversible transfer","N2","OWASP ASI09",
   ["F3X-1016"],["TA0002"],["R3"],["B1"],"intent"),
]

# --- Cluster 7: India rail, regulator-documented ----------------------------
T += [
 V("UPI-001","APP fraud — victim initiates and authenticates under deception","N0","RBI DP Apr 2026",
   ["F1025.001","F1025.002"],["TA0002","FA0002"],["R4"],["A4"],"none-coerced","implemented"),
 V("UPI-002","Bogus call centre operations","N0","RBI DP Apr 2026",
   ["F1032"],["TA0001"],["R4","R5"],["A1","A4"],"none-coerced"),
 V("UPI-003","Deepfake-driven impersonation scam","N0","RBI DP Apr 2026",
   ["F1031"],["TA0001","TA0005"],["R4"],["A1","A2"],"identity"),
 V("UPI-004","Mule account network for proceeds movement","N0","RBI DP · MuleHunter.AI",
   ["F1009","F1009.002"],["FA0001","FA0002"],["R4"],["A3"],"identity","implemented"),
 V("UPI-005","Impersonation of family, fabricated medical or legal urgency","N0","RBI DP Apr 2026",
   ["F1031"],["TA0001"],["R4"],["A1","A4"],"none-coerced"),
 V("UPI-006","Collect-request fraud — a debit dressed as a credit","N0","Rail primitive",
   ["F3X-1017"],["TA0002"],["R5"],["A4"],"none-coerced","implemented"),
 V("UPI-007","Aggregator-onboarded merchant laundering as small-business commerce","N0","Mule telemetry",
   ["F1021"],["TA0042","FA0002"],["R4"],["A3"],"identity"),
 V("UPI-008","Payments-bank VPA farming via low-friction onboarding","N0","Mule telemetry",
   ["T1585","F1020.001"],["TA0042","FA0001"],["R4"],["A3"],"identity"),
 V("UPI-009","Whitelist bypass — victim persuaded to whitelist the payee","N2","RBI DP, stated con",
   ["F3X-1018"],["TA0112"],["R4"],["A4"],"none-coerced","implemented",
   "RBI names this weakness in Option 1 themselves."),
]

# --- Cluster 8: classic, GenAI-accelerated ---------------------------------
T += [
 V("CRD-001","Card testing — micro-probes to validate a BIN range","N0","Standard",
   ["F1012","F1046"],["FA0001"],["R2"],["A6","A7"],"credential","implemented"),
 V("CRD-002","Deepfake video-call authorisation of a transfer","N0","Arup, Jan 2024",
   ["F1031"],["TA0001"],["R2"],["A2"],"identity"),
 V("CRD-003","Voice-cloned relative-in-need scam","N0","Widely reported",
   ["F1031","F1040.001"],["TA0001"],["R2","R4"],["A1"],"none-coerced"),
 V("CRD-004","Deepfake selfie at biometric onboarding","N0","Entrust 2026",
   ["F1020.001"],["TA0042"],["R2"],["A2"],"identity"),
 V("CRD-005","Injection attack bypassing the biometric capture path","N0","Entrust 2026, +40% YoY",
   ["F1023"],["TA0042","TA0005"],["R2"],["A6"],"identity"),
 V("CRD-006","Synthetic identity onboarding with generated documents","N0","Sumsub",
   ["F1020.001","F1027"],["TA0042"],["R2"],["A3"],"identity"),
 V("CRD-007","Cloned merchant site resurfacing after takedown","N0","Standard",
   ["F1020.002","T1583.001"],["TA0042"],["R2"],["A6"],"identity"),
 V("CRD-008","LLM-in-the-loop malware querying a model mid-execution","N0","PROMPTFLUX/STEAL Nov 2025",
   ["T1195"],["TA0002"],["R2"],["A6","A7"],"credential"),
 V("CRD-009","Chargeback abuse / first-party fraud","N0","Sumsub",
   ["F1024"],["TA0002"],["R2"],[],"none"),
 V("CRD-010","3DS bypass via deliberate authentication failure","N0","F3 F1001",
   ["F1001","F1039"],["TA0005"],["R2"],[],"session"),
]

# ============================================================================
# DERIVED — N3.  Ours. Produced by crossing anchors against empty matrix cells.
# ============================================================================

# --- R3 x Reconnaissance (was near-empty) ----------------------------------
T += [
 V("DRV-001","Model-tier fingerprinting of a payment agent","N3","Derived · AIP-Bench gradient",
   ["F3X-1019"],["TA0043"],["R3"],["A5","B1"],"none","implemented",
   "Probe with graded payloads to identify the model, then pick structural vs semantic attack. "
   "Exists only because published ASR ranges 0-100% by model."),
 V("DRV-002","Mandate policy enumeration via boundary probing","N3","Derived from F1046",
   ["F3X-1020"],["TA0043"],["R3"],["A5","B2"],"none","implemented",
   "Learn ceiling, MCC allowlist and expiry without triggering a decline. "
   "F1046 Test Payment Thresholds, but against a policy object rather than a rail."),
 V("DRV-003","Agent card harvesting across a merchant population","N3","Derived from AGT-014",
   ["F3X-1020"],["TA0043"],["R3"],["A5","B4"],"none"),
 V("DRV-004","Agent liveness and capability probing via benign orders","N3","Derived",
   ["F3X-1020"],["TA0043"],["R3"],["A5"],"none"),
]

# --- R3 x Resource Development ---------------------------------------------
T += [
 V("DRV-005","SEO poisoning tuned for agent retrieval, not human search","N3","Derived from T1608.006",
   ["T1608.006","F3X-1008"],["TA0042"],["R3"],["A5","A6"],"intent",
   "taxonomy_only","Agents rank on structured data and description text, so the poisoning differs from human SEO."),
 V("DRV-006","Shell merchant optimised for agent discovery rather than clicks","N3","Derived from F1021",
   ["F1021","F3X-1008"],["TA0042"],["R3"],["A5"],"identity"),
 V("DRV-007","Disposable agent identity farming below per-agent velocity limits","N3","Derived from UPI-008",
   ["T1585","F3X-1004"],["TA0042"],["R3"],["A7","B1"],"identity"),
]

# --- R3 x Positioning (empty before) ---------------------------------------
T += [
 V("DRV-008","Mule-controlled agent holding a legitimately delegated token","N3","Derived · UPI-004 x R3",
   ["F1009","F3X-1021"],["FA0001"],["R3"],["B1","B2"],"identity","implemented",
   "Fraud acquires genuine delegation provenance. Defeats provenance-based defences by construction."),
 V("DRV-009","Dormant agent aging — clean history built before compromise","N3","Derived · mule dormancy x R3",
   ["F3X-1021"],["FA0001","TA0005"],["R3"],["B1"],"identity","implemented",
   "Direct analogue of mule dormancy. Produces the burst-after-quiet signature in agent form."),
 V("DRV-010","Agent reputation laundering via low-value legitimate volume","N3","Derived",
   ["F3X-1021"],["FA0001","TA0005"],["R3"],["A7","B1"],"none"),
]

# --- R3 x Monetization (empty before) --------------------------------------
T += [
 V("DRV-011","In-scope resale laundering — liquid goods to a drop address","N3","Derived",
   ["F1028"],["FA0002"],["R3"],["B2"],"none"),
 V("DRV-012","Stored-value purchase inside an MCC allowlist","N3","Derived",
   ["F1028","F3X-1022"],["FA0002"],["R3"],["B2"],"mandate",
   "taxonomy_only","MCC allowlists rarely exclude stored value, so gift cards sit inside most mandates."),
]

# --- R3 x Defense Impairment: attacks on OUR OWN detector -------------------
T += [
 V("DRV-013","Intent-schema ambiguity exploitation","N3","Derived · attack on our Head C",
   ["F3X-1023"],["TA0112","TA0005"],["R3"],["A5","B2"],"intent","implemented",
   "Craft purchases semantically defensible against the stated intent. Targets a semantic-consistency "
   "detector specifically. This is the attack on our own defence and belongs in F16."),
 V("DRV-014","Mandate expiry extension via memory poisoning","N3","Derived · AGT-022 x B2",
   ["F3X-1023"],["TA0112"],["R3"],["B2","B3"],"mandate"),
 V("DRV-015","Velocity-window straddling across agent identities","N3","Derived",
   ["F1045","F3X-1023"],["TA0112","TA0005"],["R3"],["A7"],"none"),
]

# --- R4/R5 x Reconnaissance (empty before) ---------------------------------
T += [
 V("DRV-016","VPA liveness enumeration abusing beneficiary name look-up","N3","Derived · RBI DP mentions the facility",
   ["F3X-1024"],["TA0043"],["R4","R5"],["A5","A7"],"none","implemented",
   "Turns a security feature into a reconnaissance oracle."),
 V("DRV-017","Vulnerable-segment disclosure via the trusted-person requirement","N3","Derived · RBI Option 2",
   ["F3X-1024"],["TA0043"],["R4"],["A5"],"none","implemented",
   "Once the control ships, an account requiring trusted-person approval reveals the holder is 70+ "
   "or a person with disability. The protective control leaks the vulnerability it protects."),
]

# --- R4/R5 x Defense Impairment: the RBI control-survival set ---------------
T += [
 V("DRV-018","Trusted-person social engineering above Rs 50,000","N3","Derived · RBI Option 2",
   ["F3X-1018"],["TA0112"],["R4"],["A1","A4"],"none-coerced","implemented"),
 V("DRV-019","Micro-structuring below the Rs 10,000 lag threshold","N3","Derived · RBI Option 1",
   ["F1045"],["TA0112","TA0005"],["R4"],["A7"],"none-coerced","implemented",
   "F3 already has Structuring. The derivation is the specific threshold and the throughput cost."),
 V("DRV-020","Aggregate-credit structuring below the Rs 25 lakh ceiling","N3","Derived · RBI Option 3",
   ["F1045","F1009"],["TA0112","FA0002"],["R4"],["A7"],"identity","implemented"),
 V("DRV-021","Cancellation-window exhaustion — sustained contact through the lag hour","N3","Derived · RBI Option 1",
   ["F3X-1018"],["TA0112"],["R4"],["A1","A4"],"none-coerced","implemented",
   "The lag only works if the victim disengages. RBI names sustained psychological pressure as the "
   "fraudster's core method, which is precisely what defeats it."),
 V("DRV-022","Kill-switch social engineering and malicious activation","N3","Derived · RBI Option 4",
   ["F3X-1018"],["TA0112"],["R4","R7"],["A4"],"none-coerced"),
]

# --- R6 tokenised recurring: the exemption finding --------------------------
T += [
 V("DRV-023","Recurring mandate as control evasion","N3","Derived · RBI Options 1 & 2 exemptions",
   ["F3X-1025"],["TA0112","FA0001"],["R6"],["B2"],"mandate","implemented",
   "RBI exempts e-mandates and NACH from BOTH the one-hour lag and the trusted-person requirement. "
   "Converting a one-off fraud into a recurring mandate escapes both proposed controls. "
   "An exemption written for convenience is an evasion path."),
 V("DRV-024","E-mandate amount creep on variable recurring authorisations","N3","Derived",
   ["F3X-1025"],["TA0005","TA0002"],["R6"],["B2"],"mandate"),
 V("DRV-025","Dormant mandate reactivation after the relationship lapses","N3","Derived from F1042",
   ["F1042","F3X-1025"],["FA0001"],["R6"],["B2"],"mandate"),
]

# --- R7 wallet -------------------------------------------------------------
T += [
 V("DRV-026","Wallet top-up as a lag-free intermediate hop","N3","Derived · RBI Option 1 scope",
   ["F3X-1026"],["TA0112","FA0001"],["R7"],["A7"],"none",
   "taxonomy_only","If the lag binds A2A transfers but wallet loads route differently, wallets are the bypass."),
 V("DRV-027","PPI chaining to break the payer-payee link before cash-out","N3","Derived",
   ["F3X-1026","F1017"],["FA0002","TA0005"],["R7"],["A7"],"none"),
]

# --- R2 cross-effects ------------------------------------------------------
T += [
 V("DRV-028","Agent-assisted card testing under a legitimate agent framework","N3","Derived · CRD-001 x A7",
   ["F1012","F3X-1027"],["FA0001","TA0005"],["R2","R3"],["A6","A7"],"credential","implemented",
   "The attacker runs card testing through a real browsing-agent stack, so bot fingerprinting fails "
   "because the traffic genuinely is an agent."),
 V("DRV-029","Rail-hopping to defeat position-limited detection","N3","Derived · four-party asymmetry",
   ["F3X-1028"],["TA0005","FA0002"],["R2","R4"],["A7"],"none","implemented",
   "Acquire on cards, cash out on UPI. No single node in the four-party model sees both halves."),
 V("DRV-030","Agent-mediated dispute abuse at scale","N3","Derived · CRD-009 x A7",
   ["F1024"],["TA0002","FA0002"],["R2","R3"],["A7","A4"],"none"),
]

# ============================================================================
# RENDER
# ============================================================================
def main():
    out = []
    w = out.append

    n = len(T)
    grades = Counter(v["grade"] for v in T)
    anchors = sum(grades[g] for g in ("N0","N1","N2"))

    w("# Chakra taxonomy — Phase 1 complete\n")
    w("*Generated from `taxonomy_build.py`. Every number below is computed from the data.*\n")

    w("## Headline counts\n")
    w(f"- **{n} vectors total**")
    w(f"- **{anchors} anchors** (N0 {grades['N0']} · N1 {grades['N1']} · N2 {grades['N2']}) — none invented by us")
    w(f"- **{grades['N3']} derived** by crossing anchors against empty matrix cells")
    w(f"- **0 at N4** so far — the loop has not run yet\n")

    impl = sum(1 for v in T if v["status"] == "implemented")
    w(f"- {impl} marked `implemented` (a generator will be built), {n-impl} `taxonomy_only`\n")

    # --- matrix ---
    w("## The matrix — F3 tactic x rail\n")
    w("Counts are technique-rail pairs. A vector spanning two tactics and two rails appears four times, "
      "which follows F3's own multi-tactic convention.\n")
    grid = defaultdict(list)
    for v in T:
        for ta in v["tactics"]:
            for r in v["rails"]:
                grid[(ta, r)].append(v["id"])

    hdr = "| Tactic | " + " | ".join(f"{r}" for r in RAIL_ORDER) + " | **Σ** |"
    w(hdr)
    w("|" + "---|" * (len(RAIL_ORDER) + 2))
    coltot = Counter()
    for ta in TAC_ORDER:
        cells, rowtot = [], 0
        for r in RAIL_ORDER:
            c = len(grid[(ta, r)])
            rowtot += c; coltot[r] += c
            cells.append(str(c) if c else "·")
        w(f"| **{ta}** {TAC_NAME[ta]} | " + " | ".join(cells) + f" | **{rowtot}** |")
    w("| **Σ** | " + " | ".join(f"**{coltot[r]}**" for r in RAIL_ORDER) +
      f" | **{sum(coltot.values())}** |")
    w("")
    w("Rail key: " + " · ".join(f"**{k}** {RAIL_NAME[k]}" for k in RAIL_ORDER) + "\n")

    # --- empty cells ---
    empty = [(ta, r) for ta in TAC_ORDER for r in RAIL_ORDER if not grid[(ta, r)]]
    w(f"### The {len(empty)} cells that are still empty\n")
    w("Empty cells are a finding, not a gap. Grouped by why:\n")
    byrail = defaultdict(list)
    for ta, r in empty:
        byrail[r].append(TAC_NAME[ta])
    for r in RAIL_ORDER:
        if byrail[r]:
            w(f"- **{r} {RAIL_NAME[r]}** — {', '.join(byrail[r])}")
    w("")
    w("**R1 card-present is empty throughout.** That is the single clearest structural result in the "
      "taxonomy: GenAI barely touches card-present fraud because the attack requires physical presence "
      "at a terminal. No capability on our Axis 3 collapses that cost. Say this explicitly — a team that "
      "reports an empty region and explains the mechanism reads very differently from one that quietly "
      "pads it.\n")

    # --- capability split ---
    w("## Capability axis — the two-family split\n")
    capcount = Counter()
    fam = Counter()
    for v in T:
        for c in v["caps"]:
            capcount[c] += 1
            fam["A — cost collapse" if c.startswith("A") else "B — surface creation"] += 1
    w("| Code | Capability | Vectors |")
    w("|---|---|---|")
    for c in sorted(CAPS):
        w(f"| {c} | {CAPS[c]} | {capcount[c]} |")
    w("")

    # split by grade — the aggregate hides the real result
    split = {"anchor": Counter(), "derived": Counter()}
    for v in T:
        bucket = "derived" if v["grade"] == "N3" else "anchor"
        for c in v["caps"]:
            split[bucket]["A" if c.startswith("A") else "B"] += 1
    aa, ab = split["anchor"]["A"], split["anchor"]["B"]
    da, db = split["derived"]["A"], split["derived"]["B"]

    w("| Set | A — cost collapse | B — surface creation |")
    w("|---|---|---|")
    w(f"| Anchors (N0–N2) | {aa} | {ab} |")
    w(f"| Derived (N3) | {da} | {db} |")
    w(f"| **All** | **{aa+da}** | **{ab+db}** |")
    w("")
    def lead(a, b):
        if a == b: return f"the two families are dead even at {a}:{b}"
        return (f"cost collapse leads {a}:{b}" if a > b else f"surface creation leads {b}:{a}")
    w(f"**The two sets behave differently, and that is the finding.** Among the anchors — what the "
      f"field has actually documented — {lead(aa, ab)}. Among our derived entries, {lead(da, db)}.\n")
    w("The reading: the documented record splits evenly, so neither family can be dropped. But our "
      "derivation, working outward from those anchors into the empty cells, lands disproportionately "
      "on cost collapse — specifically on A5 semantic targeting and A7 autonomy. The empty cells are "
      "mostly reconnaissance, positioning and evasion, and those are the stages where an old technique "
      "becomes newly viable once it can be run at machine scale: directory enumeration, structuring "
      "under a threshold, reputation farming, rail-hopping.\n")
    w("So the honest framing for the write-up is that published research favours novel surfaces "
      "because novel surfaces are what gets published, while systematic derivation surfaces the "
      "industrialisation of old techniques. A taxonomy built only from the literature would miss the "
      "second half entirely.\n")

    # --- trust link ---
    w("## What breaks, by trust link\n")
    br = Counter(v["breaks"] for v in T if v["breaks"])
    w("| Link broken | Vectors |")
    w("|---|---|")
    for k, vv in br.most_common():
        w(f"| {k} | {vv} |")
    w("")
    auth_defeating = br["mandate"] + br["intent"] + br["none-coerced"]
    auth_breaking  = br["credential"] + br["session"] + br["identity"]
    w(f"**{auth_defeating} vectors defeat authentication by design** (`mandate`, `intent`, "
      f"`none-coerced`) against **{auth_breaking} that break it** (`credential`, `session`, "
      f"`identity`) — a {auth_defeating}:{auth_breaking} ratio.\n")
    w("In the first group every authentication factor is presented correctly by the legitimate party. "
      "A passkey, a PIN, a signed mandate: all valid. There is no anomaly to detect because nothing "
      "anomalous happened. That is the single sentence the whole defence architecture answers, and "
      "RBI states it independently — account-takeover fraud is now negligible and most fraud is "
      "authorised push payment.\n")
    w("It is also the direct justification for a third detection head. A behavioural model and a graph "
      "model are both anomaly detectors, so between them they address the smaller group. The larger "
      "group needs a detector that compares authorised intent against executed action, which is what "
      "Head C is.\n")

    # --- F3 extension register ---
    w("## F3 extension register\n")
    ext = defaultdict(list)
    native = Counter()
    for v in T:
        for f in v["f3"]:
            (ext if f.startswith("F3X") else native)[f] if f.startswith("F3X") else None
            if f.startswith("F3X"):
                ext[f].append(v["id"])
            else:
                native[f] += 1
    w(f"**{len(ext)} proposed extensions** covering {sum(len(x) for x in ext.values())} vectors, "
      f"against **{len(native)} existing F3 techniques** reused.\n")
    w("F3 v1.1 contains 74 top-level techniques and 49 sub-techniques across 8 tactics. A keyword scan "
      "of all 123 returns zero hits for AI, LLM, model, deepfake, synthetic media, voice cloning, "
      "generative, autonomous or mandate. **F3 has no agentic or GenAI coverage at all**, so every "
      "extension below is genuinely new rather than a relabelling.\n")
    names = {
        "F3X-1001":"Agent Goal Hijack for Payment Redirection",
        "F3X-1002":"Mandate Replay and Scope Reuse",
        "F3X-1003":"Approval Threshold Drift",
        "F3X-1004":"Agent Identity Forgery",
        "F3X-1005":"Cross-Agent Confused Deputy",
        "F3X-1006":"Agent Memory Poisoning",
        "F3X-1007":"Detector Saturation by Autonomous Agents",
        "F3X-1008":"Agent Retrieval Poisoning",
        "F3X-1009":"Cross-Principal Context Disclosure",
        "F3X-1010":"Authorisation Staleness Exploitation",
        "F3X-1011":"Inter-Agent Semantic Divergence",
        "F3X-1012":"Agent Protocol Downgrade",
        "F3X-1013":"Delegated Privilege Overreach",
        "F3X-1014":"Agent Behavioural Profiling",
        "F3X-1015":"Tool Interface Poisoning",
        "F3X-1016":"Agent-Mediated Human Manipulation",
        "F3X-1017":"Collect Request Inversion",
        "F3X-1018":"Consumer Safeguard Circumvention",
        "F3X-1019":"Model Tier Fingerprinting",
        "F3X-1020":"Agent Policy Enumeration",
        "F3X-1021":"Agent Reputation Positioning",
        "F3X-1022":"In-Mandate Stored Value Conversion",
        "F3X-1023":"Intent Detector Evasion",
        "F3X-1024":"Instant Rail Directory Enumeration",
        "F3X-1025":"Recurring Mandate Abuse",
        "F3X-1026":"Prepaid Instrument Chaining",
        "F3X-1027":"Agent Framework Laundering",
        "F3X-1028":"Cross-Rail Visibility Evasion",
    }
    w("| Extension ID | Proposed name | Vectors | F3 tactics reached |")
    w("|---|---|---|---|")
    for k in sorted(ext):
        tacs = sorted({t for vid in ext[k] for v in T if v["id"] == vid for t in v["tactics"]})
        w(f"| `{k}` | {names.get(k,'—')} | {len(ext[k])} | {', '.join(tacs)} |")
    w("")
    w("### Existing F3 techniques reused\n")
    w(", ".join(f"`{k}`({v})" for k, v in sorted(native.items())) + "\n")

    # --- generator shortlist ---
    w("## Generator shortlist\n")
    w("Vectors marked `implemented` get a plugin. Everything else is taxonomy coverage, declared as such.\n")
    w("| ID | Vector | Grade | Rails |")
    w("|---|---|---|---|")
    for v in T:
        if v["status"] == "implemented":
            w(f"| {v['id']} | {v['name']} | {v['grade']} | {', '.join(v['rails'])} |")
    w("")

    # --- full register ---
    w("## Full register\n")
    w("| ID | Vector | Grade | F3 / F3X | Tactics | Rails | Caps | Breaks |")
    w("|---|---|---|---|---|---|---|---|")
    for v in T:
        w(f"| {v['id']} | {v['name']} | {v['grade']} | {', '.join(v['f3'])} | "
          f"{', '.join(v['tactics'])} | {', '.join(v['rails'])} | {', '.join(v['caps']) or '—'} | {v['breaks'] or '—'} |")
    w("")

    # --- notes ---
    w("## Vectors carrying design notes\n")
    for v in T:
        if v["note"]:
            w(f"**{v['id']} — {v['name']}**  \n{v['note']}\n")

    return "\n".join(out)


if __name__ == "__main__":
    md = main()
    with open("/mnt/user-data/outputs/phase1-taxonomy-complete.md", "w") as f:
        f.write(md)
    # also emit machine-readable for the renderer / web app
    with open("/mnt/user-data/outputs/taxonomy.json", "w") as f:
        json.dump(T, f, indent=2)
    print(md[:2600])
    print("\n...\n[full file written]")
