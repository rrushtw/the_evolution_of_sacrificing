from abc import ABC, abstractmethod
from typing import Type, Tuple
from definitions import Action  # 相對路徑引用 definitions

# ==========================================
# 策略介面 (Strategy Abstract Base Class)
# ==========================================


class BaseStrategy(ABC):
    """
    所有策略的 base class
    """

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
    def decide(self, opponent_strategy_type: Type['BaseStrategy']) -> Action:
        """
        核心決策邏輯。

        Args:
            opponent_strategy_type: 對手的策略類型 (Class Type)。

        Returns:
            Action.NOTIFY or Action.RUN
        """
        pass

    def __str__(self):
        return self.name
