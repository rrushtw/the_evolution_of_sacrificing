import random

from base_strategy import BaseStrategy
from definitions import Action, Reputation


class Chaotic(BaseStrategy):
    """50/50 coin flip every round. Baseline noise floor."""

    @property
    def name(self) -> str:
        return "Chaotic"

    @property
    def color(self) -> tuple:
        return (148, 0, 211)

    def decide(
        self,
        opponent_unique_id: str,
        opponent_reputation: Reputation,
        opponent_history: list[dict],
    ) -> Action:
        return Action.NOTIFY if random.random() < 0.5 else Action.RUN
