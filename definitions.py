import os
from enum import Enum


class Reputation(Enum):
    """
    Binary Standing Reputation (Sugden 1986).

    GOOD: presumed cooperative; refusing to help me is now bad.
    BAD : presumed defector; refusing to help me is justified.

    New agents start as GOOD (presumption of innocence).
    """
    GOOD = "Good"
    BAD = "Bad"


class Action(Enum):
    """
    Spotter's choice when danger is detected.
    """
    NOTIFY = "Notify"
    RUN = "Run"


class GameConfig:
    """
    All tunables in one place. ENV vars override defaults.
    """

    # --- Noise ---
    # External noise: signal lost / accidentally tipped off
    NOISE_RATE = float(os.getenv("NOISE_RATE", "0.01"))
    # Internal noise: slip of tongue / fumble; the engine still treats
    # the slipped action as the agent's "intent" for reputation purposes.
    INTERNAL_NOISE_RATE = float(os.getenv("INTERNAL_NOISE_RATE", "0.02"))

    # --- Alarm Call mechanics ---
    PROB_SPOT_DANGER = float(os.getenv("PROB_SPOT_DANGER", "0.5"))
    SURVIVAL_SPOTTER_NOTIFY = float(
        os.getenv("SURVIVAL_SPOTTER_NOTIFY", "0.9"))
    SURVIVAL_SPOTTER_RUN = float(os.getenv("SURVIVAL_SPOTTER_RUN", "1.0"))
    SURVIVAL_LISTENER_WARNED = float(
        os.getenv("SURVIVAL_LISTENER_WARNED", "1.0"))
    SURVIVAL_LISTENER_IGNORANT = float(
        os.getenv("SURVIVAL_LISTENER_IGNORANT", "0.05"))

    # --- Evolution (capital + overlapping generations) ---
    # Death is no longer binary: outcomes become capital gains/losses. Agents
    # are long-lived, age, and only die of old age or bankruptcy; each death is
    # replaced by an offspring of a capital-weighted parent (population stays N).
    INITIAL_COPIES = int(os.getenv("INITIAL_COPIES", "10"))
    # Each round runs ENCOUNTERS_PER_AGENT × N // 2 interactions, then everyone
    # recovers + ages, then mortality is rolled.
    ENCOUNTERS_PER_AGENT = int(os.getenv("ENCOUNTERS_PER_AGENT", "2"))
    # Capital each agent starts (and recovers toward). Outcomes are applied as
    # delta = (payoff − 1): a missed warning (IGNORANT) is a −0.95 hit, NOTIFY a
    # −0.1 cost — see _resolve_interaction. Baseline must sit well ABOVE a single
    # hit so a bad encounter HURTS but rarely bankrupts you in one round (that's
    # what makes lives long & capital graded); 5 keeps a strong influence gap.
    CAPITAL_BASELINE = float(os.getenv("CAPITAL_BASELINE", "5.0"))
    # Fraction of the gap to baseline that heals each round. Lower = a loss
    # lingers longer = a longer 'shadow of the future' (reciprocity pays more).
    CAPITAL_RECOVERY = float(os.getenv("CAPITAL_RECOVERY", "0.1"))
    # Mortality per round = BASE_DEATH + AGE_DEATH × age (clamped to 1), plus
    # instant death on bankruptcy (capital ≤ 0). Tuned for long-but-finite lives.
    BASE_DEATH = float(os.getenv("BASE_DEATH", "0.002"))
    AGE_DEATH = float(os.getenv("AGE_DEATH", "0.0010"))
    # ASSORTMENT: when an agent forms a NEW tie, P(it prefers a same-Standing
    # partner). 0 = unbiased rewiring; 1 = GOOD only befriends GOOD.
    ASSORTMENT = float(os.getenv("ASSORTMENT", "0.0"))
    MAX_GENERATIONS = int(os.getenv("MAX_GENERATIONS", "3000"))

    # --- Social network (Stage B) ---
    # Agents sit on a graph and interact with their contacts → repeated
    # encounters → private history. AVG_DEGREE = how many contacts each holds.
    AVG_DEGREE = int(os.getenv("AVG_DEGREE", "6"))
    # CHURN_RATE = per-round probability each tie reshuffles. The village↔metropolis
    # dial: 0 = a fixed village (you keep contacts for life → private history rules);
    # →1 = a churning metropolis (you rarely re-meet → reputation rules). Independent
    # of this, EXPLOITATION (running on a GOOD partner) always breaks that tie and
    # the exploiter flees to a new circle — so a hit-and-run escapes private revenge.
    CHURN_RATE = float(os.getenv("CHURN_RATE", "0.05"))

    # --- Knockout flags (for private-vs-public causal experiments) ---
    # BLIND_REPUTATION: deciders always see opponents as GOOD (reputation ablated).
    BLIND_REPUTATION = os.getenv("BLIND_REPUTATION", "0") == "1"
    # BLIND_PRIVATE: per-opponent memory is never recorded (private history ablated).
    BLIND_PRIVATE = os.getenv("BLIND_PRIVATE", "0") == "1"

    # --- Stability ---
    # Stable = every species' count has fluctuated by ≤ TOLERANCE for the
    # last THRESHOLD generations. (Species-set-only stability is too lax —
    # counts can still swing wildly while the set is unchanged.)
    STABILITY_THRESHOLD = int(os.getenv("STABILITY_THRESHOLD", "100"))
    STABILITY_TOLERANCE = int(os.getenv("STABILITY_TOLERANCE", "5"))
