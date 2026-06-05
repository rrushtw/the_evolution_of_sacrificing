"""
入侵 / ESS 實驗 — Sheriff 的防守(擋得住入侵)與救贖(從少數翻轉不信任世界)。

雙軸甜蜜點分析(strategy_arena / sweet_spot)結論:Sheriff 是唯一「自己不吃虧 + 社會也好」
的策略,全 Sheriff 社會穩態信任 good_share~0.98 —— 但那是**固定族群**(不繁殖不死亡)。
本實驗放開繁殖動態,問兩個鏡像問題:

  • 防守(ESS 穩定):全 Sheriff 社會 + 少數掠食者入侵 → Sheriff 壓得住嗎(入侵者份額→0)?
  • 救贖(殖民翻轉):掠食者當道的不信任世界 + 少數 Sheriff → Sheriff 從少數茁壯、
                    把社會 good_share 從低谷翻回 ~1 嗎?要看世代軌跡。

機制:Sheriff 只讀名聲。掠食者多淪 BAD → Sheriff 認得出就 RUN(不被剝削)+ 與其他 Sheriff
互助 → capital 高 → 資本加權繁殖權重高 → 翻轉。但 knockout `-reputation`(deciders 看誰都像
GOOD)讓 Sheriff 認不出掠食者 → 被剝削 → 救贖預期失敗 → 結果強依賴 churn/knockout 命運。

為何用 run_evolution(非 monomorphic 的薄 loop):入侵的核心就是「份額隨繁殖動態漲/消」,
需要完整的資本加權繁殖 + 死亡 + 早停。引擎僅加一個向後相容的 `initial_population` 參數播種混合族群。

翻轉判定的細節:所有 founder 因「無罪推定」起手皆 GOOD,故 good_share **初始恆 ~1.0**;不信任
要等掠食者 RUN-on-GOOD 被標 BAD 後才浮現。因此「翻轉」用 good_share **低谷→末值**(社會先跌入
不信任、Sheriff 再拉回),而非初值→末值。

用法(容器內,可續跑):
    docker compose run --rm simulator python -u experiments/invasion.py
旋鈕(env var):
    INV_REPS=30               每格 reps
    INV_GENERATIONS=300       每 run 代數上限(早停常提早結束)
    INV_N=160                 族群大小
    INVADER_FRACS=0.03,0.05,0.10,0.20   入侵種子比例(找翻轉所需最小種子)
    INV_CHURN_GRID=0.0,0.3,1.0
    INV_KNOCKOUTS=none,-reputation,-private
    INV_PREDATORS=Cheater,Prober,Whitewasher,Clannish
    RANDOM_SEED=12345         rep i 用 RANDOM_SEED+i;代表性軌跡取 +0
    JOBS=<cpu>
    CHECKPOINT_FILE=output/invasion_checkpoint.json
"""
import json
import multiprocessing
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import random                              # noqa: E402
import simulation                          # noqa: E402
from base_strategy import BaseStrategy     # noqa: E402
from definitions import GameConfig         # noqa: E402
from phase_sweep import _apply_preset, _agg   # noqa: E402  (復用, 不複製)

SHERIFF = "Sheriff"

REPS = int(os.getenv("INV_REPS", "30"))
GENS = int(os.getenv("INV_GENERATIONS", "300"))
N = int(os.getenv("INV_N", "160"))
BASE_SEED = int(os.getenv("RANDOM_SEED", "12345"))
FRACS = [float(x) for x in os.getenv("INVADER_FRACS", "0.03,0.05,0.10,0.20").split(",")]
CHURNS = [float(x) for x in os.getenv("INV_CHURN_GRID", "0.0,0.3,1.0").split(",")]
_ALL_KNOCKOUTS = [
    ("none", False, False),
    ("-reputation", True, False),
    ("-private", False, True),
]
_KO_FILTER = [s.strip() for s in
              os.getenv("INV_KNOCKOUTS", "none,-reputation,-private").split(",") if s.strip()]
KNOCKOUTS = [k for k in _ALL_KNOCKOUTS if k[0] in _KO_FILTER]
PREDATORS = [s.strip() for s in
             os.getenv("INV_PREDATORS", "Cheater,Prober,Whitewasher,Clannish").split(",")
             if s.strip()]
DIRECTIONS = ("defend", "redeem")   # defend: Sheriff resident; redeem: Sheriff invader
_EPS = 0.02                          # 份額 ≤eps 視為清除, ≥1-eps 視為全取代

STRATEGY_BY_NAME = {t.__name__: t for t in simulation.load_all_strategies()}


def _roles(predator: str, direction: str) -> tuple[str, str]:
    """回傳 (resident_name, invader_name)。defend=Sheriff 當原住民; redeem=Sheriff 當入侵者。"""
    return (SHERIFF, predator) if direction == "defend" else (predator, SHERIFF)


