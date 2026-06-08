"""不變量(3):payoff → capital delta 映射(四象限),delta == survival − 1.0。"""
import pytest

import engine
from definitions import Action, GameConfig
from tests.conftest import AlwaysNotify, AlwaysRun


# ---- 純函式:四象限 survival 機率 ----

def test_spotter_outcome_quadrants():
    assert engine._spotter_outcome(Action.NOTIFY) == GameConfig.SURVIVAL_SPOTTER_NOTIFY
    assert engine._spotter_outcome(Action.RUN) == GameConfig.SURVIVAL_SPOTTER_RUN


def test_listener_warned_when_partner_notifies_no_noise():
    # noise=0 → 警告必達 → WARNED
    assert engine._listener_outcome(Action.NOTIFY, noise=0.0) == GameConfig.SURVIVAL_LISTENER_WARNED


def test_listener_ignorant_when_nobody_spots():
    assert engine._listener_outcome(None, noise=0.0) == GameConfig.SURVIVAL_LISTENER_IGNORANT


def test_listener_ignorant_when_partner_runs_no_noise():
    # 夥伴 RUN、noise=0 → 沒注意到對方逃 → IGNORANT
    assert engine._listener_outcome(Action.RUN, noise=0.0) == GameConfig.SURVIVAL_LISTENER_IGNORANT


# ---- 整合:_resolve_interaction 把 survival 寫成 delta = survival − 1.0 ----

def test_resolve_both_notify_delta(monkeypatch):
    # 兩造都偵測到危險 → 皆為 spotter;都 NOTIFY → survival 0.9 → delta −0.1
    monkeypatch.setattr(GameConfig, "PROB_SPOT_DANGER", 1.0)
    s1, s2 = AlwaysNotify(), AlwaysNotify()
    c1, c2 = s1.capital, s2.capital
    engine._resolve_interaction(s1, s2, noise=0.0)
    assert s1.capital == pytest.approx(c1 + (GameConfig.SURVIVAL_SPOTTER_NOTIFY - 1.0))
    assert s2.capital == pytest.approx(c2 + (GameConfig.SURVIVAL_SPOTTER_NOTIFY - 1.0))


def test_resolve_both_run_delta(monkeypatch):
    # 都 RUN → spotter RUN survival 1.0 → delta 0
    monkeypatch.setattr(GameConfig, "PROB_SPOT_DANGER", 1.0)
    s1, s2 = AlwaysRun(), AlwaysRun()
    c1, c2 = s1.capital, s2.capital
    engine._resolve_interaction(s1, s2, noise=0.0)
    assert s1.capital == pytest.approx(c1 + (GameConfig.SURVIVAL_SPOTTER_RUN - 1.0))
    assert s2.capital == pytest.approx(c2 + (GameConfig.SURVIVAL_SPOTTER_RUN - 1.0))


def test_resolve_nobody_spots_delta(monkeypatch):
    # 沒人偵測到 → 皆為 listener、spotter_action=None → IGNORANT 0.05 → delta −0.95
    monkeypatch.setattr(GameConfig, "PROB_SPOT_DANGER", 0.0)
    s1, s2 = AlwaysNotify(), AlwaysNotify()
    c1, c2 = s1.capital, s2.capital
    engine._resolve_interaction(s1, s2, noise=0.0)
    assert s1.capital == pytest.approx(c1 + (GameConfig.SURVIVAL_LISTENER_IGNORANT - 1.0))
    assert s2.capital == pytest.approx(c2 + (GameConfig.SURVIVAL_LISTENER_IGNORANT - 1.0))


def test_resolve_returns_exploitation_flag(monkeypatch):
    # 兩造都 spot,一造 RUN on GOOD → 回傳 True(被剝削,呼叫端據此斷線)
    monkeypatch.setattr(GameConfig, "PROB_SPOT_DANGER", 1.0)
    exploiter, victim = AlwaysRun(), AlwaysNotify()  # 皆起始 GOOD
    exploited = engine._resolve_interaction(exploiter, victim, noise=0.0)
    assert exploited is True
