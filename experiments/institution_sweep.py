"""
第三方制度懲罰 sweep — 系統主動淘汰 BAD(Nowak 第五法則),回答三個研究問題:

  (a) 制度能否在「都會 + 關名聲」(自發名聲失效)取代名聲、把合作救回?
  (b) 制度能否廢掉 Whitewasher 的洗白套利(BAD 一被標記就清掉 → 套利窗口關閉)?
  (c) 誤判率(冤枉 GOOD)多高會反噬合作?

機制:`INSTITUTION_STRENGTH` = 每 round 把 BAD 淘汰的機率;`INSTITUTION_FALSE_POSITIVE` =
誤判 GOOD 的機率(見 definitions.py / simulation.py 死亡階段)。淘汰走既有 on_death →
資本加權繁殖,引擎僅加一支分支。

**assortment 是顯式變量**(P(遇到同名聲的人);0=隨機混合, 0.6=善良抱團)—— 因為結構(assortment)
與名聲是部分替代品, 制度的效果在不同結構下不同。固定 default preset。

復用 phase_sweep 的 `_apply_preset` / `_agg` / `NICE`(合作 = NICE 策略族群佔比),
checkpoint / Pool 平行 / 原子寫照其模式。

用法(容器內, 可續跑):
    docker compose run --rm simulator python -u experiments/institution_sweep.py
旋鈕(env var):
    INST_REPS=30                       每格 reps
    INST_GENERATIONS=300               每 run 代數
    INST_STRENGTH_GRID=0.0,0.02,0.05,0.1,0.2   制度強度(BAD 被淘汰機率)
    INST_ASSORT_GRID=0.0,0.3,0.6       同類結伴(顯式;不靠 .env 默吃)
    INST_CHURN_GRID=0.0,0.3,1.0
    INST_KNOCKOUTS=none,-reputation    制度 vs 自發名聲:關名聲時只剩制度
    INST_SETS=full,no_whitewasher      是否含洗白者(驗套利是否被壓制)
    INST_FP_GRID=0.0,0.05,0.1,0.2,0.4  誤判率敏感度線(固定 strength/churn/ko/set/assort)
    INST_FP_STRENGTH=0.1  INST_FP_CHURN=1.0  INST_FP_ASSORT=0.0   誤判率線的固定點
    RANDOM_SEED=12345  JOBS=<cpu>
    CHECKPOINT_FILE=output/institution_sweep_checkpoint.json
"""
import json
import multiprocessing
import os
import random
import sys
import time
from collections import defaultdict
from datetime import datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import simulation                                   # noqa: E402
from definitions import GameConfig                  # noqa: E402
from phase_sweep import _apply_preset, _agg, NICE   # noqa: E402  (復用, 不複製)

REPS = int(os.getenv("INST_REPS", "30"))
GENS = int(os.getenv("INST_GENERATIONS", "300"))
BASE_SEED = int(os.getenv("RANDOM_SEED", "12345"))
STRENGTHS = [float(x) for x in
             os.getenv("INST_STRENGTH_GRID", "0.0,0.02,0.05,0.1,0.2").split(",")]
ASSORTS = [float(x) for x in os.getenv("INST_ASSORT_GRID", "0.0,0.3,0.6").split(",")]
CHURNS = [float(x) for x in os.getenv("INST_CHURN_GRID", "0.0,0.3,1.0").split(",")]
_ALL_KO = [("none", False), ("-reputation", True)]
_KO_FILTER = [s.strip() for s in
              os.getenv("INST_KNOCKOUTS", "none,-reputation").split(",") if s.strip()]
KNOCKOUTS = [k for k in _ALL_KO if k[0] in _KO_FILTER]
SETS = [s.strip() for s in
        os.getenv("INST_SETS", "full,no_whitewasher").split(",") if s.strip()]
FP_GRID = [float(x) for x in os.getenv("INST_FP_GRID", "0.0,0.05,0.1,0.2,0.4").split(",")]
FP_STRENGTH = float(os.getenv("INST_FP_STRENGTH", "0.1"))
FP_CHURN = float(os.getenv("INST_FP_CHURN", "1.0"))
FP_ASSORT = float(os.getenv("INST_FP_ASSORT", "0.0"))

WHITEWASHER = "Whitewasher"
_ALL_TYPES = simulation.load_all_strategies()
TYPES_BY_SET = {
    "full": _ALL_TYPES,
    "no_whitewasher": [t for t in _ALL_TYPES if t.__name__ != WHITEWASHER],
}


