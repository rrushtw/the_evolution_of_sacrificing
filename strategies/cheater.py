from typing import Type
from base_strategy import BaseStrategy
from definitions import Action


class Cheater(BaseStrategy):
    """
    😈 絕對自私者：永遠選擇背叛（逃跑）。
    """

    @property
    def name(self) -> str:
        return "Cheater"

    @property
    def color(self) -> tuple:
        # 紅色: 代表危險、警告
        return (255, 0, 0)

    def decide(self, opponent_strategy_type: Type[BaseStrategy]) -> Action:
        # 總是自己逃跑，不管對方死活
        return Action.RUN
