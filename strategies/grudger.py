from base_strategy import BaseStrategy
from definitions import Action, Reputation


class Grudger(BaseStrategy):
    """
    Private Grim Trigger: if this specific opponent has EVER chosen RUN
    against me, refuse to help them — forever. Other opponents are
    untouched. The opposite of Jacobin (which uses the public log).

    Tests whether *personal* infinite punishment is more or less
    effective than *public* infinite punishment under Standing.
    """

    @property
    def name(self) -> str:
        return "Grudger"

    @property
    def color(self) -> tuple:
        return (139, 0, 0)

    def decide(
        self,
        opponent_unique_id: str,
        opponent_reputation: Reputation,
        opponent_history: list[dict],
    ) -> Action:
        my_records = self.private_history_with(opponent_unique_id)

        for r in my_records:
            if r.get("opponent_action") == Action.RUN:
                return Action.RUN

        return Action.NOTIFY
