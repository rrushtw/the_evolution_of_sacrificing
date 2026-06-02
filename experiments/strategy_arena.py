"""
Strategy arena — 把「環境相圖」翻成「策略擂台」(策略當主體,非環境)。

phase_sweep.py 跑出的 JSON 裡, 每個環境格子 (preset × churn × knockout) 都帶
per-strategy 明細 (share / capital / age / survived)。本腳本「純讀那份 JSON、零模擬」,
把它轉成「策略 × 環境」矩陣, 算個人決策者該看的穩健性準則:

  • maximin        — 每策略跨所有環境取「最差表現」, 選最差也最不差者 (風險趨避;
                     「不知道命運會把我丟進哪種社會時, 學哪招最不會出錯」)。
  • minimax-regret — 每策略跨環境的最大「後悔值」(比該環境最優策略差多少) 取最小。
                     maximin 與它常選出不同策略, 那個分歧本身最有資訊量。
  • 環境排名       — 每策略當幾次冠軍格 / 進前 3 / 在幾格全滅。驗證 maximin 結論
                     是否被單一退化格綁架。

主指標預設 capital (採用該策略的個體之平均資本 = 「我過得好不好」, 非零和)。
可切 share (零和、反映香火能否傳下去): ARENA_METRIC=share。

⚠ 前提 (務必連同結論一起讀): 沙盒是「16 策略生態混戰」(非兩兩對局、非 invasion),
每策略表現都受同場其他 15 策略影響。故本擂台量的是「在當前 16 策略共存的社會中」
採用某策略的穩健性, 非脈絡無關的內在價值。增刪策略可能翻盤。

用法 (純讀檔, 本機/容器皆可, 不跑模擬):
    python -u experiments/strategy_arena.py
旋鈕 (env var):
    ARENA_METRIC=capital|share   主指標 (預設 capital)
    ARENA_SWEEP=<path>           指定輸入 JSON (預設取 output/ 最新 phase_sweep_*)
"""
import glob
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

METRIC = os.getenv("ARENA_METRIC", "capital")
_VALID_METRICS = ("capital", "share", "age", "survived")


def load_latest_sweep(path=None):
    """讀指定或 output/ 最新的 phase_sweep_*.json; 缺 per_strategy 欄 → 明確報錯。"""
    if path is None:
        # [0-9]* 排除 phase_sweep_checkpoint.json
        cands = sorted(glob.glob(os.path.join(_ROOT, "output", "phase_sweep_[0-9]*.json")))
        if not cands:
            sys.exit("✗ output/ 找不到 phase_sweep_*.json — 先跑 experiments/phase_sweep.py")
        path = cands[-1]
    with open(path) as f:
        payload = json.load(f)
    cells = payload.get("cells", {})
    if not cells:
        sys.exit(f"✗ {path} 沒有 cells")
    sample = next(iter(cells.values()))
    if "per_strategy" not in sample:
        sys.exit(f"✗ {path} 是舊版 (無 per_strategy 欄) —— 請以新版 phase_sweep 重跑後再分析")
    return payload, path


def build_matrix(payload, metric):
    """回傳 {strategy: {cell_key: score}}, score 取該 cell 該策略該指標的 mean。"""
    matrix = {}
    for cell_key, cell in payload["cells"].items():
        for name, fields in cell["per_strategy"].items():
            matrix.setdefault(name, {})[cell_key] = fields[metric]["mean"]
    return matrix


def maximin(matrix):
    """每策略跨 cell 取 min + 記最差格; 降序 (分數越高越穩健)。"""
    out = []
    for name, row in matrix.items():
        worst_cell = min(row, key=row.get)
        out.append((name, row[worst_cell], worst_cell))
    return sorted(out, key=lambda t: t[1], reverse=True)


def minimax_regret(matrix):
    """每 cell 算 best; 每策略 max-regret + 發生格; 升序 (後悔越小越好)。"""
    cells = next(iter(matrix.values())).keys()
    best = {e: max(matrix[s][e] for s in matrix) for e in cells}
    out = []
    for name, row in matrix.items():
        regrets = {e: best[e] - row[e] for e in cells}
        worst_cell = max(regrets, key=regrets.get)
        out.append((name, regrets[worst_cell], worst_cell))
    return sorted(out, key=lambda t: t[1])


