"""不變量(2):資本動態 —— apply_capital / recover / is_bankrupt。"""
import pytest

from definitions import GameConfig
from tests.conftest import AlwaysNotify


def test_apply_capital_is_linear_accumulation():
    a = AlwaysNotify()
    start = a.capital
    a.apply_capital(-0.95)
    a.apply_capital(+0.5)
    assert a.capital == pytest.approx(start - 0.95 + 0.5)


def test_recover_drifts_toward_baseline_from_below():
    a = AlwaysNotify()
    a.capital = 1.0
    a.recover()
    expected = 1.0 + GameConfig.CAPITAL_RECOVERY * (GameConfig.CAPITAL_BASELINE - 1.0)
    assert a.capital == pytest.approx(expected)
    assert a.capital > 1.0  # 低於 baseline → 回升


def test_recover_drifts_toward_baseline_from_above():
    a = AlwaysNotify()
    a.capital = 9.0
    a.recover()
    expected = 9.0 + GameConfig.CAPITAL_RECOVERY * (GameConfig.CAPITAL_BASELINE - 9.0)
    assert a.capital == pytest.approx(expected)
    assert a.capital < 9.0  # 高於 baseline → 回落


def test_recover_is_fixedpoint_at_baseline():
    a = AlwaysNotify()
    a.capital = GameConfig.CAPITAL_BASELINE
    a.recover()
    assert a.capital == pytest.approx(GameConfig.CAPITAL_BASELINE)


def test_is_bankrupt_boundary():
    a = AlwaysNotify()
    a.capital = 0.01
    assert a.is_bankrupt() is False
    a.capital = 0.0          # 恰 0 視為破產(capital <= 0)
    assert a.is_bankrupt() is True
    a.capital = -1.0
    assert a.is_bankrupt() is True
