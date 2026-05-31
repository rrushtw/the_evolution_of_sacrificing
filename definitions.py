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

    # --- Evolution (well-mixed; Axelrod-style) ---
    # Defaults sized for ~1s/generation on a laptop with 10 strategies.
    # Crank up via env vars for more statistical power.
    INITIAL_COPIES = int(os.getenv("INITIAL_COPIES", "10"))
    KILL_COUNT = int(os.getenv("KILL_COUNT", "5"))
    ROUNDS_PER_GAME = int(os.getenv("ROUNDS_PER_GAME", "20"))
    AVG_MATCHES_PER_STRATEGY = int(
        os.getenv("AVG_MATCHES_PER_STRATEGY", "20"))
    MAX_GENERATIONS = int(os.getenv("MAX_GENERATIONS", "3000"))

    # --- Stability ---
    # Stable = every species' count has fluctuated by ≤ TOLERANCE for the
    # last THRESHOLD generations. (Species-set-only stability is too lax —
    # counts can still swing wildly while the set is unchanged.)
    STABILITY_THRESHOLD = int(os.getenv("STABILITY_THRESHOLD", "100"))
    STABILITY_TOLERANCE = int(os.getenv("STABILITY_TOLERANCE", "5"))
