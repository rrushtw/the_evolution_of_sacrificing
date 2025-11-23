import random
from base_strategy import BaseStrategy
from definitions import Action, Reputation


class Sheriff(BaseStrategy):
    @property
    def name(self) -> str:
        return "Sheriff"

    @property
    def color(self) -> tuple:
        # 警徽金 / 銅色
        return (184, 134, 11)

    def decide(self, opponent: BaseStrategy) -> Action:
        # 1. 族群團結
        if type(self) is type(opponent):
            return Action.NOTIFY

        # 2. 絕對過濾：聲譽太差的 (EVIL/NEUTRAL)，直接不理
        # 這可以過濾掉 Xenophobe 和 Cheater
        if opponent.reputation <= Reputation.NEUTRAL:
            return Action.RUN

        # 3. 行為審查
        if opponent.last_action == Action.NOTIFY:
            return Action.NOTIFY

        else:  # opponent.last_action == RUN
            # 即使你聲譽是 LEGEND，你剛剛 RUN 了，我也不會因為你聲譽高就原諒你
            # (這是剋制政客的關鍵)

            # 但為了抗雜訊，我給予極小的機率 (5%) 原諒
            if random.random() < 0.05:
                return Action.NOTIFY

            return Action.RUN
