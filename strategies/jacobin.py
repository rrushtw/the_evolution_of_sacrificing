from base_strategy import BaseStrategy
from definitions import Action, OpponentView


class Jacobin(BaseStrategy):
    """
    Public Grim Trigger: if the opponent has EVER chosen RUN in their
    public log, refuse to help them — forever. Pure ones never tarnish.

    Differs from Sheriff (who tracks live reputation) and Grudger (private
    memory of personal grudges) — Jacobin is permanent ostracism based on
    a globally-visible single transgression.
    """

    @property
    def name(self) -> str:
        return "Jacobin"

    @property
    def color(self) -> tuple:
        return (178, 34, 34)

    def decide(self, view: OpponentView) -> Action:
        for r in view.history:
            if r.get("my_action") == Action.RUN:
                return Action.RUN

        return Action.NOTIFY
