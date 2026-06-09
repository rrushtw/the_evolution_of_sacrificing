"""
共用 fixture 與探針策略。

核心是 `clean_config`(autouse):`GameConfig` 在 import 時就把環境變數(含 container 的
`.env`,可能帶 `ASSORTMENT=0.6`、`INSTITUTION_STRENGTH` 等)烙進 class 屬性。測試若靠「程式碼預設值」
就會被 `.env` 污染而飄移。此 fixture 在每個測試前用 monkeypatch 把測試會依賴的旋鈕還原成
`definitions.py` 的出廠值,測後自動復原 —— 不論宿主 / container / 任何 `.env` 都得到同一基準。
"""
import random

import pytest

from definitions import Action, GameConfig, OpponentView, Reputation
from base_strategy import BaseStrategy


# definitions.py 的「出廠值」(= 無任何 ENV 覆寫時的預設)。集中於此,測試一律以此為基準。
_FACTORY = {
    "BLIND_REPUTATION": False,
    "BLIND_PRIVATE": False,
    "INSTITUTION_STRENGTH": 0.0,
    "INSTITUTION_FALSE_POSITIVE": 0.0,
    "ASSORTMENT": 0.0,
    "INTERNAL_NOISE_RATE": 0.0,   # 測 payoff/reputation 時要可預測,關掉口誤翻轉
    "NOISE_RATE": 0.0,
    "PROB_SPOT_DANGER": 0.5,
    "CAPITAL_BASELINE": 5.0,
    "CAPITAL_RECOVERY": 0.1,
    "SURVIVAL_SPOTTER_NOTIFY": 0.9,
    "SURVIVAL_SPOTTER_RUN": 1.0,
    "SURVIVAL_LISTENER_WARNED": 1.0,
    "SURVIVAL_LISTENER_IGNORANT": 0.05,
    "AVG_DEGREE": 6,
    "CHURN_RATE": 0.05,
}


@pytest.fixture(autouse=True)
def clean_config(monkeypatch):
    """每個測試前把 GameConfig 還原成出廠值,中和 .env 污染(測後 monkeypatch 自動復原)。"""
    for key, value in _FACTORY.items():
        monkeypatch.setattr(GameConfig, key, value)
    # 全域 RNG 也給個固定起點,避免測試間互相干擾(個別測試要重現時自行 re-seed)。
    random.seed(0)
    yield


# ----------------------------------------------------------------------
# 確定性探針策略 —— 不依賴隨機 decide,讓不變量可被精準斷言
# ----------------------------------------------------------------------

class AlwaysNotify(BaseStrategy):
    """恆 NOTIFY。"""
    @property
    def name(self) -> str:
        return "AlwaysNotify"

    @property
    def color(self) -> tuple:
        return (0, 255, 0)

    def decide(self, view: OpponentView) -> Action:
        return Action.NOTIFY


class AlwaysRun(BaseStrategy):
    """恆 RUN。"""
    @property
    def name(self) -> str:
        return "AlwaysRun"

    @property
    def color(self) -> tuple:
        return (255, 0, 0)

    def decide(self, view: OpponentView) -> Action:
        return Action.RUN


class SpyStrategy(BaseStrategy):
    """探針:記下 decide() 實際收到的 (reputation, history),供 knockout 測試檢查傳入值。"""
    @property
    def name(self) -> str:
        return "Spy"

    @property
    def color(self) -> tuple:
        return (128, 128, 128)

    def decide(self, view: OpponentView) -> Action:
        self.seen_reputation = view.reputation
        self.seen_history = view.history
        return Action.NOTIFY


@pytest.fixture
def notify_agent():
    return AlwaysNotify()


@pytest.fixture
def run_agent():
    return AlwaysRun()