def _one_run(strength: float, fp: float, churn: float, blind_rep: bool,
             strat_set: str, assortment: float, seed: int) -> dict:
    """一個複本:套制度 + assortment 旋鈕跑完整演化, 回合作/剝削/制度淘汰/洗白份額指標。"""
    random.seed(seed)
    _apply_preset("default")
    GameConfig.BLIND_REPUTATION = blind_rep
    GameConfig.BLIND_PRIVATE = False
    GameConfig.INSTITUTION_STRENGTH = strength
    GameConfig.INSTITUTION_FALSE_POSITIVE = fp
    GameConfig.ASSORTMENT = assortment   # 顯式, 不靠 .env 默吃

    types = TYPES_BY_SET[strat_set]
    last_snapshot: dict = {}
    result = simulation.run_evolution(
        types, churn_rate=churn, assortment=assortment, max_generations=GENS,
        on_generation=lambda generation, snapshot: last_snapshot.update(snapshot))
    final_counts = result["final_counts"]
    total = sum(final_counts.values()) or 1
    return {
        "nice": sum(cnt for name, cnt in final_counts.items() if name in NICE) / total,
        "expl": float(last_snapshot.get("exploitations", 0)),
        "inst_removals": float(last_snapshot.get("institutional_removals", 0)),
        "whitewasher_share": final_counts.get(WHITEWASHER, 0) / total,
        "capital_mean": last_snapshot.get("capital_mean", 0.0),
    }


# task = (kind, strength, fp, churn, ko_label, blind_rep, strat_set, assortment, seed)
def _worker(task: tuple) -> tuple:
    kind, strength, fp, churn, ko_label, blind_rep, strat_set, assortment, seed = task
    key = _run_key(task)
    metrics = _one_run(strength, fp, churn, blind_rep, strat_set, assortment, seed)
    return key, _cell_of(kind, strength, fp, churn, ko_label, strat_set, assortment), metrics


# ---- Checkpoint (resumable across interrupts) -------------------------------
CKPT_PATH = os.getenv(
    "CHECKPOINT_FILE",
    os.path.join(_ROOT, "output", "institution_sweep_checkpoint.json"))


def _run_key(task: tuple) -> str:
    kind, strength, fp, churn, ko_label, _, strat_set, assortment, seed = task
    return f"{kind}|a{assortment}|s{strength}|fp{fp}|c{churn}|{ko_label}|{strat_set}|{seed}"


def _cell_of(kind, strength, fp, churn, ko_label, strat_set, assortment) -> tuple:
    return (kind, assortment, strength, fp, churn, ko_label, strat_set)


def _signature() -> dict:
    return {"reps": REPS, "generations": GENS, "base_seed": BASE_SEED,
            "strengths": STRENGTHS, "assorts": ASSORTS, "churn_grid": CHURNS,
            "knockouts": [k[0] for k in KNOCKOUTS], "sets": SETS,
            "fp_grid": FP_GRID, "fp_strength": FP_STRENGTH,
            "fp_churn": FP_CHURN, "fp_assort": FP_ASSORT}


def _load_checkpoint() -> dict:
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


def _save_checkpoint(runs: dict) -> None:
    os.makedirs(os.path.dirname(CKPT_PATH), exist_ok=True)
    tmp_path = CKPT_PATH + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump({"signature": _signature(), "runs": runs}, f, ensure_ascii=False)
    os.replace(tmp_path, CKPT_PATH)


def _build_tasks() -> list:
    """主掃描格(fp=0)+ 誤判率敏感度線(固定 strength/churn/ko/set/assort)。"""
    grid = [("grid", strength, 0.0, churn, ko_label, blind_rep, strat_set,
             assortment, BASE_SEED + rep)
            for strat_set in SETS
            for assortment in ASSORTS
            for ko_label, blind_rep in KNOCKOUTS
            for churn in CHURNS
            for strength in STRENGTHS
            for rep in range(REPS)]
    # 誤判率線:都會 + 關名聲 + full + 固定 strength/assort, 掃 fp(>0 才有意義, 0 已在 grid)。
    fpline = [("fpline", FP_STRENGTH, fp, FP_CHURN, "-reputation", True, "full",
               FP_ASSORT, BASE_SEED + rep)
              for fp in FP_GRID if fp > 0.0
              for rep in range(REPS)]
    return grid + fpline


