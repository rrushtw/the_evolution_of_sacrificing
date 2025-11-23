from abc import ABC, abstractmethod
from typing import Tuple
from definitions import Action, GameConfig, Reputation

# ==========================================
# 策略介面 (Strategy Abstract Base Class)
# ==========================================


class BaseStrategy(ABC):
    """
    所有策略的 base class
    """

    def __init__(self):
        # 記錄上一輪我做了什麼
        self.last_action: Action = Action.NOTIFY

        # 信譽分數：合作加分，背叛扣分
        self.reputation: int = 0

    @property
    @abstractmethod
    def name(self) -> str:
        """策略顯示名稱 (e.g., 'Altruist')"""
        pass

    @property
    @abstractmethod
    def color(self) -> Tuple[int, int, int]:
        """策略代表顏色 (R, G, B)，用於地圖視覺化"""
        pass

    @abstractmethod
    def decide(self, opponent: 'BaseStrategy') -> Action:
        """
        核心決策邏輯。

        Args:
            pponent: 對手的【實例 (Instance)】。

        Returns:
            Action.NOTIFY or Action.RUN
        """
        pass

    def update_history(self, action: Action, opponent: 'BaseStrategy'):
        """
        每輪結束後，更新自己的履歷。
        修正邏輯：只有幫助「非同類」時，才增加聲譽。
        """
        self.last_action = action

        if action == Action.NOTIFY:
            # 判斷是否為同類 (Exact Type Match)
            # 如果我是 Xenophobe，你是 Xenophobe，這只是本份，不加分。
            # 如果我是 Altruist，你是 Cheater，我還救你，這就是聖人，加分。
            if type(self) is type(opponent):
                # 同類互助：視為本能/義務，聲譽不變 (或是只加一點點)
                pass
            elif self.reputation < GameConfig.MAX_REPUTATION:
                # 跨種族互助：視為真正的利他，聲譽上升
                self.reputation += 1

        elif action == Action.RUN and self.reputation > GameConfig.MIN_REPUTATION:
            # 只要逃跑，無論對象是誰，通常都會被視為不可靠
            if self.reputation >= Reputation.TRUSTED:
                self.reputation = Reputation.SUSPICIOUS
            else:
                self.reputation -= 1

    def __str__(self):
        return self.name
