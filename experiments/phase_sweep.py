"""
Batch phase-sweep — the statistically-meaningful private↔public experiment.

Runs the full grid  CHURN × KNOCKOUT × REPS  inside a SINGLE container call,
seeding each replicate reproducibly, then aggregates mean ± 95% CI and writes
both a console table and a JSON file under output/.

Run it (after `docker compose build` or with --build):

    docker compose run --rm simulator python -u experiments/phase_sweep.py

All knobs are env vars (override on the command line with -e):

    REPS=30                 replicates per cell (≥30 for tight CIs)
    BATCH_GENERATIONS=300   rounds per run
    CHURN_GRID=0.0,0.1,0.3,0.6,1.0   village → 城鄉移民 → metropolis
    RANDOM_SEED=12345       base seed; replicate i uses RANDOM_SEED+i
                            (same seeds reused across cells = paired contrasts)
    JOBS=<cpu count>        parallel worker processes (replicates run in parallel)
    CHECKPOINT_FILE=output/phase_sweep_checkpoint.json
                            incremental per-replicate checkpoint. Each finished
                            replicate is flushed here (atomic write); re-running
                            the SAME config resumes — already-done replicates are
                            skipped. Deleted on full completion. A config change
                            (presets/churn/reps/seed/…) invalidates it → fresh run.

Resume after an interrupt (kill / reboot): just launch the exact same command
again — it picks up where it stopped. Mount output/ so the checkpoint survives.

Example — a quick smoke test:
    docker compose run --rm -e REPS=8 -e BATCH_GENERATIONS=120 \
        -e CHURN_GRID=0.0,0.3,1.0 simulator python -u experiments/phase_sweep.py
"""
import json
import multiprocessing
import os
import random
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime

# Make the repo root importable regardless of where we're launched from.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import simulation                       # noqa: E402
from definitions import GameConfig      # noqa: E402

# Reputation-based / nice strategies — our cooperation proxy is their share.
NICE = {"Altruist", "Samaritan", "Prophet", "Sheriff", "Politician",
        "TitForTwoTats", "Pavlov", "Jacobin", "Grudger"}

REPS = int(os.getenv("REPS", "30"))
GENS = int(os.getenv("BATCH_GENERATIONS", "300"))
BASE_SEED = int(os.getenv("RANDOM_SEED", "12345"))
CHURNS = [float(x) for x in os.getenv("CHURN_GRID", "0.0,0.1,0.3,0.6,1.0").split(",")]
KNOCKOUTS = [
    ("none", False, False),
    ("-reputation", True, False),
    ("-private", False, True),
]
# A1: 社會 preset 維度 — 每個 preset 是一組 c/b (門檻 r*), 各掃一張 churn×knockout 相圖。
PRESETS = [p.strip() for p in
           os.getenv("PRESETS", "default,cheap_voice,safety_net,ancient").split(",")
           if p.strip()]

TYPES = simulation.load_all_strategies()
STRATEGY_NAMES = [t.__name__ for t in TYPES]
N = len(TYPES) * GameConfig.INITIAL_COPIES


def _apply_preset(name):
    """把 SOCIETY_PRESETS[name] 寫回四個 SURVIVAL_* (缺鍵還原 default 出廠值)。

    engine.py 於互動時即時讀 GameConfig.SURVIVAL_*, 故 worker 內覆寫即生效 ——
    與 _one_run 設 BLIND_* 同模式。也更新 SOCIETY_PRESET 讓 society_params() 報對。
    """
    GameConfig.SOCIETY_PRESET = name
    vals = {**GameConfig._SURVIVAL_DEFAULTS, **GameConfig.SOCIETY_PRESETS.get(name, {})}
    GameConfig.SURVIVAL_SPOTTER_NOTIFY = vals["spotter_notify"]
    GameConfig.SURVIVAL_SPOTTER_RUN = vals["spotter_run"]
    GameConfig.SURVIVAL_LISTENER_WARNED = vals["listener_warned"]
    GameConfig.SURVIVAL_LISTENER_IGNORANT = vals["listener_ignorant"]