def main() -> None:
    all_tasks = _build_tasks()
    jobs = int(os.getenv("JOBS", str(multiprocessing.cpu_count() or 1)))
    total = len(all_tasks)

    done_runs = _load_checkpoint()
    by_cell: dict = defaultdict(list)
    for record in done_runs.values():
        by_cell[tuple(record["cell"])].append(record["metrics"])
    tasks = [task for task in all_tasks if _run_key(task) not in done_runs]

    print(f"Institution sweep | sets={SETS} assorts={ASSORTS} | REPS={REPS} "
          f"GENS={GENS} base_seed={BASE_SEED} jobs={jobs}")
    print(f"strength: {STRENGTHS} | churn: {CHURNS} | "
          f"knockouts: {[k[0] for k in KNOCKOUTS]}")
    print(f"fp-line: strength={FP_STRENGTH} churn={FP_CHURN} assort={FP_ASSORT} "
          f"-reputation full | fp: {FP_GRID}")
    if done_runs:
        print(f"resume: {len(done_runs)}/{total} 已完成, 續跑剩 {len(tasks)}")
    print(f"total runs = {total}\n")

    started = time.time()
    flush_every = max(1, jobs)
    with multiprocessing.Pool(jobs) as pool:
        done = len(done_runs)
        since_flush = 0
        step = max(1, total // 20)
        for key, cell, metrics in pool.imap_unordered(_worker, tasks):
            by_cell[cell].append(metrics)
            done_runs[key] = {"cell": list(cell), "metrics": metrics}
            done += 1
            since_flush += 1
            if since_flush >= flush_every:
                _save_checkpoint(done_runs)
                since_flush = 0
            if done % step == 0 or done == total:
                print(f"  {done}/{total} runs done ({time.time() - started:.0f}s)")
    _save_checkpoint(done_runs)

    _AGG_FIELDS = ("nice", "expl", "inst_removals", "whitewasher_share",
                   "capital_mean")
    cells = {}
    for cell, runs in by_cell.items():
        cells[cell] = {field: _agg([run[field] for run in runs])
                       for field in _AGG_FIELDS}

    _print_console(cells)
    _persist(cells, started)


def _grid_cell(cells: dict, assortment, strength, churn, ko_label, strat_set) -> dict:
    return cells.get(("grid", assortment, strength, 0.0, churn, ko_label, strat_set))


def _print_console(cells: dict) -> None:
    for assortment in ASSORTS:
        for strat_set in SETS:
            for ko_label, _ in KNOCKOUTS:
                print(f"\n=== nice% | assort={assortment} set={strat_set} "
                      f"knockout={ko_label} (mean ± 95% CI, n={REPS}) ===")
                print("strength\\churn |" + "".join(f" {c:>12} |" for c in CHURNS))
                for strength in STRENGTHS:
                    row = f"   {strength:>11} |"
                    for churn in CHURNS:
                        cell = _grid_cell(cells, assortment, strength, churn,
                                          ko_label, strat_set)
                        if not cell:
                            row += f" {'-':>12} |"
                            continue
                        m = cell["nice"]
                        row += f" {m['mean']:>5.0%}±{m['ci95']:>4.0%} |"
                    print(row)

    # Whitewasher 套利窗口:full set、none、assort=0.0, 隨 strength × churn
    if "full" in SETS and 0.0 in ASSORTS:
        print(f"\n=== Whitewasher 份額 | assort=0.0 set=full knockout=none "
              f"(隨制度強度是否被壓制, n={REPS}) ===")
        print("strength\\churn |" + "".join(f" {c:>12} |" for c in CHURNS))
        for strength in STRENGTHS:
            row = f"   {strength:>11} |"
            for churn in CHURNS:
                cell = _grid_cell(cells, 0.0, strength, churn, "none", "full")
                if not cell:
                    row += f" {'-':>12} |"
                    continue
                m = cell["whitewasher_share"]
                row += f" {m['mean']:>5.0%}±{m['ci95']:>4.0%} |"
            print(row)

    # 誤判率反噬線
    print(f"\n=== 誤判率反噬 | strength={FP_STRENGTH} churn={FP_CHURN} "
          f"assort={FP_ASSORT} -reputation full (n={REPS}) ===")
    print("   fp   |   nice%      | inst_removals")
    for fp in FP_GRID:
        if fp == 0.0:
            cell = _grid_cell(cells, FP_ASSORT, FP_STRENGTH, FP_CHURN,
                              "-reputation", "full")
        else:
            cell = cells.get(("fpline", FP_ASSORT, FP_STRENGTH, fp, FP_CHURN,
                              "-reputation", "full"))
        if not cell:
            print(f" {fp:>5} |     -        |     -")
            continue
        print(f" {fp:>5} | {cell['nice']['mean']:>5.0%}±{cell['nice']['ci95']:>4.0%} "
              f"| {cell['inst_removals']['mean']:>6.1f}")


def _persist(cells: dict, started: float) -> None:
    os.makedirs(os.path.join(_ROOT, "output"), exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(_ROOT, "output", f"institution_sweep_{stamp}.json")
    config = {
        "reps": REPS, "generations": GENS, "base_seed": BASE_SEED,
        "strength_grid": STRENGTHS, "assort_grid": ASSORTS, "churn_grid": CHURNS,
        "knockouts": [k[0] for k in KNOCKOUTS], "sets": SETS,
        "fp_grid": FP_GRID, "fp_strength": FP_STRENGTH,
        "fp_churn": FP_CHURN, "fp_assort": FP_ASSORT,
        "preset": "default",
        "duration_seconds": round(time.time() - started, 1),
    }
    serialized_cells = {
        f"kind={kind}|assort={assortment}|strength={strength}|fp={fp}|churn={churn}"
        f"|{ko_label}|set={strat_set}": cell
        for (kind, assortment, strength, fp, churn, ko_label, strat_set), cell
        in cells.items()
    }
    payload = {"config": config, "cells": serialized_cells}
    with open(path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\nSaved → ./output/institution_sweep_{stamp}.json  "
          f"({config['duration_seconds']}s)")

    try:
        os.remove(CKPT_PATH)
        print(f"✓ checkpoint 已清除 ({CKPT_PATH})")
    except OSError:
        pass


if __name__ == "__main__":
    main()
