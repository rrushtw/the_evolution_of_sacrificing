from typing import Type
from base_strategy import BaseStrategy
from definitions import Action
from strategies.cheater import Cheater


class Grudger(BaseStrategy):
    @property
    def name(self) -> str:
        return "Grudger"

    @property
    def color(self) -> tuple:
        # 黃色: 代表警示，平時溫暖(像太陽/綠色)，但有時會變臉
        return (255, 215, 0)

    def decide(self, opponent_strategy_type: Type[BaseStrategy]) -> Action:
        # 【負面表列機制 (Blacklist)】

        # 1. 識別壞人：如果是已知的壞蛋 (Cheater)，我就報復 (不幫忙)
        if issubclass(opponent_strategy_type, Cheater):
            return Action.RUN

        # 2. 對於其他所有未知或已知的策略 (Altruist, Selective, Random...)
        #    預設選擇「信任」與「合作」
        return Action.NOTIFY
