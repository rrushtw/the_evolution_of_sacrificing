from base_strategy import BaseStrategy
from definitions import Action, Reputation


class Politician(BaseStrategy):
    """
    Sucker hunter: NOTIFY against cautious opponents (to remain palatable),
    RUN against opponents whose public log is dominated by NOTIFY — these
    are the "suckers" who will keep helping even after I exploit them.

    Under Standing rules this strategy quickly turns BAD, but it can still
    parasitize unconditional cooperators like Altruist whose decision does
    not depend on the Politician's reputation.
    """

    SUCKER_RATIO = 2.0  # NOTIFY-count must exceed RUN-count by this factor

    @property
    def name(self) -> str:
        return "Politician"

    @property
    def color(self) -> tuple:
        return (128, 0, 128)

    def decide(
        self,
        opponent_unique_id: str,
        opponent_reputation: Reputation,
        opponent_history: list[dict],
    ) -> Action:
        notify_count = 0
        run_count = 0
        for r in opponent_history:
            act = r.get("my_action")
            if act == Action.NOTIFY:
                notify_count += 1
            elif act == Action.RUN:
                run_count += 1

        if notify_count == 0 and run_count == 0:
            return Action.NOTIFY

        if notify_count > run_count * self.SUCKER_RATIO:
            return Action.RUN

        return Action.NOTIFY
