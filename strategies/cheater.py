from base_strategy import BaseStrategy
from definitions import Action, OpponentView


class Cheater(BaseStrategy):
    """Unconditional defector. Always RUN."""

    @property
    def name(self) -> str:
        return "Cheater"

    @property
    def color(self) -> tuple:
        return (255, 0, 0)

    def decide(self, view: OpponentView) -> Action:
        return Action.RUN
