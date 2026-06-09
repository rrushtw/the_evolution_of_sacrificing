from base_strategy import BaseStrategy
from definitions import Action, OpponentView


class Pavlov(BaseStrategy):
    """
    Win-Stay, Lose-Shift (Nowak & Sigmund 1993).

    Adapted to the Alarm Call game by using the action-pair as the
    outcome signal (since survival probability of the spotter depends
    only on their own action, raw survival isn't a useful win/lose hint):

      Last (mine, opp's) toward this opponent →   Verdict   → This time
      ----------------------------------------    --------    ---------
      (NOTIFY, NOTIFY)  mutual cooperation         WIN          NOTIFY
      (NOTIFY, RUN)     I was suckered             LOSE         RUN
      (RUN,    NOTIFY)  I escaped while they helped WIN          RUN
      (RUN,    RUN)     mutual defection           LOSE         NOTIFY

    First encounter: NOTIFY (presumption of cooperation).
    """

    @property
    def name(self) -> str:
        return "Pavlov"

    @property
    def color(self) -> tuple:
        return (255, 105, 180)

    def decide(self, view: OpponentView) -> Action:
        my_records = self.private_history_with(view.unique_id)

        my_last = None
        for r in reversed(my_records):
            if r.get("my_action") is not None:
                my_last = r["my_action"]
                break

        if my_last is None:
            return Action.NOTIFY

        opp_last = None
        for r in reversed(my_records):
            if r.get("opponent_action") is not None:
                opp_last = r["opponent_action"]
                break

        if my_last == Action.NOTIFY:
            if opp_last == Action.RUN:
                return Action.RUN
            return Action.NOTIFY
        else:
            if opp_last == Action.RUN:
                return Action.NOTIFY
            return Action.RUN
