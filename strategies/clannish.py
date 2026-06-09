from base_strategy import BaseStrategy
from definitions import Action, OpponentView


class Clannish(BaseStrategy):
    """
    Trust the familiar, exploit the stranger.

    NOTIFY anyone this agent already shares private history with (a known
    contact); RUN on anyone it has never met. In a stable village it quickly
    turns its small circle into mutual aid (a model neighbour); in a churning
    metropolis, where almost everyone is a stranger, the same rule makes it a
    serial exploiter. The cleanest single probe of the private/public divide:
    its niceness is entirely a function of how often you re-meet.
    """

    @property
    def name(self) -> str:
        return "Clannish"

    @property
    def color(self) -> tuple:
        return (160, 82, 45)

    def decide(self, view: OpponentView) -> Action:
        if self.private_history_with(view.unique_id):
            return Action.NOTIFY      # a known face — help them
        return Action.RUN             # a stranger — don't risk it
