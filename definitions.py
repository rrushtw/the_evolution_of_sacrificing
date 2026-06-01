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

    # --- Evolution (well-mixed; death-based selection) ---
    # A generation is a brutal one-shot tournament: agents play until the
    # living pool is culled down to the survival floor (a single bad
    # encounter can kill), then the survivors breed back up to N and each
    # newborn inherits only its parent's Standing.
    INITIAL_COPIES = int(os.getenv("INITIAL_COPIES", "10"))
    # Survival floor: stop the generation once this fraction of N is still
    # alive. It caps per-generation mortality (default 0.5 = at most half die)
    # so the population persists across generations instead of collapsing.
    # Lower = crueler environment.
    SURVIVAL_FLOOR_FRAC = float(os.getenv("SURVIVAL_FLOOR_FRAC", "0.5"))
    # Safety cap on interactions per generation (as a multiple of N), so a
    # placid, low-death generation that never reaches the floor still ends.
    MAX_ENCOUNTERS_PER_AGENT = int(os.getenv("MAX_ENCOUNTERS_PER_AGENT", "4"))
    # Reputation-biased assortment: with this probability each encounter is
    # drawn from partners of the SAME Standing as the first agent (homophily /
    # clustering), else fully random. 0.0 = the well-mixed baseline; 1.0 =
    # GOOD only ever meets GOOD. Lets cooperators cluster and warn each other —
    # the well-mixed stand-in for spatial/network reciprocity.
    ASSORTMENT = float(os.getenv("ASSORTMENT", "0.0"))
    MAX_GENERATIONS = int(os.getenv("MAX_GENERATIONS", "3000"))

    # --- Stability ---
    # Stable = every species' count has fluctuated by ≤ TOLERANCE for the
    # last THRESHOLD generations. (Species-set-only stability is too lax —
    # counts can still swing wildly while the set is unchanged.)
    STABILITY_THRESHOLD = int(os.getenv("STABILITY_THRESHOLD", "100"))
    STABILITY_TOLERANCE = int(os.getenv("STABILITY_TOLERANCE", "5"))