def _preset_rstar(name):
    """該 preset 的理論 r* (用過後還原四個常數, 不污染當前進程)。"""
    saved = (GameConfig.SOCIETY_PRESET,
             GameConfig.SURVIVAL_SPOTTER_NOTIFY, GameConfig.SURVIVAL_SPOTTER_RUN,
             GameConfig.SURVIVAL_LISTENER_WARNED, GameConfig.SURVIVAL_LISTENER_IGNORANT)
    _apply_preset(name)
    r = GameConfig.society_params()["r_star"]
    (GameConfig.SOCIETY_PRESET, GameConfig.SURVIVAL_SPOTTER_NOTIFY,
     GameConfig.SURVIVAL_SPOTTER_RUN, GameConfig.SURVIVAL_LISTENER_WARNED,
     GameConfig.SURVIVAL_LISTENER_IGNORANT) = saved
    return r


def _one_run(preset: str, churn: float, blind_rep: bool,
             blind_priv: bool, seed: int) -> dict:
    """跑一個複本, 回傳該 run 的相圖指標 + per-strategy 明細 (皆 0-1 / 計數值)。"""
    random.seed(seed)
    _apply_preset(preset)
    GameConfig.BLIND_REPUTATION = blind_rep
    GameConfig.BLIND_PRIVATE = blind_priv
    last_snapshot: dict = {}
    result = simulation.run_evolution(
        TYPES, churn_rate=churn, max_generations=GENS,
        on_generation=lambda generation, snapshot: last_snapshot.update(snapshot))
    final_counts = result["final_counts"]
    total = sum(final_counts.values()) or 1
    winner = max(final_counts, key=final_counts.get) if final_counts else None

    # per-strategy 明細 (策略當主體的 maximin 擂台用) —— 從 final_population 即時聚
    # 個體 capital/age, 零引擎改動 (本來就回傳, 過去被丟掉)。對「全 STRATEGY_NAMES」
    # 產生, 絕種策略補一筆零分 (share/capital/age/survived 全 0): maximin 視絕種為
    # 最差命運才能重罰它, 否則會反向偏袒「只在友善環境繁榮、惡劣環境直接消失」的脆弱策略。
    capitals_by_strategy: dict[str, list[float]] = defaultdict(list)
    ages_by_strategy: dict[str, list[float]] = defaultdict(list)
    for agent in result["final_population"]:
        strategy_name = type(agent).__name__
        capitals_by_strategy[strategy_name].append(agent.capital)
        ages_by_strategy[strategy_name].append(agent.age)
    per_strategy: dict[str, dict] = {}
    for strategy_name in STRATEGY_NAMES:
        count = final_counts.get(strategy_name, 0)
        capitals = capitals_by_strategy.get(strategy_name, [])
        agent_ages = ages_by_strategy.get(strategy_name, [])
        per_strategy[strategy_name] = {
            "share": count / total,
            "capital": (sum(capitals) / len(capitals)) if capitals else 0.0,
            "age": (sum(agent_ages) / len(agent_ages)) if agent_ages else 0.0,
            "survived": 1.0 if count else 0.0,
            "count": count,
        }
    return {
        "nice": sum(cnt for name, cnt in final_counts.items() if name in NICE) / total,
        "capital_mean": last_snapshot.get("capital_mean", 0.0),
        "gini": last_snapshot.get("capital_gini", 0.0),
        "reenc": last_snapshot.get("re_encounter_rate", 0.0),
        "expl": float(last_snapshot.get("exploitations", 0)),
        "winner": winner,
        "per_strategy": per_strategy,
    }


