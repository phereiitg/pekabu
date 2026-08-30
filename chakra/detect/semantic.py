"""Semantic intent matching.

WHY THIS IS THE LAST THING LEFT
-------------------------------
AGT-004 stays inside every declared bound. Same category as the hint, amount
well under the ceiling, mandate unexpired, signature valid. All seven hard
checks in Head C pass, and they should — nothing about the mandate was
violated. Head P catches part of it by noticing the merchant is one comparable
agents do not use, but a poisoned listing at a *popular* merchant slips past
that too.

What is left is meaning. The person asked for running shoes and the agent
bought a gift card. Both are inside a 5661 mandate under ₹6,000; only one is
what was meant.

TWO PATHS, ONE INTERFACE
------------------------
`embed` when a Gemini key or a cached artifact is present, `lexical` otherwise.
The repository must run for a judge with no credentials, so the offline path is
not a stub — it is a real character-n-gram TF-IDF model, deterministic and
fitted on the corpus itself.

The offline path is weaker and we say which one produced a number rather than
letting a reader assume the stronger one. `SemanticMatcher.mode` carries it.

WHY EMBEDDINGS AND NOT GENERATION
---------------------------------
The detector is itself a target. DRV-013 in our taxonomy is an attack aimed at
exactly this component: craft a purchase that is semantically defensible against
the stated intent. Asking a generative model "does this purchase match this
instruction?" hands an attacker an instruction-following surface inside the
defence. An embedding endpoint has none — there is no prompt to hijack, only a
vector.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    num = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return num / (na * nb) if na and nb else 0.0


@dataclass
class SemanticMatcher:
    """Similarity between a stated intent and what was actually bought."""

    mode: str = 'lexical'          # 'embed' once real vectors are loaded
    _vec: Dict[str, List[float]] = field(default_factory=dict)
    _idf: Dict[str, float] = field(default_factory=dict)
    _fitted: bool = False

    # ---- offline path -------------------------------------------------
    @staticmethod
    def _grams(text: str, n: int = 4) -> List[str]:
        t = ' ' + ' '.join((text or '').lower().split()) + ' '
        return [t[i:i + n] for i in range(max(0, len(t) - n + 1))]

    def fit(self, corpus: Sequence[str]) -> 'SemanticMatcher':
        """Fit inverse document frequency on the corpus.

        Character n-grams rather than words, so 'running shoes' and 'trail
        running shoe' land near each other without a stemmer, and a product
        title that shares no whole words with the intent still scores above
        zero when it shares morphology.
        """
        df: Dict[str, int] = {}
        n = 0
        for t in corpus:
            n += 1
            for g in set(self._grams(t)):
                df[g] = df.get(g, 0) + 1
        self._idf = {g: math.log((n + 1) / (c + 1)) + 1.0 for g, c in df.items()}
        self._fitted = True
        return self

    def _lexical_vec(self, text: str) -> Dict[str, float]:
        tf: Dict[str, float] = {}
        for g in self._grams(text):
            tf[g] = tf.get(g, 0.0) + 1.0
        return {g: v * self._idf.get(g, 1.0) for g, v in tf.items()}

    @staticmethod
    def _sparse_cos(a: Dict[str, float], b: Dict[str, float]) -> float:
        if not a or not b:
            return 0.0
        small, large = (a, b) if len(a) < len(b) else (b, a)
        num = sum(v * large.get(k, 0.0) for k, v in small.items())
        na = math.sqrt(sum(v * v for v in a.values()))
        nb = math.sqrt(sum(v * v for v in b.values()))
        return num / (na * nb) if na and nb else 0.0

    # ---- online path --------------------------------------------------
    def load_embeddings(self, vectors: Dict[str, List[float]]) -> 'SemanticMatcher':
        """Adopt precomputed embeddings, keyed by exact text.

        Written by scripts/pregenerate.py and committed under artifacts/genai/,
        so a clone with no API key still gets the stronger path for every string
        the simulator produces.
        """
        if vectors:
            self._vec = vectors
            self.mode = 'embed'
        return self

    # ---- scoring ------------------------------------------------------
    def similarity(self, intent: str, item: str) -> float:
        if self.mode == 'embed':
            a, b = self._vec.get(intent), self._vec.get(item)
            if a and b:
                return _cosine(a, b)
            # fall through rather than return a wrong number for an unseen string
        if not self._fitted:
            return 0.5
        return self._sparse_cos(self._lexical_vec(intent), self._lexical_vec(item))

    def features(self, intent: str, item: str,
                 agent_mean: Optional[float] = None) -> Dict[str, float]:
        """The semantic block for Head C.

        `intent_margin` matters as much as the raw similarity. Agents differ in
        how literally they interpret an instruction, so a fixed threshold on
        similarity punishes the loose ones. Measuring against this agent's own
        running mean asks the better question: is this purchase unusual *for
        this agent*, given how it normally reads its instructions.
        """
        s = self.similarity(intent, item)
        out = {
            'intent_similarity': s,
            'intent_sim_low': 1.0 if s < 0.35 else 0.0,
            'semantic_mode': 1.0 if self.mode == 'embed' else 0.0,
        }
        if agent_mean is not None:
            out['intent_margin'] = s - agent_mean
        return out


# ---------------------------------------------------------------------------
#: What a merchant category actually sells. Used to give an execution an item
#: description, so the semantic comparison has something to compare against.
ITEM_CATALOG: Dict[str, List[str]] = {
    '5411': ['rice dal and cooking oil', 'weekly vegetables and milk',
             'atta sugar and tea', 'household groceries basket'],
    '5812': ['dinner for two', 'family meal delivery', 'lunch thali order'],
    '5814': ['burger meal combo', 'pizza and sides'],
    '4121': ['airport transfer 32 km', 'city cab ride', 'outstation drop'],
    '5999': ['assorted gift hamper', 'stationery and desk items',
             'birthday present set'],
    '5732': ['wireless earbuds', 'electric kettle 1.7L', 'bluetooth speaker',
             'phone charging adapter'],
    '5661': ['road running shoes size 9', 'trail running shoe',
             'cushioned trainers', 'sports socks and insoles'],
    '5941': ['yoga mat and blocks', 'badminton racket', 'gym gloves'],
    '4900': ['broadband plan renewal', 'electricity bill payment'],
    '6011': ['cash withdrawal', 'account funding'],
    '5541': ['fuel top up', 'petrol fill'],
    '4814': ['prepaid mobile recharge', 'data pack top up'],
}

#: What a hijacked agent buys instead. Liquid, resaleable, and — crucially —
#: still plausible inside the mandate, which is why the hard checks pass.
DIVERTED_ITEMS: List[str] = [
    'digital gift card 5000',
    'prepaid stored value voucher',
    'electronics accessory bundle',
    'general merchandise voucher',
    'open loop prepaid card',
]


def item_for(mcc: str, rng) -> str:
    pool = ITEM_CATALOG.get(mcc)
    return rng.choice(pool) if pool else 'general purchase'
