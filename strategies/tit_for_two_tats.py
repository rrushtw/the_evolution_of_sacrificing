from base_strategy import BaseStrategy
from definitions import Action, OpponentView


class TitForTwoTats(BaseStrategy):
    """
    Forgiving private TFT: retaliate only after the SAME opponent has
    RUN against me twice in a row. One RUN is forgiven as possible noise.

    Tests noise tolerance — Simpleton retaliates immediately, this one
    waits for confirmation. In a noisy world (internal slip 2%, external
    1%), instant retaliation can cascade into mutual-defection spirals.
    """

    @property
    def name(self) -> str:
        return "TitForTwoTats"

    @property
    def color(self) -> tuple:
        return (70, 130, 180)

    def decide(self, view: OpponentView) -> Action:
        my_records = self.private_history_with(view.unique_id)

        # Collect opponent's most recent two actions toward me.
        opp_actions: list[Action] = []
        for r in reversed(my_records):
            act = r.get("opponent_action")
            if act is not None:
                opp_actions.append(act)
                if len(opp_actions) == 2:
                    break

        if len(opp_actions) == 2 and all(a == Action.RUN for a in opp_actions):
            return Action.RUN

        return Action.NOTIFY
