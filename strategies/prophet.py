from base_strategy import BaseStrategy
from definitions import Action, Reputation


class Prophet(BaseStrategy):
    """
    Deep forgiver: NOTIFY anyone who has EVER shown a NOTIFY in their
    public history (one good deed redeems past sins). Newcomers also
    get NOTIFY by default. Only runs against opponents whose entire
    public log is RUN-only.
    """

    @property
    def name(self) -> str:
        return "Prophet"

    @property
    def color(self) -> tuple:
        return (255, 215, 0)

    def decide(
        self,
        opponent_unique_id: str,
        opponent_reputation: Reputation,
        opponent_history: list[dict],
    ) -> Action:
        for r in opponent_history:
            if r.get("my_action") == Action.NOTIFY:
                return Action.NOTIFY

        spotter_actions = [
            r["my_action"] for r in opponent_history
            if r.get("my_action") is not None
        ]
        if not spotter_actions:
            return Action.NOTIFY

        return Action.RUN
