"""
單型社會福祉 sweep — 「假設大家都採用策略 X, 那會是好社會還是地獄?」

策略擂台 (experiments/strategy_arena.py) 答的是「在 16 策略零和混戰裡, 我個人怎樣最不
吃虧」(掠食者 Prober 勝)。本實驗補另一半:把整個族群換成「全部都是策略 X」的**單型社會**,
跑到穩態, 量這個社會的**信任/合作水準**。雙軸合成在 experiments/sweet_spot.py。

為何不用 simulation.run_evolution:它有 `len(surviving)<=1 → break("winner")` 早停
(simulation.py:281-283)。單型族群只有 1 個 species → 第 1 代跑完就早停, 到不了穩態。
故本檔**自驅 engine.run_round 的薄 loop**:固定族群、不繁殖、不死亡 (單型繁殖無意義), 只保留
recover() 讓 capital 有均衡, 跑滿 T 代到行為穩態。engine / network / 統計函式全唯讀復用,
**零引擎改動**。

社會福祉主訊號 = good_share (穩態 GOOD 名聲佔比 = 信任/合作率):
  全 Altruist → 互相吹哨 → 全 GOOD → 1 (天堂);全 Cheater → 互相背叛 → 全 BAD → 0 (地獄)。
  注意 nice% (策略佔比) 在單型退化 (恆 100%/0%), 不可當合作率 —— 故改用行為層的 good_share。
  capital_mean / expl_norm / gini 一併記錄為輔, 分析器可事後換主訊號重算, 不必重跑。

命運格 = churn (社會流動度) × knockout (資訊管道關閉)。preset 不納:策略 decide() 看不到
capital / 存活參數 (base_strategy.py:64-70), 故 preset (只改 SURVIVAL_*/c-b) 不影響 good_share
的決策動態, 只影響 capital —— 對「信任率」這軸無意義。

用法 (容器內, 可續跑):
    docker compose run --rm simulator python -u experiments/monomorphic_sweep.py
旋鈕 (env var):
    MONO_REPS=30              每格重複次數
    MONO_GENERATIONS=300      每 run 互動代數
    MONO_N=160               單型族群人數 (= melee N, 對齊社會規模; 勿用 10, 雜訊爆表)
    MONO_TAIL=50             末 K 代平均窗 (壓單型初始條件雜訊)
    MONO_CHURN_GRID=0.0,0.3,1.0       村莊 / 中間 / 大都會
    MONO_KNOCKOUTS=none,-reputation,-private   資訊管道壓力測試
    MONO_CVAR_K=3            console 預覽:跨格取最差 K 格 good_share 平均 (maximin 軟化)
    RANDOM_SEED=12345        replicate i 用 RANDOM_SEED+i
    JOBS=<cpu>               平行 worker 數
    CHECKPOINT_FILE=output/monomorphic_sweep_checkpoint.json
"""
import json
import multiprocessing
import os
import statistics
import sys
import time
from collections import defaultdict, deque
from datetime import datetime

# Make the repo root importable regardless of where we're launched from.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import random                              # noqa: E402
import engine                              # noqa: E402
import network                             # noqa: E402
import simulation                          # noqa: E402
from definitions import GameConfig         # noqa: E402
from phase_sweep import _apply_preset, _agg   # noqa: E402  (復用, 不複製)
from simulation import _reputation_distribution, _capital_stats  # noqa: E402

REPS = int(os.getenv("MONO_REPS", "30"))
GENS = int(os.getenv("MONO_GENERATIONS", "300"))
BASE_SEED = int(os.getenv("RANDOM_SEED", "12345"))
MONO_N = int(os.getenv("MONO_N", "160"))
TAIL = int(os.getenv("MONO_TAIL", "50"))
CVAR_K = int(os.getenv("MONO_CVAR_K", "3"))
CHURNS = [float(x) for x in os.getenv("MONO_CHURN_GRID", "0.0,0.3,1.0").split(",")]
_ALL_KNOCKOUTS = [
    ("none", False, False),
    ("-reputation", True, False),
    ("-private", False, True),
]
_KO_FILTER = [s.strip() for s in
              os.getenv("MONO_KNOCKOUTS", "none,-reputation,-private").split(",")
              if s.strip()]
KNOCKOUTS = [k for k in _ALL_KNOCKOUTS if k[0] in _KO_FILTER]

TYPES = simulation.load_all_strategies()
STRATEGY_BY_NAME = {t.__name__: t for t in TYPES}
STRATEGY_NAMES = sorted(STRATEGY_BY_NAME)


