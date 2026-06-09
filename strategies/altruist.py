from base_strategy import BaseStrategy
from definitions import Action, OpponentView


class Altruist(BaseStrategy):
    """Unconditional cooperator. NOTIFY no matter what."""

    @property
    def name(self) -> str:
        return "Altruist"

    @property
    def color(self) -> tuple:
        return (0, 255, 0)

    def decide(self, view: OpponentView) -> Action:
        return Action.NOTIFY
