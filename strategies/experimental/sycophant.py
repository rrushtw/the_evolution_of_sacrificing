from base_strategy import BaseStrategy
from definitions import Action, OpponentView


class Sycophant(BaseStrategy):
    """
    嫌貧愛富 — attach to the rich, exploit the poor.

    The first strategy that reads the Phase 2.5 capital channel: NOTIFY anyone
    wealthier than me (curry favour with the powerful, who are worth keeping
    sweet), RUN on anyone poorer (the weak can't retaliate and aren't worth
    the cost). Reputation- and memory-blind — wealth is its only compass.

    Lives in strategies/experimental/ so it is NOT auto-discovered by
    load_all_strategies() (pkgutil doesn't recurse) — the canonical 16-strategy
    experiments stay uncontaminated; only capital_arena.py opts it in.
    """

    @property
    def name(self) -> str:
        return "Sycophant"

    @property
    def color(self) -> tuple:
        return (60, 179, 113)

    def decide(self, view: OpponentView) -> Action:
        if view.capital > self.capital:
            return Action.NOTIFY      # richer than me — worth flattering
        return Action.RUN             # poorer than me — safe to exploit
