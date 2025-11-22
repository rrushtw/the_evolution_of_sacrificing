from typing import Type
from base_strategy import BaseStrategy
from definitions import Action
from strategies.altruist import Altruist


class Selective(BaseStrategy):
    @property
    def name(self) -> str:
        return "Selective"

    @property
    def color(self) -> tuple:
        # 藍色
        return (0, 0, 255)

    def decide(self, opponent_strategy_type: Type[BaseStrategy]) -> Action:
        # 【正面表列機制】
        # 1. 判斷是否是同類 (Kin Selection)
        #    直接比較 class type 是否相同，或者是否是子類別
        if issubclass(opponent_strategy_type, Selective):
            return Action.NOTIFY

        # 2. 判斷是否是已知的好人 (Reciprocal Altruism)
        #    我知道 Altruist 是無害且有益的
        if issubclass(opponent_strategy_type, Altruist):
            return Action.NOTIFY

        # 3. 對於所有「未知」或「非白名單」的策略 (Cheater, Random, etc.)
        #    預設採取防禦姿態
        return Action.RUN