def _seed_mixed(resident_cls: type, invader_cls: type,
                n: int, invader_count: int) -> list[BaseStrategy]:
    """N 人混合族群:invader_count 個 invader + (n-invader_count) 個 resident, 打散。

    全員 gen-0 founder → reputation 預設 GOOD(presumption of innocence)。
    """
    invaders = [invader_cls() for _ in range(invader_count)]
    residents = [resident_cls() for _ in range(n - invader_count)]
    population = invaders + residents
    random.shuffle(population)   # 打散, 避免播種順序與網路 _seed 抽樣相關
    return population


def _share(snapshot: dict, name: str) -> float:
    counts = snapshot["counts"]
    total = sum(counts.values()) or 1
    return counts.get(name, 0) / total


def _good_share(snapshot: dict) -> float:
    reputation = snapshot["reputation"]
    total = sum(reputation.values()) or 1
    return reputation.get("Good", 0) / total


def _extract(result: dict, invader_name: str) -> dict:
    """從 run_evolution 回傳萃取 final 結局指標(純量, 供跨 reps 聚合)。

    翻轉用 good_share 低谷→末值(社會先跌入不信任、Sheriff 再拉回), 非初值(初值恆~1)。
    """
    history = result["history"]
    first, last = history[0], history[-1]
    good_shares = [_good_share(snap) for snap in history]
    good_min, good_final = min(good_shares), good_shares[-1]
    invader_final = _share(last, invader_name)
    final_counts = result["final_counts"]
    winner = (next(iter(final_counts)) if result["stopped_reason"] == "winner"
              and final_counts else None)
    return {
        "invader_share_init": _share(first, invader_name),
        "invader_share_final": invader_final,
        "sheriff_share_final": _share(last, SHERIFF),
        "good_share_init": good_shares[0],
        "good_share_min": good_min,
        "good_share_final": good_final,
        "flipped": 1.0 if (good_min < 0.5 and good_final > 0.5) else 0.0,
        "invader_extinct": 1.0 if invader_final <= _EPS else 0.0,
        "generations_run": float(result["generations_run"]),
        "stopped_reason": result["stopped_reason"],
        "winner": winner,
    }


def _trajectory(result: dict) -> list[dict]:
    """逐代 {g, sheriff_share, good_share} —— 代表性 run 的救贖/防守曲線。"""
    return [{"g": snap["generation"],
             "sheriff_share": round(_share(snap, SHERIFF), 4),
             "good_share": round(_good_share(snap), 4)}
            for snap in result["history"]]


def _classify(invader_share_final: float, direction: str) -> str:
    """每 run 一個結局 label(對齊使用者語意)。"""
    if invader_share_final <= _EPS:                 # 入侵者被清除
        return "resisted" if direction == "defend" else "redeem_fail"
    if invader_share_final >= 1.0 - _EPS:           # 入侵者全取代原住民
        return "invaded" if direction == "defend" else "redeem_win"
    return "coexist"


def _one_run(predator: str, direction: str, frac: float, churn: float,
             blind_rep: bool, blind_priv: bool, seed: int,
             keep_traj: bool) -> tuple[dict, list | None]:
    """一個複本:播種混合族群, 跑完整演化, 回 (final 指標, 代表性軌跡或 None)。"""
    random.seed(seed)
    _apply_preset("default")
    GameConfig.BLIND_REPUTATION = blind_rep
    GameConfig.BLIND_PRIVATE = blind_priv

    resident_name, invader_name = _roles(predator, direction)
    resident_cls = STRATEGY_BY_NAME[resident_name]
    invader_cls = STRATEGY_BY_NAME[invader_name]
    invader_count = max(1, min(N - 1, round(N * frac)))
    population = _seed_mixed(resident_cls, invader_cls, N, invader_count)

    result = simulation.run_evolution(
        [resident_cls, invader_cls], churn_rate=churn,
        max_generations=GENS, initial_population=population)

    metrics = _extract(result, invader_name)
    trajectory = _trajectory(result) if keep_traj else None
    return metrics, trajectory


def _worker(task: tuple) -> tuple:
    """跑單一複本(獨立進程)。回傳 (key, predator, direction, frac, churn, label, metrics, traj)。"""
    predator, direction, frac, churn, label, blind_rep, blind_priv, seed = task
    key = _run_key(predator, direction, frac, churn, label, seed)
    keep_traj = (seed == BASE_SEED)   # 每格只留代表性 run(seed 0)的完整軌跡
    metrics, trajectory = _one_run(predator, direction, frac, churn,
                                   blind_rep, blind_priv, seed, keep_traj)
    return key, predator, direction, frac, churn, label, metrics, trajectory