def env_rankings(matrix, survived):
    """每策略: #冠軍格 (該格 score 最高, 含並列) / #前3格 / #全滅格 (survived mean==0)。"""
    cells = next(iter(matrix.values())).keys()
    champ = {s: 0 for s in matrix}
    top3 = {s: 0 for s in matrix}
    extinct = {s: 0 for s in matrix}
    for e in cells:
        scores = {s: matrix[s][e] for s in matrix}
        best = max(scores.values())
        ordered = sorted(scores.values(), reverse=True)
        third = ordered[min(2, len(ordered) - 1)]
        for s in matrix:
            if scores[s] >= best:
                champ[s] += 1
            if scores[s] >= third:
                top3[s] += 1
            if survived[s][e] == 0.0:
                extinct[s] += 1
    return champ, top3, extinct


def print_arena_table(payload, metric):
    matrix = build_matrix(payload, metric)
    survived = build_matrix(payload, "survived")
    mm = maximin(matrix)
    regret = dict((n, (r, c)) for n, r, c in minimax_regret(matrix))
    champ, top3, extinct = env_rankings(matrix, survived)
    n_cells = len(next(iter(matrix.values())))

    cfg = payload.get("config", {})
    print(f"\n=== 策略擂台 | 主指標={metric} | {n_cells} 環境格 "
          f"(preset×churn×knockout) | reps={cfg.get('reps', '?')} ===")
    print("⚠ 量的是『在當前 16 策略共存社會中』採用某策略的穩健性, 非脈絡無關內在價值。\n")
    print(f"{'策略':<16} {'maximin↑':>9} {'最差格':<34} {'mean':>6} "
          f"{'maxRegret↓':>10} {'#冠軍':>5} {'#前3':>5} {'#全滅':>5}")
    print("-" * 100)
    for name, mmval, worst in mm:
        row = matrix[name]
        mean = sum(row.values()) / len(row)
        reg, _ = regret[name]
        print(f"{name:<16} {mmval:>9.3f} {worst:<34} {mean:>6.3f} "
              f"{reg:>10.3f} {champ[name]:>5} {top3[name]:>5} {extinct[name]:>5}")

    mm_winner = mm[0]
    rg = minimax_regret(matrix)[0]
    print(f"\n→ maximin 冠軍: {mm_winner[0]} (最壞 {metric}={mm_winner[1]:.3f} @ {mm_winner[2]})")
    print(f"→ minimax-regret 冠軍: {rg[0]} (最大後悔 {rg[1]:.3f} @ {rg[2]})")
    if mm_winner[0] != rg[0]:
        print("  (兩準則選出不同策略 —— maximin 保絕對下限, regret 保『不比當下最優差太多』)")
    return matrix, mm, regret, (champ, top3, extinct)


def main():
    if METRIC not in _VALID_METRICS:
        sys.exit(f"✗ ARENA_METRIC={METRIC} 不合法, 須為 {_VALID_METRICS}")
    payload, path = load_latest_sweep(os.getenv("ARENA_SWEEP"))
    print(f"讀入: {path}")
    matrix, mm, regret, ranks = print_arena_table(payload, METRIC)

    # 存一份分析快照 (純衍生自 sweep JSON)。
    champ, top3, extinct = ranks
    stamp = os.path.basename(path).replace("phase_sweep_", "").replace(".json", "")
    out_path = os.path.join(_ROOT, "output", f"strategy_arena_{stamp}.json")
    result = {
        "source": os.path.basename(path),
        "metric": METRIC,
        "n_cells": len(next(iter(matrix.values()))),
        "maximin": [{"strategy": n, "score": v, "worst_cell": c} for n, v, c in mm],
        "minimax_regret": [{"strategy": n, "max_regret": r, "worst_cell": c}
                           for n, r, c in minimax_regret(matrix)],
        "env_rankings": {s: {"champion": champ[s], "top3": top3[s], "extinct": extinct[s]}
                         for s in matrix},
    }
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\nSaved → ./output/strategy_arena_{stamp}.json")


if __name__ == "__main__":
    main()
