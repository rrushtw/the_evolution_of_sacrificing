import os
import json
import time
from datetime import datetime
from collections import deque
from typing import List

from simulation import Simulation
from definitions import GameConfig

# ==========================================
# 1. 視覺化與排名輔助函式 (保持不變)
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


def format_leaderboard(ranked_list: List[dict], color_map: dict[str, tuple] = None) -> str:
    """
    將排名列表轉換為可讀字串，並支援 ANSI True Color 上色。
    Args:
        ranked_list: 排名資料
        color_map: { 'StrategyName': (R, G, B) } 的字典
    """
    parts = []
    RESET = "\033[0m"

    for i, item in enumerate(ranked_list, 1):
        medal = ""
        if i == 1:
            medal = "🥇 "
        elif i == 2:
            medal = "🥈 "
        elif i == 3:
            medal = "🥉 "

        name = item['name']
        display_name = name

        # 如果有提供顏色表，就幫名字上色
        if color_map and name in color_map:
            r, g, b = color_map[name]
            # ANSI True Color: \033[38;2;R;G;Bm
            display_name = f"\033[38;2;{r};{g};{b}m{name}{RESET}"

        parts.append(f"{medal}{display_name}: {item['display']}")

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
# 2. 主程式
# ==========================================

def main():
    print("🚀 Starting Simulation...")
    print(
        f"📋 Config: Grid={GameConfig.GRID_SIZE}x{GameConfig.GRID_SIZE}, "
        f"Noise={GameConfig.NOISE_RATE}, MaxRounds={GameConfig.MAX_ROUNDS}"
    )

    sim = Simulation(
        grid_size=GameConfig.GRID_SIZE,
        noise_rate=GameConfig.NOISE_RATE
    )

    # 設定初始人口
    initial_population = {
        strategy_cls().name: GameConfig.INITIAL_COPIES
        for strategy_cls in sim.available_strategy_types
    }
    sim.populate(initial_population)

    # 建立顏色對照表
    strategy_colors = {
        cls().name: cls().color
        for cls in sim.available_strategy_types
    }

    all_strategy_names = list(initial_population.keys())
    extinction_log = {}  # 紀錄滅絕時間點

    print(f"👥 Initial Population: {initial_population}")
    render_grid(sim)
    print("-" * 40)

    history_for_json = []
    stability_window = deque(maxlen=GameConfig.STABILITY_WINDOW)

    start_time = time.time()

    # --- 演化迴圈 ---
    final_ranked_list = []  # 用來存最後的結果

    for generation in range(1, GameConfig.MAX_ROUNDS + 1):
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
        leaderboard_str = format_leaderboard(ranked_list, strategy_colors)

        # 紀錄歷史
        history_for_json.append({
            "generation": generation,
            "stats": stats,
            "ranking": [item['name'] for item in ranked_list]
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
        if check_stability(stability_window, GameConfig.STABILITY_TOLERANCE):
            print(
                f"\n🛑 Stability Reached! (Counts haven't changed significantly for {GameConfig.STABILITY_WINDOW} rounds)")
            final_ranked_list = ranked_list
            break

        # 如果跑到最後一輪
        if generation == GameConfig.MAX_ROUNDS:
            final_ranked_list = ranked_list

    duration = time.time() - start_time

    # 格式化最終排名顯示
    final_leaderboard_str = format_leaderboard(
        final_ranked_list, strategy_colors)

    print("-" * 40)
    print(f"🏁 Simulation Complete in {duration:.2f}s")
    print(f"👑 Final Ranking:\n{final_leaderboard_str.replace(' | ', '\n')}")

    # --- 儲存結果 ---
    # OUTPUT_DIR 還是可以從 os 讀取，或者您也可以放進 GameConfig，這邊先維持 os.getenv
    OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./output")
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
                    "grid_size": GameConfig.GRID_SIZE,
                    "noise_rate": GameConfig.NOISE_RATE,
                    "max_rounds": GameConfig.MAX_ROUNDS,
                    "migration_rate": GameConfig.MIGRATION_RATE,
                    "conversion_rate": GameConfig.CONVERSION_RATE,
                    "initial_population": initial_population
                },
                "final_summary": {
                    "ranking_str": final_leaderboard_str,
                    "ranking_details": final_ranked_list,
                    "extinction_log": extinction_log
                },
                "history": history_for_json
            }, f, indent=2)
        print(f"✅ Results saved to: {filename}")
    except Exception as e:
        print(f"❌ Failed to save results: {e}")


if __name__ == "__main__":
    main()
