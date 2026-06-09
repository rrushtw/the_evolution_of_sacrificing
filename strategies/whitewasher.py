from base_strategy import BaseStrategy
from definitions import Action, OpponentView, Reputation


class Whitewasher(BaseStrategy):
    """
    A reputation launderer that attacks the public-Standing channel itself.

    While its own Standing is GOOD it RUNs — cashing in the good name to
    exploit; that turns it BAD, whereupon it NOTIFYs to scrub back to GOOD,
    then exploits again. It oscillates GOOD↔BAD, defecting whenever it has a
    clean name to spend. A direct stress-test of how robust reputation-based
    cooperation is to active gaming — most dangerous exactly where reputation
    is load-bearing (the churning metropolis).
    """

    @property
    def name(self) -> str:
        return "Whitewasher"

    @property
    def color(self) -> tuple:
        return (192, 192, 192)

    def decide(self, view: OpponentView) -> Action:
        if self.reputation == Reputation.GOOD:
            return Action.RUN         # spend the good name
        return Action.NOTIFY          # launder back to GOOD
