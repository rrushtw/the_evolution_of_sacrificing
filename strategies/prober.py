from base_strategy import BaseStrategy
from definitions import Action, Reputation


class Prober(BaseStrategy):
    """
    Probe-and-adapt predator.

    First 3 times I'm the spotter against this specific opponent → RUN
    (deliberate exploitation probe). After the probe phase, inspect what
    that opponent has done back to me:

      - Any RUN against me → "this one punishes" → switch to TFT mode
        (mirror their last action toward me).
      - Never punished     → "this one is exploitable" → keep running.

    Tests whether the population can defend itself against active
    predators that target the most cooperative members.
    """

    PROBE_ROUNDS = 3

    @property
    def name(self) -> str:
        return "Prober"

    @property
    def color(self) -> tuple:
        return (218, 165, 32)

    def decide(
        self,
        opponent_unique_id: str,
        opponent_reputation: Reputation,
        opponent_history: list[dict],
    ) -> Action:
        my_records = self.private_history_with(opponent_unique_id)

        my_spotter_count = sum(
            1 for r in my_records if r.get("my_action") is not None)

        if my_spotter_count < self.PROBE_ROUNDS:
            return Action.RUN

        opp_has_retaliated = any(
            r.get("opponent_action") == Action.RUN for r in my_records)

        if not opp_has_retaliated:
            return Action.RUN

        # They punish — switch to TFT toward this opponent.
        for r in reversed(my_records):
            opp_act = r.get("opponent_action")
            if opp_act is not None:
                return opp_act

        return Action.NOTIFY
