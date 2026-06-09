import os

from base_strategy import BaseStrategy
from definitions import Action, OpponentView


class Desperado(BaseStrategy):
    """
    背水一戰 — gamble when you are close to ruin.

    Reads its OWN Phase 2.5 capital and defects (RUN) only when within
    DESPERATE_DISTANCE of bankruptcy — a high-risk grab to claw back, accepting
    the BAD Standing as the price of survival; above that it cooperates (NOTIFY).
    A model of how scarcity itself breeds defection, independent of the opponent.

    'Desperate' is anchored to the **bankruptcy boundary** (ruin = capital ≤ 0),
    NOT the aspirational CAPITAL_BASELINE: in this economy realised capital sits
    far below baseline, so a baseline-relative threshold would keep it permanently
    'desperate' (≡ a constant defector) and never test the two-regime idea. The
    distance is env-tunable (DESPERADO_THRESHOLD) so we can sweep it rather than
    hand-pick one number.

    Lives in strategies/experimental/ so it is NOT auto-discovered by
    load_all_strategies() — see Sycophant for the isolation rationale.
    """

    # RUN when capital is within this distance of ruin (0). Env-tunable for sweeps.
    DESPERATE_DISTANCE = float(os.getenv("DESPERADO_THRESHOLD", "0.3"))

    @property
    def name(self) -> str:
        return "Desperado"

    @property
    def color(self) -> tuple:
        return (199, 21, 133)

    def decide(self, view: OpponentView) -> Action:
        if self.capital < self.DESPERATE_DISTANCE:
            return Action.RUN         # within reach of ruin — gamble for capital
        return Action.NOTIFY          # solvent — play nice
