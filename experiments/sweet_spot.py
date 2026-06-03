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


def _latest(pattern):
    cands = sorted(glob.glob(os.path.join(_ROOT, "output", pattern)))
    return cands[-1] if cands else None


def load_mono(path=None):
    """讀指定或 output/ 最新 monomorphic_sweep_*.json (排除 checkpoint)。"""
    if path is None:
        path = _latest("monomorphic_sweep_[0-9]*.json")
        if not path:
            sys.exit("✗ output/ 找不到 monomorphic_sweep_*.json — 先跑 "
                     "experiments/monomorphic_sweep.py")
    with open(path) as f:
        payload = json.load(f)
    if not payload.get("cells"):
        sys.exit(f"✗ {path} 沒有 cells")
    sample = next(iter(payload["cells"].values()))
    if "good_share" not in sample.get("metrics", {}):
        sys.exit(f"✗ {path} 無 good_share 欄 —— 請以 monomorphic_sweep 重跑")
    return payload, path


def _cvar(values, k):
    """最差 k 格平均 (CVaR 軟化 maximin)。"""
    s = sorted(values)
    kk = min(k, len(s)) or 1
    return sum(s[:kk]) / kk


def x_axis(melee_payload):
    """X = 個人在 melee 的表現。復用 strategy_arena.build_matrix('composite')。

    散佈軸用**跨命運 mean**(典型值)而非 CVaR-maximin —— 因為 melee 含團滅格, CVaR
    對所有善良策略歸零 (13/16 並列 0), 當連續散佈軸不堪用、象限會失效。改用 mean 能區辨
    全 16 策略, 同時把 CVaR 保底值 (= 既有擂台 maximin 主指標) 留作附註欄, 資訊不丟。
    回傳 (mean:{strategy:score}, cvar:{strategy:score}, champion_name)。
    """
    arena.CVAR_K = X_CVAR_K
    matrix = arena.build_matrix(melee_payload, "composite")
    mm = arena.maximin(matrix)            # [(name, cvar, worst_cell), ...] 已降序
    cvar = {n: c for n, c, _ in mm}
    mean = {s: sum(row.values()) / len(row) for s, row in matrix.items()}
    return mean, cvar, (mm[0][0] if mm else None)


def y_axis(mono_payload):
    """Y = 社會信任。mono cells → {strategy:{cell: good_share.mean}}, 每策略取 CVaR-K。

    回傳 {strategy: {"cvar","mean","low_trust_cells"}}。cell key 形如
    'strategy=Grudger|churn=0.0|none', 前綴拆出策略名, 其餘當該策略的 cell。
    """
    matrix = {}
    for cell_key, cell in mono_payload["cells"].items():
        parts = cell_key.split("|", 1)
        sname = parts[0].split("=", 1)[1]
        within = parts[1] if len(parts) > 1 else cell_key
        matrix.setdefault(sname, {})[within] = cell["metrics"]["good_share"]["mean"]
    out = {}
    for sname, row in matrix.items():
        vals = list(row.values())
        out[sname] = {
            "cvar": _cvar(vals, Y_CVAR_K),
            "mean": sum(vals) / len(vals) if vals else 0.0,
            "low_trust_cells": sum(1 for v in vals if v < 0.5),
        }
    return out


def quadrant(x, y, x_med, y_med):
    hi_x, hi_y = x >= x_med, y >= y_med
    if hi_x and hi_y:
        return "右上★甜蜜點"
    if hi_x and not hi_y:
        return "右下(自私穩健)"
    if not hi_x and hi_y:
        return "左上(利社會但脆弱)"
    return "左下(兩頭空)"