# ---- Checkpoint (resumable across interrupts) -------------------------------
CKPT_PATH = os.getenv(
    "CHECKPOINT_FILE", os.path.join(_ROOT, "output", "invasion_checkpoint.json"))


def _run_key(predator: str, direction: str, frac: float,
             churn: float, label: str, seed: int) -> str:
    return f"{predator}|{direction}|{frac}|{churn}|{label}|{seed}"


def _signature() -> dict:
    """Config fingerprint; mismatch → old checkpoint can't be reused."""
    return {"reps": REPS, "generations": GENS, "N": N, "base_seed": BASE_SEED,
            "fracs": FRACS, "churn_grid": CHURNS,
            "knockouts": [label for label, _, _ in KNOCKOUTS],
            "predators": PREDATORS}


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
    """Atomic write (tmp + replace) so a kill mid-flush never corrupts the file."""
    os.makedirs(os.path.dirname(CKPT_PATH), exist_ok=True)
    tmp_path = CKPT_PATH + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump({"signature": _signature(), "runs": runs}, f, ensure_ascii=False)
    os.replace(tmp_path, CKPT_PATH)


_BLOCKS = "▁▂▃▄▅▆▇█"


def _sparkline(values: list[float], width: int = 42) -> str:
    """[0,1] 序列 → 8 級 block sparkline, 下採樣到 width 欄。"""
    if not values:
        return ""
    if len(values) > width:
        step = (len(values) - 1) / (width - 1)
        values = [values[round(i * step)] for i in range(width)]
    return "".join(_BLOCKS[min(7, max(0, int(v * 8)))] for v in values)


