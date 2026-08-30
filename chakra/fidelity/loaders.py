"""Loaders.

The UID problem, stated plainly: IEEE-CIS has no entity identifier. P1, P2 and
P3 all need one, so it has to be reconstructed, and the reconstruction changes
the answer.

Measured on the full 590,540-row training set:

    partition key                      entities   singletons   p50 events
    card1                                13,553       25.4%        4
    card1 + addr1                        37,531       39.5%        2
    card1 + addr1 + acct_start          199,070       58.0%        1

The community-standard UID is the third one, and at 58% singletons it is too
fragmented to estimate inter-event timing from. The coarsest key gives usable
sequences but conflates distinct cardholders who share a card1 bucket.

There is no correct answer here, so we do not pick one and hide it. The floor
is computed under all three and the spread is reported. A fidelity claim that
does not state its partition is not a claim.
"""
from __future__ import annotations
import math, random
from typing import Dict, List, Optional

import pandas as pd

from chakra.fidelity.metrics import Event, EventLog

PARTITIONS = {
    "card1":      ["card1"],
    "card1_addr1": ["card1", "addr1"],
    "uid_full":   ["card1", "addr1", "acct_start"],
}


def load_ieee(txn_path: str, identity_path: Optional[str] = None,
              partition: str = "card1_addr1",
              crop_days: Optional[float] = None) -> EventLog:
    keep = (["TransactionID", "TransactionDT", "TransactionAmt", "ProductCD",
             "isFraud", "card1", "card2", "card3", "card5", "card4", "card6",
             "addr1", "addr2", "P_emaildomain", "D1"])
    df = pd.read_csv(txn_path, usecols=keep)
    df["day"] = df.TransactionDT // 86400
    df["acct_start"] = df.day - df.D1

    if identity_path:
        idf = pd.read_csv(identity_path,
                          usecols=["TransactionID", "DeviceInfo",
                                   "id_30", "id_31"])
        df = df.merge(idf, on="TransactionID", how="left")
    else:
        df["DeviceInfo"] = None

    cols = PARTITIONS[partition]
    df = df.dropna(subset=cols)
    key = df[cols].astype(str).agg("|".join, axis=1)

    if crop_days:
        t0 = df.TransactionDT.min()
        m = df.TransactionDT <= t0 + crop_days * 86400
        df, key = df[m], key[m]

    events: List[Event] = []
    dev = df["DeviceInfo"] if "DeviceInfo" in df else None
    for i, (k, row) in enumerate(zip(key, df.itertuples(index=False))):
        attrs = {}
        d = getattr(row, "DeviceInfo", None)
        if isinstance(d, str) and d:
            attrs["device"] = d
        a1 = getattr(row, "addr1", None)
        if a1 is not None and not (isinstance(a1, float) and math.isnan(a1)):
            attrs["addr"] = str(a1)
        em = getattr(row, "P_emaildomain", None)
        if isinstance(em, str) and em:
            attrs["email_domain"] = em
        events.append(Event(entity=k, t=float(row.TransactionDT),
                            amount=float(row.TransactionAmt),
                            category=str(row.ProductCD),
                            attrs=attrs, is_fraud=bool(row.isFraud)))
    return EventLog(f"ieee[{partition}]", events)


def load_chakra(csv_path: str) -> EventLog:
    """Our own output, reduced through the identical abstraction.

    Note the entity choice mirrors Transaction.entity_id(): token for card
    rails, VPA for UPI. At the network node nothing links the two, so one
    person legitimately appears as two entities. That is the schema being
    honest, not a bug — and it is what DRV-029 rail-hopping exploits.
    """
    df = pd.read_csv(csv_path)
    events: List[Event] = []
    for row in df.itertuples(index=False):
        ent = (row.token_pan if isinstance(row.token_pan, str)
               else row.payer_vpa)
        if not isinstance(ent, str):
            continue
        attrs = {}
        d = getattr(row, "device_binding_id", None)
        if isinstance(d, str) and d:
            attrs["device"] = d
        m = getattr(row, "merchant_id", None)
        if isinstance(m, str) and m:
            attrs["merchant"] = m
        a = getattr(row, "acquirer_id", None)
        if isinstance(a, str) and a:
            attrs["acquirer"] = a
        ts = pd.Timestamp(row.ts).timestamp()
        events.append(Event(entity=ent, t=float(ts),
                            amount=float(row.amount),
                            category=str(row.mcc),
                            attrs=attrs, is_fraud=False))
    return EventLog("chakra", events)


