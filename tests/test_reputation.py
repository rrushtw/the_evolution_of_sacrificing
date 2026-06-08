"""不變量(4):Binary Standing(Sugden 1986)reputation 轉移。"""
from definitions import Action, Reputation
from tests.conftest import AlwaysNotify


def test_new_agent_starts_good():
    a = AlwaysNotify()
    assert a.reputation == Reputation.GOOD


def test_notify_sets_good_unconditionally():
    a = AlwaysNotify()
    a.reputation = Reputation.BAD  # 即使原本 BAD
    a.update_reputation(Action.NOTIFY, Reputation.BAD)
    assert a.reputation == Reputation.GOOD
    a.update_reputation(Action.NOTIFY, Reputation.GOOD)
    assert a.reputation == Reputation.GOOD


def test_run_against_good_becomes_bad():
    a = AlwaysNotify()
    assert a.reputation == Reputation.GOOD
    a.update_reputation(Action.RUN, Reputation.GOOD)
    assert a.reputation == Reputation.BAD


def test_run_against_bad_is_unchanged_justified_defection():
    a = AlwaysNotify()
    # 起始 GOOD,對 BAD 逃跑 → 正當防衛,不變
    a.update_reputation(Action.RUN, Reputation.BAD)
    assert a.reputation == Reputation.GOOD
    # 起始 BAD,對 BAD 逃跑 → 仍不變
    a.reputation = Reputation.BAD
    a.update_reputation(Action.RUN, Reputation.BAD)
    assert a.reputation == Reputation.BAD
