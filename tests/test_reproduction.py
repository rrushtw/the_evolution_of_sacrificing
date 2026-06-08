"""不變量(7):繁衍繼承 —— spawn_offspring 只繼承 reputation;_repopulate capital 加權。"""
import simulation
from definitions import GameConfig, Reputation
from tests.conftest import AlwaysNotify, AlwaysRun


def test_spawn_offspring_inherits_only_reputation():
    parent = AlwaysNotify()
    parent.reputation = Reputation.BAD
    parent.capital = 99.0
    parent.age = 50
    parent.my_history.append({"my_action": None, "opponent_action": None})

    child = parent.spawn_offspring()

    assert type(child) is type(parent)               # 同策略型別
    assert child.reputation == Reputation.BAD         # 唯一跨代繼承的:Standing
    assert child.unique_id != parent.unique_id        # 全新身分
    assert child.my_history == []                     # 空白歷史
    assert child.capital == GameConfig.CAPITAL_BASELINE
    assert child.age == 0


def test_repopulate_returns_exactly_n_deaths():
    survivors = [AlwaysNotify() for _ in range(5)]
    newborns = simulation._repopulate(survivors, 3)
    assert len(newborns) == 3


def test_repopulate_zero_or_negative_is_empty():
    survivors = [AlwaysNotify() for _ in range(5)]
    assert simulation._repopulate(survivors, 0) == []
    assert simulation._repopulate(survivors, -2) == []


def test_repopulate_is_capital_weighted():
    # 一個富裕 AlwaysRun + 一群零資本 AlwaysNotify → 後代應幾乎全來自富裕者
    rich = AlwaysRun()
    rich.capital = 1000.0
    poor = [AlwaysNotify() for _ in range(5)]
    for p in poor:
        p.capital = 0.0
    survivors = [rich] + poor
    newborns = simulation._repopulate(survivors, 50)
    from_rich = sum(1 for c in newborns if type(c) is AlwaysRun)
    assert from_rich == 50  # capital=0 權重為零,絕不被選為親代


def test_repopulate_all_zero_capital_falls_back_to_uniform():
    # sum(weights)<=0 → 退化均勻抽樣,不應拋例外、仍回傳正確數量
    survivors = [AlwaysNotify() for _ in range(4)]
    for s in survivors:
        s.capital = 0.0
    newborns = simulation._repopulate(survivors, 10)
    assert len(newborns) == 10
