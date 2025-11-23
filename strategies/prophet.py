from base_strategy import BaseStrategy
from definitions import Action, Reputation


class Prophet(BaseStrategy):
    @property
    def name(self) -> str:
        return "Prophet"

    @property
    def color(self) -> tuple:
        # 金色 (代表智慧、光芒、高位階)
        return (255, 215, 0)

    def decide(self, opponent: BaseStrategy) -> Action:
        # 1. 同類互助
        if type(self) is type(opponent):
            return Action.NOTIFY

        # 2. 寬恕機制 (Forgiveness)
        # 不檢查 opponent.last_action (原諒一時的過錯)
        # 只檢查 opponent.reputation (看重一生的修為)
        if opponent.reputation >= Reputation.TRUSTED:
            return Action.NOTIFY

        # 對於普通人或壞人，保持冷漠
        return Action.RUN