def main():
    melee_path = os.getenv("SWEET_MELEE")
    if melee_path:
        with open(melee_path) as f:
            melee_payload = json.load(f)
    else:
        melee_payload, melee_path = arena.load_latest_sweep(None)
    mono_payload, mono_path = load_mono(os.getenv("SWEET_MONO"))

    xs, x_cvar, champ = x_axis(melee_payload)
    ys = y_axis(mono_payload)

    # 對齊兩邊策略名 (取交集; 缺漏明確報出, 不靜默 join)。
    common = sorted(set(xs) & set(ys))
    missing_x = sorted(set(ys) - set(xs))
    missing_y = sorted(set(xs) - set(ys))
    if missing_x or missing_y:
        print(f"⚠ 策略名不對齊 — 只在 mono: {missing_x} | 只在 melee: {missing_y}")
    if not common:
        sys.exit("✗ melee 與 mono 無共同策略, 無法合成雙軸")

    x_med = statistics.median(xs[s] for s in common)
    y_med = statistics.median(ys[s]["cvar"] for s in common)

    # 排序:各軸 min-max 正規化後取 (x_norm + y_norm) 降序 → 兩軸俱佳者浮頂。
    x_vals = [xs[s] for s in common]
    y_vals = [ys[s]["cvar"] for s in common]
    x_lo, x_hi = min(x_vals), max(x_vals)
    y_lo, y_hi = min(y_vals), max(y_vals)

    def _norm(v, lo, hi):
        return (v - lo) / (hi - lo) if hi > lo else 0.0

    rows = sorted(
        common,
        key=lambda s: _norm(xs[s], x_lo, x_hi) + _norm(ys[s]["cvar"], y_lo, y_hi),
        reverse=True)

    print(f"\n=== 雙軸甜蜜點 | X=個人(melee 跨命運均 composite) "
          f"Y=社會信任(mono CVaR-{Y_CVAR_K} good_share) ===")
    print(f"melee源: {os.path.basename(melee_path)} | mono源: {os.path.basename(mono_path)}")
    print(f"驗證錨點: melee CVaR-{X_CVAR_K} 保底冠軍 = {champ} "
          f"(應對齊既有 strategy_arena 結論)")
    print("X=跨命運典型個人表現(散佈軸); 保底CVaR=最壞命運下限(善良多歸0, 故不當散佈軸)\n")
    print(f"{'策略':<16} {'X個人典型':>9} {'保底CVaR':>8} {'Y社會信任':>10} {'Y-mean':>8} "
          f"{'#低信任':>7}  象限")
    print("-" * 86)
    sweet = []
    for s in rows:
        q = quadrant(xs[s], ys[s]["cvar"], x_med, y_med)
        if q.startswith("右上"):
            sweet.append(s)
        print(f"{s:<16} {xs[s]:>9.3f} {x_cvar.get(s, 0):>8.3f} {ys[s]['cvar']:>10.3f} "
              f"{ys[s]['mean']:>8.3f} {ys[s]['low_trust_cells']:>7}  {q}")
    print(f"\n中位數: X={x_med:.3f}  Y={y_med:.3f}")
    print(f"→ 右上甜蜜點 (自己不吃虧 + 社會也好): "
          f"{', '.join(sweet) if sweet else '(無)'}")

    # ---- Persist JSON ----
    os.makedirs(os.path.join(_ROOT, "output"), exist_ok=True)
    stamp = os.path.basename(mono_path).replace("monomorphic_sweep_", "").replace(".json", "")
    out_path = os.path.join(_ROOT, "output", f"sweet_spot_{stamp}.json")
    result = {
        "melee_source": os.path.basename(melee_path),
        "mono_source": os.path.basename(mono_path),
        "x_metric": "melee 跨命運均 composite (散佈軸)",
        "x_cvar_metric": f"melee CVaR-{X_CVAR_K} composite (保底, 既有擂台主指標)",
        "y_metric": f"mono CVaR-{Y_CVAR_K} good_share",
        "medians": {"x": round(x_med, 4), "y": round(y_med, 4)},
        "melee_cvar_champion": champ,
        "points": [
            {"strategy": s, "x": round(xs[s], 4), "x_cvar": round(x_cvar.get(s, 0), 4),
             "y": round(ys[s]["cvar"], 4), "y_mean": round(ys[s]["mean"], 4),
             "low_trust_cells": ys[s]["low_trust_cells"],
             "quadrant": quadrant(xs[s], ys[s]["cvar"], x_med, y_med)}
            for s in rows],
        "sweet_spot": sweet,
    }
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\nSaved → ./output/sweet_spot_{stamp}.json")


if __name__ == "__main__":
    main()
