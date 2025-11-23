from base_strategy import BaseStrategy
from definitions import Action, Reputation


class Commoner(BaseStrategy):
    @property
    def name(self) -> str:
        return "Commoner"

    @property
    def color(self) -> tuple:
        # 棕色/亞麻色 (代表草根)
        return (139, 69, 19)

    def decide(self, opponent: BaseStrategy) -> Action:
        # 1. 族群團結
        if type(self) is type(opponent):
            return Action.NOTIFY

        # 2. 審查菁英 (Anti-Elite Check)
        # 如果你聲譽很高 (TRUSTED/LEGEND)，代表你是既得利益者。
        # 我會用放大鏡檢視你：只要你上一輪 RUN 了，我就認定你是政客。
        if opponent.reputation >= Reputation.TRUSTED:
            if opponent.last_action == Action.RUN:
                return Action.RUN
            # 菁英表現好，我也會幫 (但我心裡有數)
            return Action.NOTIFY

        # 3. 對待普通人 (NEUTRAL/GOOD)
        # 展現階級互助：只要你不是惡棍，我就願意冒險幫你 (類似 Samaritan)
        if opponent.reputation >= Reputation.NEUTRAL:
            # 如果對方上次幫忙，我一定幫
            if opponent.last_action == Action.NOTIFY:
                return Action.NOTIFY

            # 如果對方上次跑了，給予較高的寬恕機率 (20%)，因為普通人活著不容易
            import random
            if random.random() < 0.2:
                return Action.NOTIFY

            return Action.RUN

        # 4. 對待惡棍 (EVIL/SUSPICIOUS)
        return Action.RUN
