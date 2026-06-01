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
    CHURN_GRID=0.0,0.1,0.3,0.6,1.0   village → 北漂 → metropolis
    RANDOM_SEED=12345       base seed; replicate i uses RANDOM_SEED+i
                            (same seeds reused across cells = paired contrasts)
    JOBS=<cpu count>        parallel worker processes (replicates run in parallel)

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

TYPES = simulation.load_all_strategies()
N = len(TYPES) * GameConfig.INITIAL_COPIES


def _one_run(churn, blind_rep, blind_priv, seed):
    random.seed(seed)
    GameConfig.BLIND_REPUTATION = blind_rep
    GameConfig.BLIND_PRIVATE = blind_priv
    last = {}
    result = simulation.run_evolution(
        TYPES, churn_rate=churn, max_generations=GENS,
        on_generation=lambda g, s: last.update(s))
    fc = result["final_counts"]
    total = sum(fc.values()) or 1
    winner = max(fc, key=fc.get) if fc else None
    return {
        "nice": sum(v for k, v in fc.items() if k in NICE) / total,
        "capital_mean": last.get("capital_mean", 0.0),
        "gini": last.get("capital_gini", 0.0),
        "reenc": last.get("re_encounter_rate", 0.0),
        "expl": float(last.get("exploitations", 0)),
        "winner": winner,
    }


def _worker(task):
    """One replicate, run in its own process. Returns (churn, label, metrics)."""
    churn, label, blind_rep, blind_priv, seed = task
    return churn, label, _one_run(churn, blind_rep, blind_priv, seed)


def _agg(xs):
    m = statistics.mean(xs)
    sd = statistics.stdev(xs) if len(xs) > 1 else 0.0
    ci = 1.96 * sd / (len(xs) ** 0.5) if len(xs) > 1 else 0.0
    return {"mean": round(m, 4), "std": round(sd, 4), "ci95": round(ci, 4)}


def main():
    tasks = [(churn, label, br, bp, BASE_SEED + i)
             for churn in CHURNS
             for label, br, bp in KNOCKOUTS
             for i in range(REPS)]
    jobs = int(os.getenv("JOBS", str(multiprocessing.cpu_count() or 1)))
    print(f"Batch phase-sweep | strategies={len(TYPES)} N={N} | REPS={REPS} "
          f"GENS={GENS} base_seed={BASE_SEED} jobs={jobs}")
    print(f"churn grid: {CHURNS} | knockouts: {[k[0] for k in KNOCKOUTS]}")
    print(f"total runs = {len(tasks)}\n")

    started = time.time()
    # Replicates are independent and each self-seeds → run them in parallel.
    by_cell = defaultdict(list)
    with multiprocessing.Pool(jobs) as pool:
        done = 0
        step = max(1, len(tasks) // 20)
        for churn, label, m in pool.imap_unordered(_worker, tasks):
            by_cell[(churn, label)].append(m)
            done += 1
            if done % step == 0 or done == len(tasks):
                print(f"  {done}/{len(tasks)} runs done "
                      f"({time.time() - started:.0f}s)")

    cells = {}            # (churn, label) -> aggregated metrics + winners
    for key, runs in by_cell.items():
        metrics = {k: _agg([r[k] for r in runs])
                   for k in ("nice", "capital_mean", "gini", "reenc", "expl")}
        winners = {}
        for r in runs:
            winners[r["winner"]] = winners.get(r["winner"], 0) + 1
        metrics["top_winner"] = max(winners, key=winners.get)
        cells[key] = {"metrics": metrics, "winners": winners}

    # ---- Console tables ----
    print(f"\n=== nice%  (mean ± 95% CI, n={REPS}) ===")
    head = "churn |" + "".join(f" {lab:>16} |" for lab, _, _ in KNOCKOUTS)
    print(head)
    for churn in CHURNS:
        row = f"{churn:>5} |"
        for label, _, _ in KNOCKOUTS:
            m = cells[(churn, label)]["metrics"]["nice"]
            row += f" {m['mean']:>6.0%} ± {m['ci95']:>4.0%} |"
        print(row)

    print(f"\n=== no-knockout society profile (mean ± 95% CI, n={REPS}) ===")
    print("churn |   reenc%    |   nice%     |   gini      | expl/round")
    for churn in CHURNS:
        m = cells[(churn, "none")]["metrics"]
        print(f"{churn:>5} | "
              f"{m['reenc']['mean']:>5.0%}±{m['reenc']['ci95']:>3.0%} | "
              f"{m['nice']['mean']:>5.0%}±{m['nice']['ci95']:>3.0%} | "
              f"{m['gini']['mean']:>4.2f}±{m['gini']['ci95']:>4.2f} | "
              f"{m['expl']['mean']:>5.1f}±{m['expl']['ci95']:>4.1f}")

    # ---- Persist JSON ----
    os.makedirs(os.path.join(_ROOT, "output"), exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(_ROOT, "output", f"phase_sweep_{stamp}.json")
    payload = {
        "config": {"reps": REPS, "generations": GENS, "base_seed": BASE_SEED,
                   "churn_grid": CHURNS, "knockouts": [k[0] for k in KNOCKOUTS],
                   "strategies": len(TYPES), "N": N,
                   "duration_seconds": round(time.time() - started, 1)},
        "cells": {f"churn={c}|{lab}": v for (c, lab), v in cells.items()},
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\nSaved → ./output/phase_sweep_{stamp}.json  "
          f"({payload['config']['duration_seconds']}s)")


if __name__ == "__main__":
    main()
