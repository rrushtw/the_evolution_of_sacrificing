import random
from base_strategy import BaseStrategy
from definitions import Action, Reputation


class Samaritan(BaseStrategy):
    @property
    def name(self) -> str:
        return "Samaritan"

    @property
    def color(self) -> tuple:
        # 淺藍色 / 天藍色 (代表純潔與包容)
        return (135, 206, 235)

    def decide(self, opponent: BaseStrategy) -> Action:
        # 1. 族群團結
        if type(self) is type(opponent):
            return Action.NOTIFY

        # 2. 如果對方是好人 (NOTIFY)，我就幫
        # 我完全不看 Reputation，政客的高聲譽對我無效
        if opponent.last_action == Action.NOTIFY:
            return Action.NOTIFY

        # 3. 如果對方是壞人 (RUN)...
        if opponent.last_action == Action.RUN:
            # 檢查對方是否為絕對惡棍 (Cheater/Xenophobe)
            # 如果對方聲譽極低 (EVIL/SUSPICIOUS)，不值得浪費寬恕
            if opponent.reputation <= Reputation.SUSPICIOUS:
                return Action.RUN

            # 【核心機制：隨機寬恕】
            # 即使對方背叛了 (可能是政客收割，也可能是雜訊)，
            # 我給予 10% 的機會原諒他，試圖重啟合作。
            # 這能有效防止好人之間的「誤會連鎖」，但又不會像 Prophet 那樣被政客無限吸血。
            if random.random() < 0.10:
                return Action.NOTIFY

            # 90% 的情況下，我選擇報復 (自保)
            return Action.RUN

        return Action.RUN