def shuffled_control(log: EventLog, rng: random.Random) -> EventLog:
    """The row-independent baseline, built without training anything.

    Reassigning every event to a random entity and re-drawing its timestamp
    from the pooled marginal is exactly what a row-independent generator does
    at the limit of perfect marginal fit. It is the strongest such generator
    that can exist, so if it fails P1 and P3 badly, no amount of CTGAN
    training escapes it — which is the paper's proof, made checkable in about
    fifteen lines.
    """
    ents = sorted({e.entity for e in log.events})
    ts = [e.t for e in log.events]
    out = []
    for e in log.events:
        out.append(Event(entity=rng.choice(ents),
                         t=rng.choice(ts),
                         amount=e.amount,
                         category=e.category,
                         attrs={k: v for k, v in e.attrs.items()},
                         is_fraud=e.is_fraud))
    # shared attributes resampled from their marginal, which is the step that
    # destroys graph structure
    for a in ("device", "merchant", "addr", "acquirer", "email_domain"):
        vals = [e.attrs[a] for e in log.events if a in e.attrs]
        if not vals:
            continue
        for e in out:
            if a in e.attrs:
                e.attrs[a] = rng.choice(vals)
    return EventLog(log.name + "_rowindep", out)


def load_sparkov(path: str, crop_days: Optional[float] = None,
                 max_entities: Optional[int] = None) -> EventLog:
    """Sparkov (FDB `sparknov`).

    Two properties make this valuable and one makes it limited.

    VALUABLE. It carries a REAL entity identifier, `cc_num`. IEEE-CIS has
    none, so its floor rests on a reconstructed UID that produces 58%
    singletons at the community-standard key. Sparkov lets us check whether
    that reconstruction was distorting the answer. Its fraud rate is also
    0.58%, far closer to real payment base rates than IEEE-CIS's 3.50%.

    LIMITED. Sparkov is itself simulator output, not real transactions. It is
    a reference CORPUS, not a real-data floor, and the write-up must say so.
    Measuring our simulator against another simulator is informative about
    convergence, not about reality.

    It also cannot support P3, for the opposite reason to IEEE-CIS. Measured:
    the card-merchant bipartite graph is 70.3% dense, every card touches a
    median of 524 of 693 merchants, and `zip` and `street` map to exactly one
    card 98.7% of the time. Those are identity fields, not shared attributes.
    IEEE-CIS has too little linkage; Sparkov has too much and none of it
    selective.
    """
    df = pd.read_csv(path, usecols=["cc_num", "merchant", "category", "amt",
                                    "unix_time", "zip", "is_fraud"])
    if max_entities:
        ents = pd.Series(df.cc_num.unique())
        keep = set(ents.sample(min(max_entities, len(ents)), random_state=7))
        df = df[df.cc_num.isin(keep)]
    if crop_days:
        t0 = df.unix_time.min()
        df = df[df.unix_time <= t0 + crop_days * 86400]
    events: List[Event] = []
    for row in df.itertuples(index=False):
        events.append(Event(entity=str(row.cc_num), t=float(row.unix_time),
                            amount=float(row.amt), category=str(row.category),
                            attrs={"merchant": str(row.merchant),
                                   "zip": str(row.zip)},
                            is_fraud=bool(row.is_fraud)))
    return EventLog("sparkov", events)
