"""
雙軸甜蜜點 — 合成「自己不吃虧 (個人穩健)」× 「社會也好 (社會信任)」。

純讀兩份 JSON、零模擬:
  • X 軸 = 個人穩健:既有策略擂台對 melee sweep 算的 CVaR-maximin composite
            (capital + W·survived)。直接呼叫 strategy_arena 的同一條公式, 保證與既有
            擂台結論逐名一致 (melee CVaR 冠軍應 = Prober)。
  • Y 軸 = 社會信任:monomorphic sweep 的 good_share, 每策略跨 churn×knockout 格取
            CVaR-maximin (最壞命運下信任還守得住嗎)。

以各軸中位數切四象限, 找右上角「自己不吃虧 + 社會也好」的甜蜜點 (預期互惠型 Grudger/
Pavlov/TitForTwoTats 落右上;掠食者 Prober 落右下 X 高 Y 低 —— 這正是研究要凸顯的張力)。

用法 (純讀檔, 容器/本機皆可):
    docker compose run --rm simulator python -u experiments/sweet_spot.py
旋鈕 (env var):
    SWEET_MELEE=<path>   melee JSON (預設 output/ 最新 phase_sweep_*)
    SWEET_MONO=<path>    monomorphic JSON (預設 output/ 最新 monomorphic_sweep_*)
    SWEET_X_CVAR_K=5     X 軸 (melee) CVaR 取最差幾格 (對齊既有 arena 預設 5)
    SWEET_Y_CVAR_K=3     Y 軸 (mono) CVaR 取最差幾格 (9 格的最差 3)
"""
import glob
import json
import os
import statistics
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # for strategy_arena

import strategy_arena as arena   # noqa: E402  (X 軸復用既有擂台公式)

X_CVAR_K = int(os.getenv("SWEET_X_CVAR_K", "5"))
Y_CVAR_K = int(os.getenv("SWEET_Y_CVAR_K", "3"))


def _latest(pattern: str) -> str | None:
    """output/ 下符合 glob pattern 的最新檔路徑 (無則 None)。"""
    candidates = sorted(glob.glob(os.path.join(_ROOT, "output", pattern)))
    return candidates[-1] if candidates else None


def load_mono(path: str | None = None) -> tuple[dict, str]:
    """讀指定或 output/ 最新 monomorphic_sweep_*.json (排除 checkpoint)。

    回傳 (payload_dict, 實際讀取的路徑)。缺 cells / good_share 欄即明確報錯退出。
    """
    if path is None:
        path = _latest("monomorphic_sweep_[0-9]*.json")
        if not path:
            sys.exit("✗ output/ 找不到 monomorphic_sweep_*.json — 先跑 "
                     "experiments/monomorphic_sweep.py")
    with open(path) as f:
        payload = json.load(f)
    if not payload.get("cells"):
        sys.exit(f"✗ {path} 沒有 cells")
    sample_cell = next(iter(payload["cells"].values()))
    if "good_share" not in sample_cell.get("metrics", {}):
        sys.exit(f"✗ {path} 無 good_share 欄 —— 請以 monomorphic_sweep 重跑")
    return payload, path


def _cvar(values: list[float], k: int) -> float:
    """最差 k 格平均 (CVaR 軟化 maximin)。"""
    ordered = sorted(values)
    k_effective = min(k, len(ordered)) or 1
    return sum(ordered[:k_effective]) / k_effective


def x_axis(melee_payload: dict) -> tuple[dict, dict, str | None]:
    """X = 個人在 melee 的表現。復用 strategy_arena.build_matrix('composite')。

    散佈軸用**跨命運 mean**(典型值)而非 CVaR-maximin —— 因為 melee 含團滅格, CVaR
    對所有善良策略歸零 (13/16 並列 0), 當連續散佈軸不堪用、象限會失效。改用 mean 能區辨
    全 16 策略, 同時把 CVaR 保底值 (= 既有擂台 maximin 主指標) 留作附註欄, 資訊不丟。
    回傳 (mean_by_strategy, cvar_by_strategy, champion_name)。
    """
    arena.CVAR_K = X_CVAR_K
    matrix = arena.build_matrix(melee_payload, "composite")
    ranked = arena.maximin(matrix)        # [(name, cvar, worst_cell), ...] 已降序
    cvar_by_strategy = {name: cvar for name, cvar, _ in ranked}
    mean_by_strategy = {strategy_name: sum(row.values()) / len(row)
                        for strategy_name, row in matrix.items()}
    return mean_by_strategy, cvar_by_strategy, (ranked[0][0] if ranked else None)


def y_axis(mono_payload: dict) -> dict:
    """Y = 社會信任。mono cells → {strategy:{cell: good_share.mean}}, 每策略取 CVaR-K。

    回傳 {strategy: {"cvar","mean","low_trust_cells"}}。cell key 形如
    'strategy=Grudger|churn=0.0|none', 前綴拆出策略名, 其餘當該策略的 cell。
    """
    matrix: dict[str, dict] = {}
    for cell_key, cell in mono_payload["cells"].items():
        parts = cell_key.split("|", 1)
        strategy_name = parts[0].split("=", 1)[1]
        cell_within_strategy = parts[1] if len(parts) > 1 else cell_key
        matrix.setdefault(strategy_name, {})[cell_within_strategy] = \
            cell["metrics"]["good_share"]["mean"]
    result = {}
    for strategy_name, row in matrix.items():
        good_shares = list(row.values())
        result[strategy_name] = {
            "cvar": _cvar(good_shares, Y_CVAR_K),
            "mean": sum(good_shares) / len(good_shares) if good_shares else 0.0,
            "low_trust_cells": sum(1 for share in good_shares if share < 0.5),
        }
    return result


