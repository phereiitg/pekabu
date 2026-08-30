"""Controlled vocabularies. Every enum here corresponds to a real field on a
real authorisation message or a real rail primitive. Nothing invented."""
from __future__ import annotations
from enum import Enum


class Rail(str, Enum):
    CARD_PRESENT   = "R1"   # chip / contactless at a terminal
    CNP_HUMAN      = "R2"   # e-commerce, human at the keyboard
    CNP_AGENTIC    = "R3"   # delegated agent holding an agentic token
    UPI_PUSH       = "R4"   # payer initiates, device binding + PIN
    UPI_COLLECT    = "R5"   # payee requests, payer approves
    TOKEN_RECURRING= "R6"   # standing mandate, e-mandate / NACH
    WALLET_PPI     = "R7"   # prepaid instrument

    @property
    def is_pull(self) -> bool:
        """Merchant requests funds. Determines whether chargeback exists."""
        return self in (Rail.CARD_PRESENT, Rail.CNP_HUMAN,
                        Rail.CNP_AGENTIC, Rail.TOKEN_RECURRING)

    @property
    def has_chargeback(self) -> bool:
        """The single most consequential rail property. UPI has no recourse,
        so detection must happen before authorisation, not after."""
        return self.is_pull


class POSEntryMode(str, Enum):
    CHIP        = "05"
    CONTACTLESS = "07"
    MAGSTRIPE   = "90"
    KEYED       = "01"
    ECOMMERCE   = "81"
    TOKEN       = "82"   # network token, incl. agentic
    NOT_APPLIC  = "00"   # UPI and other non-card rails


class AVSResult(str, Enum):
    FULL_MATCH   = "Y"
    ZIP_ONLY     = "Z"
    ADDRESS_ONLY = "A"
    NO_MATCH     = "N"
    UNAVAILABLE  = "U"
    NOT_REQUESTED= "X"


class CVV2Result(str, Enum):
    MATCH        = "M"
    NO_MATCH     = "N"
    NOT_PROCESSED= "P"
    NOT_PRESENT  = "S"
    UNAVAILABLE  = "U"


class ThreeDSECI(str, Enum):
    """Electronic Commerce Indicator. Says whether the cardholder was
    authenticated and who carries liability. ECI 07 is the tell for
    unauthenticated CNP."""
    AUTHENTICATED       = "05"
    ATTEMPTED           = "06"
    NOT_AUTHENTICATED   = "07"
    NOT_APPLICABLE      = "00"


class ResponseCode(str, Enum):
    APPROVED          = "00"
    DO_NOT_HONOR      = "05"
    INSUFFICIENT_FUNDS= "51"
    INVALID_CARD      = "14"
    EXPIRED_CARD      = "54"
    SUSPECTED_FRAUD   = "59"
    EXCEEDS_LIMIT     = "61"
    RESTRICTED_CARD   = "62"
    SCA_REQUIRED      = "65"


class Decision(str, Enum):
    """What our own detector chose. Never present on the wire record —
    this is our output, not an input."""
    APPROVE = "approve"
    STEP_UP = "step_up"
    DECLINE = "decline"


class TrustLink(str, Enum):
    """Which link in the chain a given attack breaks. Drives F9 ablation:
    the first three are anomaly-detectable, the last three are not."""
    CREDENTIAL   = "credential"
    SESSION      = "session"
    IDENTITY     = "identity"
    MANDATE      = "mandate"
    INTENT       = "intent"
    NONE_COERCED = "none-coerced"   # every factor presented correctly
    NONE         = "none"


class MuleState(str, Enum):
    """The lifecycle that a row-independent generator provably cannot
    reproduce, because it is a trajectory rather than a marginal."""
    RECRUITED = "recruited"
    DORMANT   = "dormant"
    BURST     = "burst"
    BURNED    = "burned"


class AgentState(str, Enum):
    CLEAN      = "clean"
    AGED       = "aged"        # long benign history, the DRV-009 precondition
    COMPROMISED= "compromised"
    ROGUE      = "rogue"


class OnboardingPath(str, Enum):
    """Why 41% of suspicious VPA activity sits at payments banks and
    another 11% at aggregator-onboarded merchants."""
    DIRECT_KYC  = "direct_kyc"
    PAYMENTS_BANK = "payments_bank"    # fast, low friction
    AGGREGATOR  = "aggregator"         # merchant via PA
    UNKNOWN     = "unknown"
