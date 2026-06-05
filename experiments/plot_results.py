"""
把現有實驗 JSON 畫成全套文章用圖(matplotlib 純讀檔, 不跑模擬)。

讀 output/*.json → 出 results/figures/*.png。每張圖一個函式, 缺對應 JSON 就跳過
(不阻塞)。給 README 嵌入 + Threads 配圖用。

五張圖:
  1. phase_transition.png  相變主圖:nice% vs churn, 三線(none/-reputation/-private)+95%CI
  2. society_profile.png   社會剖面:churn 軸, 雙 y(再相遇率 ↓ vs 剝削/回合 ↑)
  3. sweet_spot.png        策略擂台甜蜜點散佈:個人 × 社會信任, 象限, Sheriff ★
  4. redemption_arc.png    入侵救贖弧線:Sheriff/good_share 對世代(谷底→回升)
  5. institution_effect.png 第三方制度:nice% vs 制度強度(制度救得回都會嗎)+ 洗白份額崩

用法(容器內, 需 matplotlib + CJK 字型, 見 Dockerfile):
    docker compose run --rm simulator python -u experiments/plot_results.py
"""
import glob
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt   # noqa: E402

# 繁中標題字型(Dockerfile 已裝 fonts-noto-cjk);列多語 fallback。
matplotlib.rcParams["font.sans-serif"] = [
    "Noto Sans CJK TC", "Noto Sans CJK SC", "Noto Sans CJK JP",
    "Noto Sans CJK KR", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(_ROOT, "output")
FIG_DIR = os.path.join(_ROOT, "results", "figures")

# 配色(色盲友善)
C_NONE = "#1b9e77"        # 完整(none)
C_REP = "#d95f02"         # 關名聲(-reputation)= 主賣點崩潰線
C_PRIV = "#7570b3"        # 關私記憶(-private)
C_SHERIFF = "#d95f02"
C_GOOD = "#1b9e77"
C_INST = "#d95f02"


def _load(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def _latest(pattern: str) -> str | None:
    files = [f for f in glob.glob(os.path.join(OUT_DIR, pattern))
             if "checkpoint" not in os.path.basename(f)]
    return max(files, key=os.path.getmtime) if files else None


def _canonical_phase_sweep() -> str | None:
    """挑「相變主圖」要用的 phase_sweep —— 統一重跑的 assort=0.0 誠實基準。

    2026-06 統一重跑後, assortment 升為顯式掃描軸。相變主圖固定取 **assort=0.0**
    的 well-mixed 基準(結構不幫忙、純看名聲的作用):村莊靠私記憶撐、churn 升高後
    名聲成為命脈、關掉名聲在都會崩到趨近 0。退回舊邏輯只在無 assortment 顯式檔時。
    """
    by_assort = _assortment_phase_sweeps()
    if 0.0 in by_assort:
        return by_assort[0.0]
    # 退回:無顯式 assortment 檔時, 挑 churn_grid 最長 / 最新的 baseline。
    files = glob.glob(os.path.join(OUT_DIR, "phase_sweep_*.json"))
    best, best_key = None, None
    for path in files:
        try:
            config = _load(path)["config"]
            key = (config.get("strategies", 0),
                   len(config["churn_grid"]),
                   0 if config.get("presets") else 1,   # baseline(無 preset)優先
                   os.path.getmtime(path))
        except (KeyError, json.JSONDecodeError, OSError):
            continue
        if best_key is None or key > best_key:
            best, best_key = path, key
    return best


def _phase_metric(data: dict, churn: float, ko: str, field: str) -> dict | None:
    """讀 phase_sweep cell 的某指標, 相容兩種 key schema(有/無 preset 前綴)。"""
    cells = data["cells"]
    for key in (f"churn={churn}|{ko}", f"preset=default|churn={churn}|{ko}"):
        if key in cells:
            return cells[key]["metrics"][field]
    return None


def _save(fig, name: str) -> None:
    os.makedirs(FIG_DIR, exist_ok=True)
    path = os.path.join(FIG_DIR, name)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ {os.path.relpath(path, _ROOT)}")


# ---- 1. 相變主圖 -----------------------------------------------------------
def plot_phase_transition() -> None:
    path = _canonical_phase_sweep()
    if not path:
        print("  - phase_transition: 無 phase_sweep JSON, 跳過")
        return
    data = _load(path)
    churns = data["config"]["churn_grid"]
    lines = [("none", C_NONE, "完整(有名聲)"),
             ("-reputation", C_REP, "關掉公共名聲"),
             ("-private", C_PRIV, "關掉私人記憶")]

    fig, ax = plt.subplots(figsize=(7.5, 5))
    for label, color, zh in lines:
        means, cis = [], []
        for churn in churns:
            m = _phase_metric(data, churn, label, "nice")
            means.append(m["mean"] * 100)
            cis.append(m["ci95"] * 100)
        xs = churns
        ax.plot(xs, means, "-o", color=color, label=zh, linewidth=2, markersize=5)
        ax.fill_between(xs,
                        [m - c for m, c in zip(means, cis)],
                        [m + c for m, c in zip(means, cis)],
                        color=color, alpha=0.15)
    ax.set_xlabel("社會流動度 churn(0 = 村莊 ←→ 1 = 都會)")
    ax.set_ylabel("合作率 nice%(善良策略族群佔比)")
    ax.set_title("Well-mixed 社會(無同類結伴):公共名聲是合作的地基\n"
                 "關掉名聲 → 合作全程崩到趨近 0(連村莊都救不回)")
    ax.set_ylim(0, 100)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper right", framealpha=0.9)
    ax.annotate("關掉公共名聲\n合作全程趨近 0", xy=(0.5, 1),
                xytext=(0.5, 20),
                arrowprops=dict(arrowstyle="->", color=C_REP),
                color=C_REP, fontsize=9, ha="center")
    _save(fig, "phase_transition.png")


# ---- 2. 社會剖面 -----------------------------------------------------------
def plot_society_profile() -> None:
    path = _canonical_phase_sweep()
    if not path:
        print("  - society_profile: 無 phase_sweep JSON, 跳過")
        return
    data = _load(path)
    churns = data["config"]["churn_grid"]
    reenc, expl = [], []
    for churn in churns:
        reenc.append(_phase_metric(data, churn, "none", "reenc")["mean"] * 100)
        expl.append(_phase_metric(data, churn, "none", "expl")["mean"])

    fig, ax1 = plt.subplots(figsize=(7.5, 5))
    ax1.plot(churns, reenc, "-o", color=C_NONE, linewidth=2, label="再相遇率 ↓")
    ax1.set_xlabel("社會流動度 churn(0 = 村莊 ←→ 1 = 都會)")
    ax1.set_ylabel("再相遇率 %(還會碰到同一人)", color=C_NONE)
    ax1.tick_params(axis="y", labelcolor=C_NONE)
    ax1.set_ylim(0, max(reenc) * 1.2 + 1)

    ax2 = ax1.twinx()
    ax2.plot(churns, expl, "-s", color=C_REP, linewidth=2, label="剝削/回合 ↑")
    ax2.set_ylabel("剝削次數/回合(被佔便宜)", color=C_REP)
    ax2.tick_params(axis="y", labelcolor=C_REP)
    ax2.set_ylim(0, max(expl) * 1.2 + 1)

    ax1.set_title("村莊 → 都會:越流動,越少重逢、越多剝削")
    ax1.grid(True, alpha=0.3)
    _save(fig, "society_profile.png")


# ---- 3. 策略擂台甜蜜點散佈 --------------------------------------------------
def plot_sweet_spot() -> None:
    path = _latest("sweet_spot_*.json")
    if not path:
        print("  - sweet_spot: 無 sweet_spot JSON, 跳過")
        return
    data = _load(path)
    xm, ym = data["medians"]["x"], data["medians"]["y"]

    fig, ax = plt.subplots(figsize=(8, 6))
    for point in data["points"]:
        name = point["strategy"]
        x, y = point["x"], point["y"]
        is_sheriff = name == "Sheriff"
        ax.scatter(x, y, s=200 if is_sheriff else 60,
                   marker="*" if is_sheriff else "o",
                   color=C_REP if is_sheriff else "#555555",
                   zorder=5 if is_sheriff else 3,
                   edgecolors="black" if is_sheriff else "none", linewidths=1)
        ax.annotate(name, xy=(x, y), xytext=(4, 4),
                    textcoords="offset points",
                    fontsize=10 if is_sheriff else 8,
                    fontweight="bold" if is_sheriff else "normal",
                    color=C_REP if is_sheriff else "#333333")
    ax.axvline(xm, color="gray", linestyle="--", alpha=0.6)
    ax.axhline(ym, color="gray", linestyle="--", alpha=0.6)
    ax.text(0.99, 0.985, "右上 = 自己不吃虧 + 社會也好", transform=ax.transAxes,
            ha="right", va="top", fontsize=9, color=C_REP,
            bbox=dict(boxstyle="round", fc="#fff3e6", ec=C_REP, alpha=0.9))
    ax.set_xlabel("個人:跨命運典型表現(越右越不吃虧)")
    ax.set_ylabel("社會:最壞命運下的信任率(越上社會越好)")
    ax.set_title("哪個策略值得採用?Sheriff 是唯一甜蜜點\n(會合作、但你變壞就懲罰你)")
    ax.grid(True, alpha=0.25)
    _save(fig, "sweet_spot.png")


# ---- 4. 入侵救贖弧線 -------------------------------------------------------
def plot_redemption_arc() -> None:
    path = _latest("invasion_*.json")
    if not path:
        print("  - redemption_arc: 無 invasion JSON, 跳過")
        return
    data = _load(path)
    panels = [("Cheater", "Sheriff 20% 入侵「純騙子」世界"),
              ("Prober", "Sheriff 20% 入侵「試探者」世界")]
    available = [(p, t) for p, t in panels
                 if data["cells"].get(
                     f"matchup=Sheriff_vs_{p}|dir=redeem|frac=0.2|churn=0.0|none",
                     {}).get("representative_trajectory")]
    if not available:
        print("  - redemption_arc: invasion JSON 無代表軌跡, 跳過")
        return

    fig, axes = plt.subplots(1, len(available), figsize=(6.5 * len(available), 5),
                             squeeze=False)
    for ax, (predator, title) in zip(axes[0], available):
        traj = data["cells"][
            f"matchup=Sheriff_vs_{predator}|dir=redeem|frac=0.2|churn=0.0|none"
        ]["representative_trajectory"]
        gens = [pt["g"] for pt in traj]
        sheriff = [pt["sheriff_share"] * 100 for pt in traj]
        good = [pt["good_share"] * 100 for pt in traj]
        pred_share = [100 - s for s in sheriff]   # 兩物種對局:掠食者 = 1 − Sheriff
        ax.plot(gens, good, color=C_GOOD, linewidth=2, label="社會信任率")
        ax.plot(gens, sheriff, color=C_SHERIFF, linewidth=2, label="Sheriff 佔比")
        ax.plot(gens, pred_share, color="#666666", linewidth=2, linestyle="--",
                label=f"{predator}(掠食者)佔比")
        valley = min(good)
        v_idx = good.index(valley)
        ax.annotate(f"信任崩到谷底 {valley:.0f}%", xy=(gens[v_idx], valley),
                    xytext=(gens[v_idx] + max(gens) * 0.1, valley + 18),
                    arrowprops=dict(arrowstyle="->", color="gray"),
                    fontsize=9, color="#333333")
        ax.set_xlabel("世代")
        ax.set_ylabel("百分比 %")
        ax.set_title(title)
        ax.set_ylim(0, 105)
        ax.grid(True, alpha=0.3)
        ax.legend(loc="center right", framealpha=0.9)
    fig.suptitle("救贖弧線:社會得先看見自己的腐敗,執法者才救得回",
                 fontsize=13, y=1.02)
    _save(fig, "redemption_arc.png")


# ---- 5. 第三方制度效果 -----------------------------------------------------
def _inst_cell(data: dict, strength, churn, ko, strat_set, field, assort=0.0):
    """相容新(含 assort=)與舊(無 assort)cell key schema;預設取 assort=0.0 基準。"""
    cells = data["cells"]
    for key in (
            f"kind=grid|assort={assort}|strength={strength}|fp=0.0|churn={churn}|{ko}|set={strat_set}",
            f"kind=grid|strength={strength}|fp=0.0|churn={churn}|{ko}|set={strat_set}"):
        if key in cells:
            return cells[key][field]["mean"]
    return None


def plot_institution_effect() -> None:
    path = _latest("institution_sweep_*.json")
    if not path:
        print("  - institution_effect: 無 institution_sweep JSON, 跳過(待 #6 跑完)")
        return
    data = _load(path)
    strengths = data["config"]["strength_grid"]
    churn = 1.0 if 1.0 in data["config"]["churn_grid"] else data["config"]["churn_grid"][-1]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    # 左:制度能否在都會取代名聲?nice% vs strength, none vs -reputation
    for ko, color, zh in [("none", C_NONE, "有自發名聲"),
                          ("-reputation", C_REP, "關掉名聲(只剩制度)")]:
        ys = [_inst_cell(data, s, churn, ko, "full", "nice") for s in strengths]
        ys = [None if v is None else v * 100 for v in ys]
        ax1.plot(strengths, ys, "-o", color=color, linewidth=2, label=zh)
    ax1.set_xlabel("制度強度(每回合淘汰 BAD 的機率)")
    ax1.set_ylabel("合作率 nice%")
    ax1.set_title(f"都會(churn={churn}):制度能取代名聲嗎?\n關名聲時, 制度把崩潰的合作救回")
    ax1.set_ylim(0, 100)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc="best", framealpha=0.9)

    # 右:制度壓制洗白套利 — Whitewasher 份額 vs strength(full, none)
    ww = [_inst_cell(data, s, churn, "none", "full", "whitewasher_share")
          for s in strengths]
    ww = [None if v is None else v * 100 for v in ww]
    ax2.plot(strengths, ww, "-s", color=C_INST, linewidth=2)
    ax2.set_xlabel("制度強度(每回合淘汰 BAD 的機率)")
    ax2.set_ylabel("洗白者 Whitewasher 族群佔比 %")
    ax2.set_title(f"制度關閉洗白套利窗口(都會 churn={churn})\nBAD 一被標記就清掉")
    ax2.set_ylim(bottom=0)
    ax2.grid(True, alpha=0.3)
    _save(fig, "institution_effect.png")


def _assortment_phase_sweeps() -> dict:
    """收集「default preset + 有 assortment 欄 + churn_grid≥3」的統一重跑檔, 依 assortment 分組。"""
    by_assort: dict = {}
    for path in glob.glob(os.path.join(OUT_DIR, "phase_sweep_*.json")):
        try:
            config = _load(path)["config"]
            if "default" not in config.get("presets", []) \
                    or "assortment" not in config or len(config["churn_grid"]) < 3:
                continue
            a = config["assortment"]
        except (KeyError, json.JSONDecodeError, OSError):
            continue
        # 同 assortment 取最新
        if a not in by_assort or os.path.getmtime(path) > os.path.getmtime(by_assort[a]):
            by_assort[a] = path
    return by_assort


def plot_assortment_phase() -> None:
    """統一重跑:結構(assortment)× 名聲(knockout)× 流動(churn)的交互 —— 三者如何撐住合作。"""
    by_assort = _assortment_phase_sweeps()
    if len(by_assort) < 2:
        print("  - assortment_phase: 統一重跑檔 <2 種 assortment, 跳過")
        return
    assorts = sorted(by_assort)
    palette = ["#7570b3", "#1b9e77", "#d95f02"]   # 低→高 assortment
    knockouts = [("none", "完整(有名聲)"),
                 ("-reputation", "關掉公共名聲"),
                 ("-private", "關掉私人記憶")]

    fig, axes = plt.subplots(1, 3, figsize=(16, 5), sharey=True)
    for ax, (ko, zh) in zip(axes, knockouts):
        for a, color in zip(assorts, palette):
            data = _load(by_assort[a])
            churns = data["config"]["churn_grid"]
            means = [_phase_metric(data, c, ko, "nice")["mean"] * 100 for c in churns]
            ax.plot(churns, means, "-o", color=color, linewidth=2,
                    label=f"assortment {a}")
        ax.set_title(zh)
        ax.set_xlabel("社會流動度 churn(村莊→都會)")
        ax.set_ylim(0, 100)
        ax.grid(True, alpha=0.3)
    axes[0].set_ylabel("合作率 nice%")
    axes[1].legend(loc="upper right", framealpha=0.9)
    fig.suptitle("結構(同類結伴 assortment)與名聲是「部分替代品」"
                 "—— 高結伴時, 關掉名聲村莊仍撐得住",
                 fontsize=13, y=1.02)
    _save(fig, "assortment_phase.png")


# ---- 終端版救贖弧線(ASCII sparkline,給 README 文字/終端呈現)----------------
_SPARK = "▁▂▃▄▅▆▇█"   # 8 階 block 字元, 低→高


def _sparkline(values: list, width: int = 32) -> str:
    """把 0–1 序列降採樣到 width 格、映成等寬 block 字元(終端折線)。"""
    if not values:
        return ""
    if len(values) > width:
        step = (len(values) - 1) / (width - 1)
        values = [values[round(i * step)] for i in range(width)]
    out = []
    for v in values:
        idx = min(len(_SPARK) - 1, max(0, int(round(v * (len(_SPARK) - 1)))))
        out.append(_SPARK[idx])
    return "".join(out)


def ascii_redemption_arc() -> None:
    """印救贖弧線的 ASCII sparkline(信任/Sheriff/掠食者三序列), README code block 用。"""
    path = _latest("invasion_*.json")
    if not path:
        print("  - ascii_redemption_arc: 無 invasion JSON, 跳過")
        return
    data = _load(path)
    print("\n=== 救贖弧線(ASCII,貼 README 用)===")
    for predator in ("Cheater", "Prober"):
        key = f"matchup=Sheriff_vs_{predator}|dir=redeem|frac=0.2|churn=0.0|none"
        cell = data["cells"].get(key, {})
        traj = cell.get("representative_trajectory")
        if not traj:
            continue
        good = [pt["good_share"] for pt in traj]
        sheriff = [pt["sheriff_share"] for pt in traj]
        pred = [1 - s for s in sheriff]   # 兩物種:掠食者 = 1 − Sheriff
        valley = min(good)
        v_gen = traj[good.index(valley)]["g"]
        last_gen = traj[-1]["g"]
        print(f"\nSheriff 20% 入侵「{predator}」世界(churn0, 有名聲, {last_gen} 代):")
        print(f"  信任 good_share  {_sparkline(good)}  "
              f"(1.00 → 谷底 {valley:.2f} @ g{v_gen} → {good[-1]:.2f})")
        print(f"  Sheriff 佔比     {_sparkline(sheriff)}  "
              f"({sheriff[0]:.2f} → {sheriff[-1]:.2f})")
        print(f"  {predator}(掠食者) {_sparkline(pred)}  "
              f"({pred[0]:.2f} → {pred[-1]:.2f})")


def main() -> None:
    print("Plotting → results/figures/")
    plot_phase_transition()
    plot_society_profile()
    plot_sweet_spot()
    plot_redemption_arc()
    plot_institution_effect()
    plot_assortment_phase()
    ascii_redemption_arc()
    print("done.")


if __name__ == "__main__":
    main()
