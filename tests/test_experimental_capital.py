"""capital-aware 策略診斷:確認它們真的「看人下菜 / 看自己下菜」(issue #7 Part B)。

這些策略住在 strategies/experimental/ 子套件,load_all_strategies() 不會自動收 → 不污染
canonical 16 策略實驗。此處直接 import 驗證 decide() 對資本的反應。
"""
from definitions import Action, GameConfig, OpponentView, Reputation
from strategies.experimental.sycophant import Sycophant
from strategies.experimental.desperado import Desperado


def _view(capital, reputation=Reputation.GOOD):
    """建一個只有 capital 有意義的 OpponentView(其餘給中性值)。"""
    return OpponentView(unique_id="opp", reputation=reputation, history=[], capital=capital)


def test_sycophant_notifies_richer_runs_poorer():
    s = Sycophant()
    s.capital = 5.0
    assert s.decide(_view(capital=9.0)) == Action.NOTIFY   # 對手較富 → 攀附
    assert s.decide(_view(capital=1.0)) == Action.RUN       # 對手較窮 → 剝削
    # 名聲 / 歷史不影響它(純看資本)
    assert s.decide(_view(capital=1.0, reputation=Reputation.GOOD)) == Action.RUN


def test_desperado_gambles_only_when_broke():
    d = Desperado()
    d.capital = 0.1 * GameConfig.CAPITAL_BASELINE          # 快破產
    assert d.decide(_view(capital=5.0)) == Action.RUN       # 背水一戰
    d.capital = GameConfig.CAPITAL_BASELINE                 # 健康
    assert d.decide(_view(capital=5.0)) == Action.NOTIFY    # 有本錢就合作
    # 對手資本不影響它(只看自己)
    d.capital = 0.1 * GameConfig.CAPITAL_BASELINE
    assert d.decide(_view(capital=0.01)) == Action.RUN