def _worker(task):
    """One replicate, run in its own process. Returns (key, preset, churn, label, metrics)."""
    preset, churn, label, blind_rep, blind_priv, seed = task
    key = _run_key(preset, churn, label, seed)
    return key, preset, churn, label, _one_run(preset, churn, blind_rep, blind_priv, seed)


def _agg(xs):
    m = statistics.mean(xs)
    sd = statistics.stdev(xs) if len(xs) > 1 else 0.0
    ci = 1.96 * sd / (len(xs) ** 0.5) if len(xs) > 1 else 0.0
    return {"mean": round(m, 4), "std": round(sd, 4), "ci95": round(ci, 4)}


# ---- Checkpoint (resumable across interrupts) -------------------------------
CKPT_PATH = os.getenv(
    "CHECKPOINT_FILE", os.path.join(_ROOT, "output", "phase_sweep_checkpoint.json"))


def _run_key(preset, churn, label, seed):
    """Unique id for one replicate — stable across runs of the same config."""
    return f"{preset}|{churn}|{label}|{seed}"


def _signature():
    """Config fingerprint; a mismatch means an old checkpoint can't be reused."""
    return {"reps": REPS, "generations": GENS, "base_seed": BASE_SEED,
            "presets": PRESETS, "churn_grid": CHURNS,
            "knockouts": [k[0] for k in KNOCKOUTS],
            "strategies": len(TYPES), "N": N}


