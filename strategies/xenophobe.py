# strategies/xenophobe.py
from base_strategy import BaseStrategy
from definitions import Action


class Xenophobe(BaseStrategy):
    @property
    def name(self) -> str:
        return "Xenophobe"

    @property
    def color(self) -> tuple:
        # 深橙色: 警戒色
        return (255, 140, 0)

    def decide(self, opponent: 'BaseStrategy') -> Action:
        # 只救自己人 (嚴格檢查)
        if isinstance(opponent, Xenophobe):
            return Action.NOTIFY  # 合作

        # 對於任何非同類，一律逃跑
        return Action.RUN
