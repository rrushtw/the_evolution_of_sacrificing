from base_strategy import BaseStrategy
from definitions import Action, Reputation


class Cheater(BaseStrategy):
    """Unconditional defector. Always RUN."""

    @property
    def name(self) -> str:
        return "Cheater"

    @property
    def color(self) -> tuple:
        return (255, 0, 0)

    def decide(
        self,
        opponent_unique_id: str,
        opponent_reputation: Reputation,
        opponent_history: list[dict],
    ) -> Action:
        return Action.RUN
