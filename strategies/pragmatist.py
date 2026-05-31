from base_strategy import BaseStrategy
from definitions import Action, Reputation


class Pragmatist(BaseStrategy):
    """
    Public Tit-for-Tat: mirror the opponent's MOST RECENT public action,
    regardless of who they did it to. Reputation-blind.

    Differs from Simpleton: Simpleton uses private history with this
    opponent only; Pragmatist uses the opponent's globally-visible log.
    """

    @property
    def name(self) -> str:
        return "Pragmatist"

    @property
    def color(self) -> tuple:
        return (0, 128, 128)

    def decide(
        self,
        opponent_unique_id: str,
        opponent_reputation: Reputation,
        opponent_history: list[dict],
    ) -> Action:
        for r in reversed(opponent_history):
            their_act = r.get("my_action")
            if their_act is not None:
                return their_act

        return Action.NOTIFY
