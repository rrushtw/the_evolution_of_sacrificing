"""
capital_arena — 隔離擂台:capital-aware 策略在何種社會流動度下勝出?(issue #7 Part C)

把 canonical 16 策略 + experimental capital-aware 策略(Sycophant 嫌貧愛富、Desperado
背水一戰)放進同一個生態,掃 churn(村莊↔都會)× reps,看這兩個「會看資本下菜」的策略
份額 / 資本隨流動度怎麼變。

**為什麼是獨立實驗(不動 canonical)**:experimental 策略住在 strategies/experimental/
子套件,load_all_strategies()(pkgutil 不遞迴)收不到 → melee / ESS / 制度等已發表的
「16 策略」結果完全不受污染。本檔**顯式** import 它們、自組 roster,輸出自有檔名前綴
(capital_arena_*.json),絕不覆寫 canonical JSON。

複用 phase_sweep 的 `_apply_preset` / `_agg`(不複製)。checkpoint 同 phase_sweep 的
atomic resume 模式,可中斷續跑。

跑法(遠端 container,顯式傳參、不讀 .env):

    docker run --rm -v ~/eos/output:/app/output \
        -e REPS=30 -e BATCH_GENERATIONS=300 -e CHURN_GRID=0.0,0.3,1.0 \
        -e ASSORTMENT=0.0 -e RANDOM_SEED=12345 -e JOBS=20 \
        eos-sim python -u experiments/capital_arena.py

knobs(env):
    REPS=30                 replicates / cell
    BATCH_GENERATIONS=300   rounds / run
    CHURN_GRID=0.0,0.3,1.0  村莊 → 都會
    ASSORTMENT=0.0          結伴度(顯式傳!避免 .env=0.6 默吃的跨機不一致陷阱)
    RANDOM_SEED=12345       base seed;replicate i 用 RANDOM_SEED+i
    JOBS=<cpu>              平行 worker 數
    CHECKPOINT_FILE=output/capital_arena_checkpoint.json
"""
import json
import multiprocessing
import os
import random
import sys
import time
from collections import defaultdict
from datetime import datetime

# Make the repo root importable regardless of where we're launched from.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import simulation                              # noqa: E402
from definitions import GameConfig             # noqa: E402
from phase_sweep import _apply_preset, _agg    # noqa: E402  (復用, 不複製)
from strategies.experimental.sycophant import Sycophant   # noqa: E402
from strategies.experimental.desperado import Desperado   # noqa: E402

# Roster = canonical 16(auto-discovered)+ experimental capital-aware(顯式加).
EXPERIMENTAL = [Sycophant, Desperado]
EXPERIMENTAL_NAMES = [t.__name__ for t in EXPERIMENTAL]
TYPES = simulation.load_all_strategies() + EXPERIMENTAL
STRATEGY_NAMES = [t.__name__ for t in TYPES]
N = len(TYPES) * GameConfig.INITIAL_COPIES

REPS = int(os.getenv("REPS", "30"))
GENS = int(os.getenv("BATCH_GENERATIONS", "300"))
BASE_SEED = int(os.getenv("RANDOM_SEED", "12345"))
CHURNS = [float(x) for x in os.getenv("CHURN_GRID", "0.0,0.3,1.0").split(",")]
# 顯式結伴度 —— 不靠 .env 默值(見 remote-exp-host 的 ASSORTMENT 陷阱)。
ASSORT = float(os.getenv("ASSORTMENT", "0.0"))


def _one_run(churn: float, seed: int) -> dict:
    """跑一個複本,回傳 winner + 全 roster 的 per-strategy 明細(絕種補零)。"""
    random.seed(seed)
    _apply_preset("default")             # pin 出廠 SURVIVAL_*,不吃殘留 preset 狀態
    GameConfig.ASSORTMENT = ASSORT       # engine 即時讀;同時顯式傳給 run_evolution
    result = simulation.run_evolution(
        TYPES, assortment=ASSORT, churn_rate=churn, max_generations=GENS)
    final_counts = result["final_counts"]
    total = sum(final_counts.values()) or 1
    winner = max(final_counts, key=final_counts.get) if final_counts else None

    capitals_by_strategy: dict[str, list[float]] = defaultdict(list)
    for agent in result["final_population"]:
        capitals_by_strategy[type(agent).__name__].append(agent.capital)
    per_strategy: dict[str, dict] = {}
    for strategy_name in STRATEGY_NAMES:
        count = final_counts.get(strategy_name, 0)
        capitals = capitals_by_strategy.get(strategy_name, [])
        per_strategy[strategy_name] = {
            "share": count / total,
            "capital": (sum(capitals) / len(capitals)) if capitals else 0.0,
            "survived": 1.0 if count else 0.0,
            "count": count,
        }
    return {"winner": winner, "per_strategy": per_strategy}


def _worker(task):
    """One replicate in its own process. Returns (key, churn, metrics)."""
    churn, seed = task
    return _run_key(churn, seed), churn, _one_run(churn, seed)


# ---- Checkpoint (resumable across interrupts) -------------------------------
CKPT_PATH = os.getenv(
    "CHECKPOINT_FILE", os.path.join(_ROOT, "output", "capital_arena_checkpoint.json"))


def _run_key(churn, seed):
    return f"{churn}|{seed}"


