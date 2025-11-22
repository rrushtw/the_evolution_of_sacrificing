# strategies/imposter.py
from strategies.altruist import Altruist
from definitions import Action


class Imposter(Altruist):  # <--- 重點：繼承自 Altruist
    @property
    def name(self) -> str:
        return "Imposter"

    @property
    def color(self) -> tuple:
        # 外表看起來像綠色(Altruist)，但帶一點點黑
        return (50, 205, 50)

    def decide(self, opponent_strategy_type):
        # 雖然我繼承自 Altruist，但我骨子裡是自私的
        return Action.RUN
