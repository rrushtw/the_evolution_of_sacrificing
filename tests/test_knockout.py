"""不變量(5):knockout flags —— BLIND_PRIVATE / BLIND_REPUTATION 的消融行為。"""
from definitions import Action, GameConfig, Reputation
from tests.conftest import AlwaysNotify, AlwaysRun, SpyStrategy


# ---- BLIND_PRIVATE:不記 per-opponent 私記憶,但公開 my_history 仍記 ----

def test_blind_private_off_records_opponent_history():
    a = AlwaysNotify()
    a.record_round("opp-1", Action.NOTIFY, Action.RUN)
    assert a.my_history  # 公開記錄一定有
    assert a.opponent_history.get("opp-1")  # 預設有私記憶


def test_blind_private_on_skips_opponent_history(monkeypatch):
    monkeypatch.setattr(GameConfig, "BLIND_PRIVATE", True)
    a = AlwaysNotify()
    a.record_round("opp-1", Action.NOTIFY, Action.RUN)
    assert a.my_history            # 公開記錄不受影響
    assert a.opponent_history == {}  # 私記憶被消融


# ---- BLIND_REPUTATION:decider 看到的對手 Standing 恆 GOOD、公開 history 被遮蔽 ----

def _run_spy_against_bad(monkeypatch):
    """讓 spy 必為 spotter,對手為一個有 BAD reputation、且有公開 history 的 agent。"""
    monkeypatch.setattr(GameConfig, "PROB_SPOT_DANGER", 1.0)
    spy = SpyStrategy()
    opp = AlwaysRun()
    opp.reputation = Reputation.BAD
    opp.my_history.append({"my_action": Action.RUN, "opponent_action": None})
    import engine
    engine._resolve_interaction(spy, opp, noise=0.0)
    return spy


def test_blind_reputation_off_spy_sees_true_standing(monkeypatch):
    spy = _run_spy_against_bad(monkeypatch)
    assert spy.seen_reputation == Reputation.BAD
    assert spy.seen_history  # 看得到對手公開 history


def test_blind_reputation_on_spy_sees_good_and_empty_history(monkeypatch):
    monkeypatch.setattr(GameConfig, "BLIND_REPUTATION", True)
    spy = _run_spy_against_bad(monkeypatch)
    assert spy.seen_reputation == Reputation.GOOD  # 真 BAD 被遮成 GOOD
    assert spy.seen_history == []                  # 公開 history 也被遮蔽