def main() -> None:
    all_tasks = [(predator, direction, frac, churn, label, blind_rep, blind_priv,
                  BASE_SEED + rep_idx)
                 for predator in PREDATORS
                 for direction in DIRECTIONS
                 for frac in FRACS
                 for churn in CHURNS
                 for label, blind_rep, blind_priv in KNOCKOUTS
                 for rep_idx in range(REPS)]
    jobs = int(os.getenv("JOBS", str(multiprocessing.cpu_count() or 1)))
    total = len(all_tasks)

    done_runs = _load_checkpoint()
    by_cell = defaultdict(list)
    trajectories: dict[tuple, list] = {}
    for record in done_runs.values():
        cell = (record["predator"], record["direction"], record["frac"],
                record["churn"], record["label"])
        by_cell[cell].append(record["metrics"])
        if record.get("trajectory"):
            trajectories[cell] = record["trajectory"]
    tasks = [task for task in all_tasks
             if _run_key(task[0], task[1], task[2], task[3], task[4], task[7])
             not in done_runs]

    print(f"Invasion / ESS | predators={PREDATORS} N={N} | REPS={REPS} GENS={GENS} "
          f"base_seed={BASE_SEED} jobs={jobs}")
    print(f"fracs: {FRACS} | churn: {CHURNS} | "
          f"knockouts: {[label for label, _, _ in KNOCKOUTS]} | preset=default")
    if done_runs:
        print(f"resume: {len(done_runs)}/{total} 已完成, 續跑剩 {len(tasks)}")
    print(f"total runs = {total}\n")

    started = time.time()
    flush_every = max(1, jobs)
    with multiprocessing.Pool(jobs) as pool:
        done = len(done_runs)
        since_flush = 0
        step = max(1, total // 20)
        for (key, predator, direction, frac, churn, label,
             metrics, trajectory) in pool.imap_unordered(_worker, tasks):
            cell = (predator, direction, frac, churn, label)
            by_cell[cell].append(metrics)
            if trajectory is not None:
                trajectories[cell] = trajectory
            done_runs[key] = {"predator": predator, "direction": direction,
                              "frac": frac, "churn": churn, "label": label,
                              "metrics": metrics, "trajectory": trajectory}
            done += 1
            since_flush += 1
            if since_flush >= flush_every:
                _save_checkpoint(done_runs)
                since_flush = 0
            if done % step == 0 or done == total:
                print(f"  {done}/{total} runs done ({time.time() - started:.0f}s)")
    _save_checkpoint(done_runs)

    # ---- Aggregate cells ----
    _AGG_FIELDS = ("invader_share_final", "sheriff_share_final", "good_share_min",
                   "good_share_final", "flipped", "invader_extinct", "generations_run")
    cells = {}
    for cell, runs in by_cell.items():
        predator, direction, frac, churn, label = cell
        metrics = {field: _agg([run[field] for run in runs]) for field in _AGG_FIELDS}
        outcomes = Counter(_classify(run["invader_share_final"], direction) for run in runs)
        stopped = Counter(run["stopped_reason"] for run in runs)
        cells[cell] = {"metrics": metrics,
                       "outcomes": dict(outcomes),
                       "stopped_reasons": dict(stopped),
                       "representative_trajectory": trajectories.get(cell)}

    _print_console(cells)
    _persist(cells, started)


def _majority(outcomes: dict) -> str:
    return max(outcomes, key=outcomes.get) if outcomes else "-"


def _fate_table(cells: dict, predator: str, direction: str, label: str,
                value: str) -> None:
    """印一張 frac × churn 表;value='outcome'|'sheriff'|'ess'。"""
    print(f"  [{direction} | knockout={label}]  "
          f"({'多數結局' if value=='outcome' else 'Sheriff末份額' if value=='sheriff' else 'ESS守住率'})")
    print("   frac\\churn |" + "".join(f" {c:>14} |" for c in CHURNS))
    for frac in FRACS:
        row = f"   {frac:>9} |"
        for churn in CHURNS:
            cell = cells.get((predator, direction, frac, churn, label))
            if not cell:
                row += f" {'-':>14} |"
                continue
            if value == "outcome":
                cls = _majority(cell["outcomes"])
                flip = cell["metrics"]["flipped"]["mean"]
                row += f" {cls:>11}{'✔' if flip > 0.5 else ' '}  |"
            elif value == "sheriff":
                row += f" {cell['metrics']['sheriff_share_final']['mean']:>14.2f} |"
            else:  # ess
                row += f" {cell['metrics']['invader_extinct']['mean']:>14.2f} |"
        print(row)


def _print_console(cells: dict) -> None:
    for predator in PREDATORS:
        print(f"\n=== Sheriff vs {predator} | reps={REPS} N={N} ===")
        # 救贖:Sheriff 從少數入侵掠食者世界 → 看翻不翻得了, 跨 frac × churn × knockout
        for label, _, _ in KNOCKOUTS:
            _fate_table(cells, predator, "redeem", label, "outcome")
        # 防守:Sheriff 當原住民擋掠食者 → ESS 守住率(none-knockout 為主)
        _fate_table(cells, predator, "defend", "none", "ess")

    # 代表性救贖軌跡 sparkline:每個掠食者自動挑 none-knockout 下「最會翻轉」的格
    # (flipped 率最高、tie-break 取最小 frac),才看得到「Sheriff 茁壯 + 把信任拉回」的弧線。
    print(f"\n=== 代表性救贖軌跡(seed={BASE_SEED}, none-knockout, 自動挑最佳翻轉格)===")
    for predator in PREDATORS:
        best = None   # (flipped_mean, -frac, frac, churn, traj)
        for frac in FRACS:
            for churn in CHURNS:
                cell = cells.get((predator, "redeem", frac, churn, "none"))
                traj = cell and cell["representative_trajectory"]
                if not traj:
                    continue
                key = (cell["metrics"]["flipped"]["mean"], -frac)
                if best is None or key > best[0]:
                    best = (key, frac, churn, traj)
        if best is None:
            continue
        _, frac, churn, traj = best
        sheriff = [point["sheriff_share"] for point in traj]
        good = [point["good_share"] for point in traj]
        last = traj[-1]
        print(f"\n  Sheriff {frac:.0%} → {predator} 世界 (churn={churn}, g={last['g']})")
        print(f"    Sheriff份額 {_sparkline(sheriff)}  {sheriff[0]:.2f}→{sheriff[-1]:.2f}")
        print(f"    good_share  {_sparkline(good)}  "
              f"{good[0]:.2f}↘{min(good):.2f}↗{good[-1]:.2f}")


def _persist(cells: dict, started: float) -> None:
    os.makedirs(os.path.join(_ROOT, "output"), exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(_ROOT, "output", f"invasion_{stamp}.json")
    config = {
        "reps": REPS,
        "generations": GENS,
        "N": N,
        "base_seed": BASE_SEED,
        "invader_fracs": FRACS,
        "churn_grid": CHURNS,
        "knockouts": [label for label, _, _ in KNOCKOUTS],
        "preset": "default",
        "predators": PREDATORS,
        "directions": list(DIRECTIONS),
        "duration_seconds": round(time.time() - started, 1),
    }
    serialized_cells = {
        f"matchup=Sheriff_vs_{predator}|dir={direction}|frac={frac}|churn={churn}|{label}": cell
        for (predator, direction, frac, churn, label), cell in cells.items()
    }
    payload = {"config": config, "cells": serialized_cells}
    with open(path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\nSaved → ./output/invasion_{stamp}.json  ({config['duration_seconds']}s)")

    try:
        os.remove(CKPT_PATH)
        print(f"✓ checkpoint 已清除 ({CKPT_PATH})")
    except OSError:
        pass


if __name__ == "__main__":
    main()
