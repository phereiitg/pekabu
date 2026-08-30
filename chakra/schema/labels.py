"""Labels, and the delay that makes them hard.

Dal Pozzolo et al. (IJCNN 2015; IEEE TNNLS 2018) state the problem plainly:
investigators can assess only a small number of alerts, while labels for the
vast majority arrive days later when customers report unauthorised
transactions. Their result is that the two streams should be modelled as two
problems and the classifiers aggregated.

Three consequences we implement here, none of which a random train/test split
can express:

  1. The FAST stream only covers transactions we alerted on. It is small and
     it is selection-biased by our own model's decisions.
  2. The DELAYED stream arrives at t + delta. At decision time it does not
     exist.
  3. A share of fraud is NEVER labelled. The customer does not notice, or does
     not report. On UPI rails this share is higher, because there is no
     chargeback mechanism to force the issue.

Ground truth is held here and nowhere else. It is never a field on Transaction.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple

from .enums import Rail, TrustLink


@dataclass(slots=True)
class GroundTruth:
    """What actually happened. Available to the evaluator, never to the model."""
    txn_id: str
    is_fraud: bool
    vector_id: Optional[str] = None      # taxonomy id, e.g. "AGT-004"
    trust_link: TrustLink = TrustLink.NONE
    adversary_id: Optional[str] = None
    value_at_risk: float = 0.0


@dataclass(slots=True)
class LabelEvent:
    txn_id: str
    label: bool
    available_from: datetime
    stream: str                          # "fast" | "delayed"


@dataclass
class LabelHarness:
    delayed_delta: timedelta = timedelta(days=45)
    fast_delta: timedelta = timedelta(hours=6)
    report_rate_pull: float = 0.85       # chargeback exists, so most surface
    report_rate_push: float = 0.55       # no recourse, so many never report

    truth: Dict[str, GroundTruth] = field(default_factory=dict)
    events: List[LabelEvent] = field(default_factory=list)
    _alerted: set = field(default_factory=set)

    # -- writing ---------------------------------------------------------
    def register(self, gt: GroundTruth, ts: datetime, rail: Rail, rng) -> None:
        self.truth[gt.txn_id] = gt
        rate = (self.report_rate_pull if rail.has_chargeback
                else self.report_rate_push)
        if gt.is_fraud and rng.random() > rate:
            return                        # never reported, never labelled
        self.events.append(LabelEvent(gt.txn_id, gt.is_fraud,
                                      ts + self.delayed_delta, "delayed"))

    def alert(self, txn_id: str, ts: datetime) -> None:
        """Our model raised this for review. Only alerted transactions can
        enter the fast stream, which is exactly the selection bias Dal Pozzolo
        warns about — and modelling it is the point."""
        if txn_id in self._alerted or txn_id not in self.truth:
            return
        self._alerted.add(txn_id)
        self.events.append(LabelEvent(txn_id, self.truth[txn_id].is_fraud,
                                      ts + self.fast_delta, "fast"))

    # -- reading ---------------------------------------------------------
    def available(self, as_of: datetime,
                  stream: Optional[str] = None) -> Dict[str, bool]:
        """Labels a model training at `as_of` would actually possess.
        Everything else is still in the future and using it is time travel."""
        out: Dict[str, bool] = {}
        for e in self.events:
            if e.available_from <= as_of and (stream is None or e.stream == stream):
                out[e.txn_id] = e.label
        return out

    def coverage(self, as_of: datetime) -> Dict[str, float]:
        """Reported alongside every efficacy number in F11. A model trained on
        40% label coverage and one trained on 95% are not comparable, and most
        submissions will not say which they had."""
        total = len(self.truth)
        fast = self.available(as_of, "fast")
        delayed = self.available(as_of, "delayed")
        both = set(fast) | set(delayed)
        frauds = sum(1 for g in self.truth.values() if g.is_fraud)
        labelled_fraud = sum(1 for t in both if self.truth[t].is_fraud)
        return {
            "transactions": float(total),
            "fast_labels": float(len(fast)),
            "delayed_labels": float(len(delayed)),
            "label_coverage": len(both) / total if total else 0.0,
            "fraud_label_coverage": labelled_fraud / frauds if frauds else 0.0,
            "unlabelled_fraud": float(frauds - labelled_fraud),
        }

    def split_no_time_travel(self, train_end: datetime
                             ) -> Tuple[Dict[str, bool], List[str]]:
        """The only split we use. Train on labels available at train_end;
        evaluate on transactions after it.

        We do not offer a random-split helper. A random split assumes labels
        you would not have at decision time, and having no function for it
        means nobody reaches for one at 3am.
        """
        train = self.available(train_end)
        test = [t for t in self.truth if t not in train]
        return train, test
