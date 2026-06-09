from base_strategy import BaseStrategy
from definitions import Action, GameConfig, OpponentView


class Desperado(BaseStrategy):
    """
    背水一戰 — gamble when you have nothing left to lose.

    Reads its OWN Phase 2.5 capital: while comfortably above ruin it cooperates
    (NOTIFY), but once capital sinks below DESPERATE_FRACTION of the baseline it
    flips to RUN — a high-risk grab to claw back, accepting the BAD Standing as
    the price of survival. A model of how scarcity itself breeds defection,
    independent of who the opponent is.

    Lives in strategies/experimental/ so it is NOT auto-discovered by
    load_all_strategies() — see Sycophant for the isolation rationale.
    """

    # Below this fraction of CAPITAL_BASELINE, switch to all-or-nothing RUN.
    DESPERATE_FRACTION = 0.4

    @property
    def name(self) -> str:
        return "Desperado"

    @property
    def color(self) -> tuple:
        return (199, 21, 133)

    def decide(self, view: OpponentView) -> Action:
        if self.capital < self.DESPERATE_FRACTION * GameConfig.CAPITAL_BASELINE:
            return Action.RUN         # cornered — gamble for capital
        return Action.NOTIFY          # solvent — play nice
