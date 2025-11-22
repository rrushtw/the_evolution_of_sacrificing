# strategies/chaotic.py
import random
from base_strategy import BaseStrategy
from definitions import Action


class Chaotic(BaseStrategy):
    @property
    def name(self) -> str:
        return "Chaotic"

    @property
    def color(self) -> tuple:
        # 紫色: 代表神秘、混沌
        return (148, 0, 211)

    def decide(self, opponent_strategy_type):
        # 擲硬幣
        if random.random() < 0.5:
            return Action.NOTIFY
        return Action.RUN