def _signature():
    return {"reps": REPS, "generations": GENS, "base_seed": BASE_SEED,
            "churn_grid": CHURNS, "assortment": ASSORT,
            "strategies": len(TYPES), "experimental": EXPERIMENTAL_NAMES, "N": N}


def _load_checkpoint():
    if not os.path.exists(CKPT_PATH):
        return {}
    try:
        with open(CKPT_PATH) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        print(f"⚠ checkpoint 損毀,忽略重跑 ({CKPT_PATH})")
        return {}
    if data.get("signature") != _signature():
        print(f"⚠ checkpoint 設定不符,忽略重跑 ({CKPT_PATH})")
        return {}
    return data.get("runs", {})


def _save_checkpoint(runs):
    """Atomic write (tmp + replace) so a kill mid-flush never corrupts the file."""
    os.makedirs(os.path.dirname(CKPT_PATH), exist_ok=True)
    tmp = CKPT_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"signature": _signature(), "runs": runs}, f, ensure_ascii=False)
    os.replace(tmp, CKPT_PATH)


def main():
    all_tasks = [(churn, BASE_SEED + i) for churn in CHURNS for i in range(REPS)]
    jobs = int(os.getenv("JOBS", str(multiprocessing.cpu_count() or 1)))
    total = len(all_tasks)

    done_runs = _load_checkpoint()
    by_churn = defaultdict(list)
    for rec in done_runs.values():
        by_churn[rec["churn"]].append(rec["metrics"])
    tasks = [t for t in all_tasks if _run_key(t[0], t[1]) not in done_runs]

    print(f"capital_arena | strategies={len(TYPES)} (experimental: "
          f"{', '.join(EXPERIMENTAL_NAMES)}) | N={N} | REPS={REPS} GENS={GENS} "
          f"assort={ASSORT} base_seed={BASE_SEED} jobs={jobs}")
    print(f"churn grid: {CHURNS}")
    if done_runs:
        print(f"resume: {len(done_runs)}/{total} 已完成,續跑剩 {len(tasks)}")
    print(f"total runs = {total}\n")

    started = time.time()
    flush_every = max(1, jobs)
    with multiprocessing.Pool(jobs) as pool:
        done = len(done_runs)
        since_flush = 0
        step = max(1, total // 20)
        for key, churn, m in pool.imap_unordered(_worker, tasks):
            by_churn[churn].append(m)
            done_runs[key] = {"churn": churn, "metrics": m}
            done += 1
            since_flush += 1
            if since_flush >= flush_every:
                _save_checkpoint(done_runs)
                since_flush = 0
            if done % step == 0 or done == total:
                print(f"  {done}/{total} runs done ({time.time() - started:.0f}s)")
    _save_checkpoint(done_runs)

    # Aggregate per churn: every strategy × field → mean ± 95% CI, plus winners.
    cells = {}
    for churn, runs in by_churn.items():
        per_strategy = {
            name: {field: _agg([r["per_strategy"][name][field] for r in runs])
                   for field in ("share", "capital", "survived")}
            for name in STRATEGY_NAMES
        }
        winners: dict = {}
        for r in runs:
            winners[r["winner"]] = winners.get(r["winner"], 0) + 1
        cells[churn] = {"per_strategy": per_strategy, "winners": winners,
                        "top_winner": max(winners, key=winners.get)}

    # ---- Console: capital-aware 策略 across churn ----
    print(f"\n=== capital-aware 策略 vs churn (share, mean ± 95% CI, n={REPS}) ===")
    head = "churn |" + "".join(f" {name:>12} |" for name in EXPERIMENTAL_NAMES) + " top winner"
    print(head)
    for churn in CHURNS:
        row = f"{churn:>5} |"
        for name in EXPERIMENTAL_NAMES:
            s = cells[churn]["per_strategy"][name]["share"]
            row += f" {s['mean']:>6.1%}±{s['ci95']:>3.0%} |"
        row += f" {cells[churn]['top_winner']}"
        print(row)

    print(f"\n=== capital-aware 策略 vs churn (mean capital ± 95% CI) ===")
    print("churn |" + "".join(f" {name:>12} |" for name in EXPERIMENTAL_NAMES))
    for churn in CHURNS:
        row = f"{churn:>5} |"
        for name in EXPERIMENTAL_NAMES:
            c = cells[churn]["per_strategy"][name]["capital"]
            row += f" {c['mean']:>6.2f}±{c['ci95']:>4.2f} |"
        print(row)

    # ---- Persist JSON ----
    os.makedirs(os.path.join(_ROOT, "output"), exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(_ROOT, "output", f"capital_arena_{stamp}.json")
    payload = {
        "config": {"reps": REPS, "generations": GENS, "base_seed": BASE_SEED,
                   "churn_grid": CHURNS, "assortment": ASSORT,
                   "strategies": len(TYPES), "experimental": EXPERIMENTAL_NAMES,
                   "N": N, "duration_seconds": round(time.time() - started, 1)},
        "cells": {f"churn={c}": v for c, v in cells.items()},
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\nSaved → ./output/capital_arena_{stamp}.json  "
          f"({payload['config']['duration_seconds']}s)")

    try:
        os.remove(CKPT_PATH)
        print(f"✓ checkpoint 已清除 ({CKPT_PATH})")
    except OSError:
        pass


if __name__ == "__main__":
    main()
