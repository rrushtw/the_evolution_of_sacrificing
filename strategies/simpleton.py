from base_strategy import BaseStrategy
from definitions import Action


class Simpleton(BaseStrategy):
    @property
    def name(self) -> str:
        return "Simpleton"

    @property
    def color(self) -> tuple:
        # 褐色/卡其色 (代表土地、樸實)
        return (210, 180, 140)  # Tan

    def decide(self, opponent: BaseStrategy) -> Action:
        # 1. 同類互助 (基本生存)
        if type(self) is type(opponent):
            return Action.NOTIFY

        # 2. 絕對的以牙還牙 (Tit-for-Tat)
        # 我完全不看你的 Reputation (無視社會地位)
        # 我只看你上一輪做了什麼

        if opponent.last_action == Action.NOTIFY:
            return Action.NOTIFY

        # 如果你是 RUN，不管你聲譽多高，我都不救
        return Action.RUN
