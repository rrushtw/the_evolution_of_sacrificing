from base_strategy import BaseStrategy
from definitions import Action, Reputation


class Altruist(BaseStrategy):
    """Unconditional cooperator. NOTIFY no matter what."""

    @property
    def name(self) -> str:
        return "Altruist"

    @property
    def color(self) -> tuple:
        return (0, 255, 0)

    def decide(
        self,
        opponent_unique_id: str,
        opponent_reputation: Reputation,
        opponent_history: list[dict],
    ) -> Action:
        return Action.NOTIFY
