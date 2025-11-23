from base_strategy import BaseStrategy
from definitions import Action, Reputation


class Jacobin(BaseStrategy):
    @property
    def name(self) -> str:
        return "Jacobin"

    @property
    def color(self) -> tuple:
        # 鮮血般的深紅 (代表革命與清洗)
        return (178, 34, 34)  # FireBrick

    def decide(self, opponent: BaseStrategy) -> Action:
        # 1. 永遠團結同志
        if type(self) is type(opponent):
            return Action.NOTIFY

        # 2. 【革命審判】檢查偽君子 (Hypocrite Check)
        # 如果你是高位者 (LEGEND/TRUSTED) 卻背叛
        # 這裡設定門檻為 TRUSTED (2)
        if opponent.reputation >= Reputation.TRUSTED and opponent.last_action == Action.RUN:
            return Action.RUN

        # 3. 一般情況：看行為 (類似 Meritocrat，但沒那麼菁英主義)
        # 只要你上一輪是合作的，我就合作
        if opponent.last_action == Action.NOTIFY:
            return Action.NOTIFY

        return Action.RUN
