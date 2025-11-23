from definitions import Action
from base_strategy import BaseStrategy


class Altruist(BaseStrategy):
    """
    😇 絕對犧牲者 (Altruist)
    """

    @property
    def name(self) -> str:
        return "Altruist"

    @property
    def color(self) -> tuple:
        # 綠色: 代表和平、生機
        return (0, 255, 0)

    def decide(self, opponent: BaseStrategy) -> Action:
        # 無論對方是誰，總是犧牲自己發出警報
        return Action.NOTIFY