def quadrant(x: float, y: float, x_median: float, y_median: float) -> str:
    """以各軸中位數切四象限, 回傳象限標籤。"""
    high_x, high_y = x >= x_median, y >= y_median
    if high_x and high_y:
        return "右上★甜蜜點"
    if high_x and not high_y:
        return "右下(自私穩健)"
    if not high_x and high_y:
        return "左上(利社會但脆弱)"
    return "左下(兩頭空)"


def main() -> None:
    melee_path = os.getenv("SWEET_MELEE")
    if melee_path:
        with open(melee_path) as f:
            melee_payload = json.load(f)
    else:
        melee_payload, melee_path = arena.load_latest_sweep(None)
    mono_payload, mono_path = load_mono(os.getenv("SWEET_MONO"))

    x_scores, x_cvar, champion = x_axis(melee_payload)
    y_scores = y_axis(mono_payload)

    # 對齊兩邊策略名 (取交集; 缺漏明確報出, 不靜默 join)。
    common_strategies = sorted(set(x_scores) & set(y_scores))
    only_in_mono = sorted(set(y_scores) - set(x_scores))
    only_in_melee = sorted(set(x_scores) - set(y_scores))
    if only_in_mono or only_in_melee:
        print(f"⚠ 策略名不對齊 — 只在 mono: {only_in_mono} | 只在 melee: {only_in_melee}")
    if not common_strategies:
        sys.exit("✗ melee 與 mono 無共同策略, 無法合成雙軸")

    x_median = statistics.median(x_scores[name] for name in common_strategies)
    y_median = statistics.median(y_scores[name]["cvar"] for name in common_strategies)

    # 排序:各軸 min-max 正規化後取 (x_norm + y_norm) 降序 → 兩軸俱佳者浮頂。
    x_values = [x_scores[name] for name in common_strategies]
    y_values = [y_scores[name]["cvar"] for name in common_strategies]
    x_low, x_high = min(x_values), max(x_values)
    y_low, y_high = min(y_values), max(y_values)

    def _normalize(value: float, low: float, high: float) -> float:
        return (value - low) / (high - low) if high > low else 0.0

    ranked_strategies = sorted(
        common_strategies,
        key=lambda name: (_normalize(x_scores[name], x_low, x_high)
                          + _normalize(y_scores[name]["cvar"], y_low, y_high)),
        reverse=True)

    print(f"\n=== 雙軸甜蜜點 | X=個人(melee 跨命運均 composite) "
          f"Y=社會信任(mono CVaR-{Y_CVAR_K} good_share) ===")
    print(f"melee源: {os.path.basename(melee_path)} | mono源: {os.path.basename(mono_path)}")
    print(f"驗證錨點: melee CVaR-{X_CVAR_K} 保底冠軍 = {champion} "
          f"(應對齊既有 strategy_arena 結論)")
    print("X=跨命運典型個人表現(散佈軸); 保底CVaR=最壞命運下限(善良多歸0, 故不當散佈軸)\n")
    print(f"{'策略':<16} {'X個人典型':>9} {'保底CVaR':>8} {'Y社會信任':>10} {'Y-mean':>8} "
          f"{'#低信任':>7}  象限")
    print("-" * 86)
    sweet_spot_strategies = []
    for name in ranked_strategies:
        quad = quadrant(x_scores[name], y_scores[name]["cvar"], x_median, y_median)
        if quad.startswith("右上"):
            sweet_spot_strategies.append(name)
        print(f"{name:<16} {x_scores[name]:>9.3f} {x_cvar.get(name, 0):>8.3f} "
              f"{y_scores[name]['cvar']:>10.3f} {y_scores[name]['mean']:>8.3f} "
              f"{y_scores[name]['low_trust_cells']:>7}  {quad}")
    print(f"\n中位數: X={x_median:.3f}  Y={y_median:.3f}")
    print(f"→ 右上甜蜜點 (自己不吃虧 + 社會也好): "
          f"{', '.join(sweet_spot_strategies) if sweet_spot_strategies else '(無)'}")

    # ---- Persist JSON ----
    os.makedirs(os.path.join(_ROOT, "output"), exist_ok=True)
    stamp = os.path.basename(mono_path).replace("monomorphic_sweep_", "").replace(".json", "")
    out_path = os.path.join(_ROOT, "output", f"sweet_spot_{stamp}.json")
    points = [
        {"strategy": name,
         "x": round(x_scores[name], 4),
         "x_cvar": round(x_cvar.get(name, 0), 4),
         "y": round(y_scores[name]["cvar"], 4),
         "y_mean": round(y_scores[name]["mean"], 4),
         "low_trust_cells": y_scores[name]["low_trust_cells"],
         "quadrant": quadrant(x_scores[name], y_scores[name]["cvar"], x_median, y_median)}
        for name in ranked_strategies
    ]
    result = {
        "melee_source": os.path.basename(melee_path),
        "mono_source": os.path.basename(mono_path),
        "x_metric": "melee 跨命運均 composite (散佈軸)",
        "x_cvar_metric": f"melee CVaR-{X_CVAR_K} composite (保底, 既有擂台主指標)",
        "y_metric": f"mono CVaR-{Y_CVAR_K} good_share",
        "medians": {"x": round(x_median, 4), "y": round(y_median, 4)},
        "melee_cvar_champion": champion,
        "points": points,
        "sweet_spot": sweet_spot_strategies,
    }
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\nSaved → ./output/sweet_spot_{stamp}.json")


if __name__ == "__main__":
    main()