def _one_run(strategy_cls, churn, blind_rep, blind_priv, seed):
    """一個 (策略, churn, knockout, seed) 複本:單型族群跑 T 代, 回末 K 代平均的社會福祉。

    自驅 engine.run_round —— 固定 N 人、不繁殖不死亡, 繞開 run_evolution 的單型早停。
    每代設定即覆寫 (preset/BLIND_*), 不必還原:下一個 run 開頭一律重設。
    """
    random.seed(seed)
    _apply_preset("default")
    GameConfig.BLIND_REPUTATION = blind_rep
    GameConfig.BLIND_PRIVATE = blind_priv

    pop = [strategy_cls() for _ in range(MONO_N)]
    net = network.Network(pop, GameConfig.AVG_DEGREE, GameConfig.ASSORTMENT)

    tail = deque(maxlen=TAIL)
    warmup = max(0, GENS - TAIL)   # 只在末 K 代收統計 (前面是 burn-in)
    for g in range(GENS):
        stats = engine.run_round(
            pop, net,
            noise=GameConfig.NOISE_RATE,
            encounters_per_agent=GameConfig.ENCOUNTERS_PER_AGENT,
            churn_rate=churn,
        )
        for agent in pop:
            agent.recover()
        if g >= warmup:
            rep = _reputation_distribution(pop)   # {"Good": n, "Bad": n}
            good = rep.get("Good", 0)
            denom = sum(rep.values())
            cap = _capital_stats(pop)
            # gini 不收:無 mortality 下 capital 可為負, 而 _gini 假設非負 → 對負值失真。
            tail.append({
                "good_share": (good / denom) if denom else 0.0,
                "expl": float(stats["exploitations"]),
                "capital_mean": cap["capital_mean"],
            })

    def _mean(field):
        return sum(t[field] for t in tail) / len(tail) if tail else 0.0

    expl = _mean("expl")
    return {
        "good_share": _mean("good_share"),
        "expl": expl,
        "expl_norm": min(1.0, expl / MONO_N),
        "capital_mean": _mean("capital_mean"),
    }


def _worker(task):
    """One replicate, own process. Returns (key, sname, churn, label, metrics)."""
    sname, churn, label, blind_rep, blind_priv, seed = task
    key = _run_key(sname, churn, label, seed)
    cls = STRATEGY_BY_NAME[sname]
    return key, sname, churn, label, _one_run(cls, churn, blind_rep, blind_priv, seed)


# ---- Checkpoint (resumable across interrupts) -------------------------------
CKPT_PATH = os.getenv(
    "CHECKPOINT_FILE",
    os.path.join(_ROOT, "output", "monomorphic_sweep_checkpoint.json"))


def _run_key(sname, churn, label, seed):
    return f"{sname}|{churn}|{label}|{seed}"


def _signature():
    """Config fingerprint; mismatch → old checkpoint can't be reused."""
    return {"reps": REPS, "generations": GENS, "base_seed": BASE_SEED,
            "churn_grid": CHURNS, "knockouts": [k[0] for k in KNOCKOUTS],
            "N": MONO_N, "tail": TAIL, "strategies": len(STRATEGY_NAMES)}


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


def _cvar(values, k):
    """最差 k 格平均 (CVaR 軟化 maximin);k>=len 即取全部 = mean。"""
    s = sorted(values)
    kk = min(k, len(s)) or 1
    return sum(s[:kk]) / kk


