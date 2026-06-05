"""不變量(1)(8):整體模擬 —— population 守恆、重現性、制度向後相容。"""
import random

import simulation
from definitions import GameConfig
from tests.conftest import AlwaysNotify, AlwaysRun


STRATS = [AlwaysNotify, AlwaysRun]


def _run(seed=42, copies=10, max_gen=15, **kw):
    random.seed(seed)
    return simulation.run_evolution(
        STRATS,
        initial_copies=copies,
        max_generations=max_gen,
        **kw,
    )


def _strip(history):
    """去除非決定性的 wall-clock 欄位,讓 history 可逐 snapshot 比對。"""
    return [{k: v for k, v in snap.items() if k != "duration_seconds"} for snap in history]


# ---- (1) population 守恆 ----

def test_population_is_conserved_each_generation():
    n = len(STRATS) * 10
    result = _run(copies=10, max_gen=20)
    for snap in result["history"]:
        counts = snap["counts"]
        if counts:  # 全滅那代 counts 為空,豁免
            assert sum(counts.values()) == n


# ---- (8) 重現性 ----

def test_same_seed_same_params_reproduces_history():
    a = _run(seed=7, max_gen=15)
    b = _run(seed=7, max_gen=15)
    assert _strip(a["history"]) == _strip(b["history"])
    assert a["generations_run"] == b["generations_run"]
    assert a["stopped_reason"] == b["stopped_reason"]


def test_different_seed_diverges():
    a = _run(seed=1, max_gen=15)
    b = _run(seed=2, max_gen=15)
    # 不同 seed 幾乎不可能逐 snapshot 完全相同
    assert _strip(a["history"]) != _strip(b["history"])


# ---- 制度向後相容:INSTITUTION_STRENGTH=0 → 永不淘汰 ----

def test_no_institution_means_zero_removals():
    # clean_config 已把 INSTITUTION_STRENGTH/FALSE_POSITIVE 設 0
    result = _run(max_gen=20)
    for snap in result["history"]:
        assert snap["institutional_removals"] == 0


def test_institution_strength_culls_bad(monkeypatch):
    # 反面 sanity:強制執法 + 族群含會變 BAD 的 AlwaysRun → 至少一代有制度淘汰
    monkeypatch.setattr(GameConfig, "INSTITUTION_STRENGTH", 1.0)
    result = _run(max_gen=15)
    total_removals = sum(s["institutional_removals"] for s in result["history"])
    assert total_removals > 0


# ---- 回傳契約 ----

def test_result_has_expected_keys():
    result = _run(max_gen=5)
    for key in ("final_counts", "final_population", "extinction_order",
                "history", "generations_run", "stopped_reason"):
        assert key in result
