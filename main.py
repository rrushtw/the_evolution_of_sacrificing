import os
import json
import time
from datetime import datetime
from collections import deque
from typing import List

from simulation import Simulation

# ==========================================
# 1. 讀取設定 (Configuration)
# ==========================================
NOISE_RATE = float(os.getenv("NOISE", "0.05"))
GRID_SIZE = int(os.getenv("GRID_SIZE", "60"))
INITIAL_COPIES = int(os.getenv("INITIAL_COPIES_PER_TYPE", "20"))
MAX_ROUNDS = int(os.getenv("ROUNDS_PER_GAME", "1000"))
STABILITY_WINDOW = int(os.getenv("STABILITY_WINDOW", "30"))
STABILITY_TOLERANCE = int(os.getenv("STABILITY_TOLERANCE", "5"))

OUTPUT_DIR = "./output"

# ==========================================
# 2. 視覺化與排名輔助函式
# ==========================================


def render_grid(sim: Simulation):
    """在 Terminal 印出 True Color 彩色網格"""
    RESET = "\033[0m"
    EMPTY_COLOR = "\033[90m"
    symbol = "██"
    empty_symbol = "··"

    output = []
    output.append("┌" + "──" * sim.size + "┐")
    for row in sim.grid:
        line = ["│"]
        for agent in row:
            if agent is None:
                line.append(f"{EMPTY_COLOR}{empty_symbol}{RESET}")
            else:
                r, g, b = agent.color
                color_code = f"\033[38;2;{r};{g};{b}m"
                line.append(f"{color_code}{symbol}{RESET}")
        line.append("│")
        output.append("".join(line))
    output.append("└" + "──" * sim.size + "┘")
    print("\n".join(output))


def get_ranked_list(current_counts: dict, extinction_log: dict, all_names: list) -> List[dict]:
    """
    計算並回傳排序後的排名列表 (資料結構)。
    排序邏輯：
    1. 存活者 (Alive) > 已滅絕者 (Dead)
    2. 存活者比數量 (Count)
    3. 已滅絕者比滅絕代數 (Died At Generation)
    """
    ranking_data = []

    for name in all_names:
        count = current_counts.get(name, 0)
        if count > 0:
            # 存活者: alive=True, score=數量
            ranking_data.append({
                "name": name,
                "alive": True,
                "score": count,
                "display": f"{count}"
            })
        else:
            # 已滅絕: alive=False, score=滅絕代數
            died_at = extinction_log.get(name, 0)
            ranking_data.append({
                "name": name,
                "alive": False,
                "score": died_at,
                "display": f"💀(Gen {died_at})"
            })

    # 排序: 先比 alive (True > False), 再比 score (大 > 小)
    ranking_data.sort(key=lambda x: (x["alive"], x["score"]), reverse=True)
    return ranking_data


def format_leaderboard(ranked_list: List[dict]) -> str:
    """將排名列表轉換為可讀字串"""
    parts = []
    for i, item in enumerate(ranked_list, 1):
        medal = ""
        if i == 1:
            medal = "🥇 "
        elif i == 2:
            medal = "🥈 "
        elif i == 3:
            medal = "🥉 "

        parts.append(f"{medal}{item['name']}: {item['display']}")

    return " | ".join(parts)


def check_stability(history: deque, tolerance: int) -> bool:
    """檢查歷史紀錄中的波動是否小於容許值"""
    if len(history) < history.maxlen:
        return False
    all_species = set()
    for record in history:
        all_species.update(record.keys())
    is_stable = True
    for species in all_species:
        counts = [record.get(species, 0) for record in history]
        if not counts:
            continue
        if (max(counts) - min(counts)) > tolerance:
            is_stable = False
            break
    return is_stable

# ==========================================
# 3. 主程式
# ==========================================


def main():
    print("🚀 Starting Simulation...")
    print(
        f"📋 Config: Grid={GRID_SIZE}x{GRID_SIZE}, Noise={NOISE_RATE}, MaxRounds={MAX_ROUNDS}")

    sim = Simulation(grid_size=GRID_SIZE, noise_rate=NOISE_RATE)

    # 設定初始人口 (確保這裡有包含所有你想測試的策略)
    # 只要你在 simulation.py 裡有 import 並加入 available_strategy_types，這裡就可以用
    initial_population = {
        "Altruist": INITIAL_COPIES,
        "Cheater": INITIAL_COPIES,
        "Selective": INITIAL_COPIES,
        "Grudger": INITIAL_COPIES,
        "Imposter": INITIAL_COPIES
    }
    sim.populate(initial_population)

    all_strategy_names = list(initial_population.keys())
    extinction_log = {}  # 紀錄滅絕時間點

    print(f"👥 Initial Population: {initial_population}")
    render_grid(sim)
    print("-" * 40)

    history_for_json = []
    stability_window = deque(maxlen=STABILITY_WINDOW)

    start_time = time.time()

    # --- 演化迴圈 ---
    final_ranked_list = []  # 用來存最後的結果

    for generation in range(1, MAX_ROUNDS + 1):
        sim.run_generation()
        stats = sim.get_stats()
        current_counts = stats['details']

        # 更新滅絕紀錄
        for name in all_strategy_names:
            if current_counts.get(name, 0) == 0 and name not in extinction_log:
                extinction_log[name] = generation

        # 計算即時排名
        ranked_list = get_ranked_list(
            current_counts, extinction_log, all_strategy_names)
        leaderboard_str = format_leaderboard(ranked_list)

        # 紀錄歷史
        history_for_json.append({
            "generation": generation,
            "stats": stats,
            "ranking": [item['name'] for item in ranked_list]  # 只存名字順序，節省空間
        })
        stability_window.append(current_counts)

        # 顯示
        print(f"\nGen {generation:03d} [Alive: {stats['total_alive']}]")
        print(f"🏆 {leaderboard_str}")
        render_grid(sim)

        # 結束條件 1: 全滅
        if stats['total_alive'] == 0:
            print("\n💀 Everyone is dead. Simulation ended early.")
            final_ranked_list = ranked_list
            break

        # 結束條件 2: 穩態
        if check_stability(stability_window, STABILITY_TOLERANCE):
            print(
                f"\n🛑 Stability Reached! (Counts haven't changed significantly for {STABILITY_WINDOW} rounds)")
            final_ranked_list = ranked_list
            break

        # 如果跑到最後一輪，更新最後排名
        if generation == MAX_ROUNDS:
            final_ranked_list = ranked_list

    duration = time.time() - start_time

    # 格式化最終排名顯示
    final_leaderboard_str = format_leaderboard(final_ranked_list)

    print("-" * 40)
    print(f"🏁 Simulation Complete in {duration:.2f}s")
    print(f"👑 Final Ranking: {final_leaderboard_str}")

    # --- 儲存結果 ---
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{OUTPUT_DIR}/sim_result_{timestamp}.json"

    try:
        with open(filename, "w", encoding='utf-8') as f:
            json.dump({
                "meta": {
                    "timestamp": timestamp,
                    "duration_seconds": duration
                },
                "config": {
                    "grid_size": GRID_SIZE,
                    "noise_rate": NOISE_RATE,
                    "max_rounds": MAX_ROUNDS,
                    "initial_population": initial_population
                },
                "final_summary": {
                    "ranking_str": final_leaderboard_str,
                    "ranking_details": final_ranked_list,  # 包含詳細分數與狀態
                    "extinction_log": extinction_log
                },
                "history": history_for_json
            }, f, indent=2)
        print(f"✅ Results saved to: {filename}")
    except Exception as e:
        print(f"❌ Failed to save results: {e}")


if __name__ == "__main__":
    main()
