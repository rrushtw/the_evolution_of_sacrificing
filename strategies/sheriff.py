from base_strategy import BaseStrategy
from definitions import Action, Reputation


class Sheriff(BaseStrategy):
    """
    Pure Standing executor: NOTIFY anyone currently GOOD,
    RUN against anyone currently BAD. Reputation is the only input.
    """

    @property
    def name(self) -> str:
        return "Sheriff"

    @property
    def color(self) -> tuple:
        return (184, 134, 11)

    def decide(
        self,
        opponent_unique_id: str,
        opponent_reputation: Reputation,
        opponent_history: list[dict],
    ) -> Action:
        if opponent_reputation == Reputation.GOOD:
            return Action.NOTIFY
        return Action.RUN