def _load_checkpoint():
    """Return {key: {preset,churn,label,metrics}} of finished replicates, or {}."""
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
    all_tasks = [(preset, churn, label, br, bp, BASE_SEED + i)
                 for preset in PRESETS
                 for churn in CHURNS
                 for label, br, bp in KNOCKOUTS
                 for i in range(REPS)]
    rstars = {p: _preset_rstar(p) for p in PRESETS}
    jobs = int(os.getenv("JOBS", str(multiprocessing.cpu_count() or 1)))
    total = len(all_tasks)

    # Resume: skip replicates already in the checkpoint, pre-fill their results.
    done_runs = _load_checkpoint()
    by_cell = defaultdict(list)
    for rec in done_runs.values():
        by_cell[(rec["preset"], rec["churn"], rec["label"])].append(rec["metrics"])
    tasks = [t for t in all_tasks
             if _run_key(t[0], t[1], t[2], t[5]) not in done_runs]

    print(f"Batch phase-sweep | strategies={len(TYPES)} N={N} | REPS={REPS} "
          f"GENS={GENS} base_seed={BASE_SEED} jobs={jobs}")
    print(f"presets: {', '.join(f'{p} (r*={rstars[p]})' for p in PRESETS)}")
    print(f"churn grid: {CHURNS} | knockouts: {[k[0] for k in KNOCKOUTS]}")
    if done_runs:
        print(f"resume: {len(done_runs)}/{total} 已完成 (checkpoint {CKPT_PATH}),"
              f" 續跑剩 {len(tasks)}")
    print(f"total runs = {total}\n")

    started = time.time()
    # Replicates are independent and each self-seeds → run them in parallel.
    # Flush the checkpoint every ~`jobs` results: bounds I/O while keeping the
    # most-we-can-lose-on-a-kill to roughly one wave of in-flight workers.
    flush_every = max(1, jobs)
    with multiprocessing.Pool(jobs) as pool:
        done = len(done_runs)
        since_flush = 0
        step = max(1, total // 20)
        for key, preset, churn, label, m in pool.imap_unordered(_worker, tasks):
            by_cell[(preset, churn, label)].append(m)
            done_runs[key] = {"preset": preset, "churn": churn,
                              "label": label, "metrics": m}
            done += 1
            since_flush += 1
            if since_flush >= flush_every:
                _save_checkpoint(done_runs)
                since_flush = 0
            if done % step == 0 or done == total:
                print(f"  {done}/{total} runs done "
                      f"({time.time() - started:.0f}s)")
    _save_checkpoint(done_runs)   # final flush of the last partial wave

    cells = {}            # (preset, churn, label) -> aggregated metrics + winners
    for key, runs in by_cell.items():
        metrics = {k: _agg([r[k] for r in runs])
                   for k in ("nice", "capital_mean", "gini", "reenc", "expl")}
        winners = {}
        for r in runs:
            winners[r["winner"]] = winners.get(r["winner"], 0) + 1
        metrics["top_winner"] = max(winners, key=winners.get)
        # per-strategy: 每策略 × 每欄跨 reps 聚 mean/std/ci95 (擂台分析的原料)。
        per_strategy = {
            name: {field: _agg([r["per_strategy"][name][field] for r in runs])
                   for field in ("share", "capital", "age", "survived")}
            for name in STRATEGY_NAMES
        }
        cells[key] = {"metrics": metrics, "winners": winners,
                      "per_strategy": per_strategy}

    # ---- Console tables (one per preset) ----
    for preset in PRESETS:
        print(f"\n=== nice%  | preset={preset} (r*={rstars[preset]}) "
              f"(mean ± 95% CI, n={REPS}) ===")
        head = "churn |" + "".join(f" {lab:>16} |" for lab, _, _ in KNOCKOUTS)
        print(head)
        for churn in CHURNS:
            row = f"{churn:>5} |"
            for label, _, _ in KNOCKOUTS:
                m = cells[(preset, churn, label)]["metrics"]["nice"]
                row += f" {m['mean']:>6.0%} ± {m['ci95']:>4.0%} |"
            print(row)

        print(f"--- no-knockout society profile | preset={preset} ---")
        print("churn |   reenc%    |   nice%     |   gini      | expl/round")
        for churn in CHURNS:
            m = cells[(preset, churn, "none")]["metrics"]
            print(f"{churn:>5} | "
                  f"{m['reenc']['mean']:>5.0%}±{m['reenc']['ci95']:>3.0%} | "
                  f"{m['nice']['mean']:>5.0%}±{m['nice']['ci95']:>3.0%} | "
                  f"{m['gini']['mean']:>4.2f}±{m['gini']['ci95']:>4.2f} | "
                  f"{m['expl']['mean']:>5.1f}±{m['expl']['ci95']:>4.1f}")

    # ---- r* 平移總覽:none-knockout nice% 隨 preset (r*↑) 的變化 ----
    print(f"\n=== r* 平移 | none-knockout nice% by preset (n={REPS}) ===")
    print("churn |" + "".join(
        f" {p[:10]:>10}(r*{rstars[p]:>4}) |" for p in PRESETS))
    for churn in CHURNS:
        row = f"{churn:>5} |"
        for preset in PRESETS:
            m = cells[(preset, churn, "none")]["metrics"]["nice"]
            row += f" {m['mean']:>16.0%} |"
        print(row)

    # ---- Persist JSON ----
    os.makedirs(os.path.join(_ROOT, "output"), exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(_ROOT, "output", f"phase_sweep_{stamp}.json")
    payload = {
        "config": {"reps": REPS, "generations": GENS, "base_seed": BASE_SEED,
                   "presets": PRESETS, "r_star": rstars,
                   "churn_grid": CHURNS, "knockouts": [k[0] for k in KNOCKOUTS],
                   "strategies": len(TYPES), "N": N,
                   "duration_seconds": round(time.time() - started, 1)},
        "cells": {f"preset={p}|churn={c}|{lab}": v
                  for (p, c, lab), v in cells.items()},
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\nSaved → ./output/phase_sweep_{stamp}.json  "
          f"({payload['config']['duration_seconds']}s)")

    # Whole grid finished → drop the checkpoint so a re-run starts clean.
    try:
        os.remove(CKPT_PATH)
        print(f"✓ checkpoint 已清除 ({CKPT_PATH})")
    except OSError:
        pass


if __name__ == "__main__":
    main()
