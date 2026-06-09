import random

from base_strategy import BaseStrategy
from definitions import Action, OpponentView


class Samaritan(BaseStrategy):
    """
    Private Tit-for-Tat with 10% random forgiveness. The forgiveness
    breaks mutual-defection spirals caused by noise.
    """

    FORGIVE_RATE = 0.10

    @property
    def name(self) -> str:
        return "Samaritan"

    @property
    def color(self) -> tuple:
        return (135, 206, 235)

    def decide(self, view: OpponentView) -> Action:
        my_records = self.private_history_with(view.unique_id)

        last_opp_action = None
        for r in reversed(my_records):
            opp_act = r.get("opponent_action")
            if opp_act is not None:
                last_opp_action = opp_act
                break

        if last_opp_action is None:
            return Action.NOTIFY

        if last_opp_action == Action.NOTIFY:
            return Action.NOTIFY

        if random.random() < self.FORGIVE_RATE:
            return Action.NOTIFY
        return Action.RUN
