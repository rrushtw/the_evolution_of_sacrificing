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

    def decide(self, opponent_strategy_type):
        # 只救自己人 (嚴格檢查)
        if opponent_strategy_type == Xenophobe:  # 或是 type(self)
            return Action.NOTIFY
        return Action.RUN
