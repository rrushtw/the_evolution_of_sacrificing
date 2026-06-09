from base_strategy import BaseStrategy
from definitions import Action, OpponentView


class Simpleton(BaseStrategy):
    """
    Private Tit-for-Tat: mirror what this specific opponent did to me last
    time they were the spotter. No reputation. No forgiveness.
    """

    @property
    def name(self) -> str:
        return "Simpleton"

    @property
    def color(self) -> tuple:
        return (210, 180, 140)

    def decide(self, view: OpponentView) -> Action:
        my_records = self.private_history_with(view.unique_id)

        for r in reversed(my_records):
            opp_act = r.get("opponent_action")
            if opp_act is not None:
                return opp_act

        # First encounter — give the benefit of the doubt.
        return Action.NOTIFY