def main():
    all_tasks = [(sname, churn, label, br, bp, BASE_SEED + i)
                 for sname in STRATEGY_NAMES
                 for churn in CHURNS
                 for label, br, bp in KNOCKOUTS
                 for i in range(REPS)]
    jobs = int(os.getenv("JOBS", str(multiprocessing.cpu_count() or 1)))
    total = len(all_tasks)

    done_runs = _load_checkpoint()
    by_cell = defaultdict(list)
    for rec in done_runs.values():
        by_cell[(rec["sname"], rec["churn"], rec["label"])].append(rec["metrics"])
    tasks = [t for t in all_tasks
             if _run_key(t[0], t[1], t[2], t[5]) not in done_runs]

    print(f"Monomorphic sweep | strategies={len(STRATEGY_NAMES)} N={MONO_N} | "
          f"REPS={REPS} GENS={GENS} tail={TAIL} base_seed={BASE_SEED} jobs={jobs}")
    print(f"churn grid: {CHURNS} | knockouts: {[k[0] for k in KNOCKOUTS]} | preset=default")
    if done_runs:
        print(f"resume: {len(done_runs)}/{total} 已完成 (checkpoint {CKPT_PATH}),"
              f" 續跑剩 {len(tasks)}")
    print(f"total runs = {total}\n")

    started = time.time()
    flush_every = max(1, jobs)
    with multiprocessing.Pool(jobs) as pool:
        done = len(done_runs)
        since_flush = 0
        step = max(1, total // 20)
        for key, sname, churn, label, m in pool.imap_unordered(_worker, tasks):
            by_cell[(sname, churn, label)].append(m)
            done_runs[key] = {"sname": sname, "churn": churn,
                              "label": label, "metrics": m}
            done += 1
            since_flush += 1
            if since_flush >= flush_every:
                _save_checkpoint(done_runs)
                since_flush = 0
            if done % step == 0 or done == total:
                print(f"  {done}/{total} runs done ({time.time() - started:.0f}s)")
    _save_checkpoint(done_runs)

    # ---- Aggregate cells ----
    cells = {}
    for key, runs in by_cell.items():
        metrics = {k: _agg([r[k] for r in runs])
                   for k in ("good_share", "expl_norm", "capital_mean")}
        cells[key] = {"metrics": metrics}

    # ---- Console: 每策略跨格 good_share + CVaR-maximin 排行 ----
    labels = [k[0] for k in KNOCKOUTS]
    matrix = {s: {} for s in STRATEGY_NAMES}   # {strategy: {cellkey: good_share.mean}}
    for (s, c, lab), v in cells.items():
        matrix[s][f"churn={c}|{lab}"] = v["metrics"]["good_share"]["mean"]

    ranking = []
    for s in STRATEGY_NAMES:
        vals = list(matrix[s].values())
        cvar = _cvar(vals, CVAR_K)
        mean = sum(vals) / len(vals) if vals else 0.0
        worst_cell = min(matrix[s], key=matrix[s].get) if matrix[s] else "-"
        ranking.append((s, cvar, mean, worst_cell))
    ranking.sort(key=lambda t: (t[1], t[2]), reverse=True)

    n_cells = len(CHURNS) * len(KNOCKOUTS)
    print(f"\n=== 單型社會福祉擂台 | Y=good_share (末{TAIL}代均) | "
          f"{n_cells}格(churn×knockout) reps={REPS} ===")
    print("⚠ 量的是『假設全社會都採用某策略』的穩態信任/合作率, 非混戰中個人表現。\n")
    print(f"{'策略':<16} {f'CVaR↑(最差{CVAR_K})':>13} {'mean':>7} {'最差格':<26}")
    print("-" * 70)
    for s, cvar, mean, worst in ranking:
        print(f"{s:<16} {cvar:>13.3f} {mean:>7.3f} {worst:<26}")
    print(f"\n→ 單型最宜居 (CVaR good_share 冠軍): {ranking[0][0]} "
          f"(CVaR={ranking[0][1]:.3f}, 最差格 @ {ranking[0][3]})")

    # 社會剖面 (none-knockout): 看 capital / expl 輔助訊號
    if "none" in labels:
        print(f"\n--- 社會剖面 | knockout=none (capital_mean / expl_norm, n={REPS}) ---")
        print("策略             " + "".join(f" churn={c:<4}" for c in CHURNS))
        for s in STRATEGY_NAMES:
            row = f"{s:<16}"
            for c in CHURNS:
                m = cells.get((s, c, "none"), {}).get("metrics")
                if m:
                    row += f" {m['capital_mean']['mean']:>4.1f}/{m['expl_norm']['mean']:>4.2f}"
                else:
                    row += "      -    "
            print(row)

    # ---- Persist JSON ----
    os.makedirs(os.path.join(_ROOT, "output"), exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(_ROOT, "output", f"monomorphic_sweep_{stamp}.json")
    payload = {
        "config": {"reps": REPS, "generations": GENS, "base_seed": BASE_SEED,
                   "churn_grid": CHURNS, "knockouts": labels,
                   "N": MONO_N, "tail": TAIL, "preset": "default",
                   "primary": "good_share", "cvar_k": CVAR_K,
                   "strategies": len(STRATEGY_NAMES),
                   "duration_seconds": round(time.time() - started, 1)},
        "cells": {f"strategy={s}|churn={c}|{lab}": v
                  for (s, c, lab), v in cells.items()},
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\nSaved → ./output/monomorphic_sweep_{stamp}.json  "
          f"({payload['config']['duration_seconds']}s)")

    try:
        os.remove(CKPT_PATH)
        print(f"✓ checkpoint 已清除 ({CKPT_PATH})")
    except OSError:
        pass


if __name__ == "__main__":
    main()
