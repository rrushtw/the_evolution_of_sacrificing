import random
from typing import List, Optional, Dict
from collections import Counter

# 引入我們定義好的規則與策略
from definitions import GameConfig, Action
from base_strategy import BaseStrategy

# 為了方便初始化，我們引入具體策略
# (實際專案中也可以用動態載入，但這裡先 Explicit 比較清楚)
from strategies.altruist import Altruist
from strategies.cheater import Cheater
from strategies.selective import Selective
from strategies.grudger import Grudger


class Simulation:
    def __init__(self, grid_size: int = 20, noise_rate: float = 0.05):
        """
        初始化模擬環境

        Args:
            grid_size: 網格邊長 (NxN)
            noise_rate: 判斷錯誤的機率 (0.0 ~ 1.0)
        """
        self.size = grid_size
        self.noise_rate = noise_rate

        # 初始化網格: List[List[Optional[BaseStrategy]]]
        # None 代表該格子是空的 (死掉了或還沒出生)
        self.grid: List[List[Optional[BaseStrategy]]] = [
            [None for _ in range(grid_size)] for _ in range(grid_size)
        ]

        # 可用的策略列表 (用於雜訊時隨機誤判，或繁殖變異)
        self.available_strategy_types = [Altruist, Cheater, Selective, Grudger]

    def populate(self, initial_counts: Dict[str, int]):
        """
        將生物隨機撒在網格上
        Args:
            initial_counts: {'Altruist': 10, 'Cheater': 5 ...}
        """
        # 1. 建立所有要放入的 Agent 實例
        agents_pool = []
        strategy_map = {s().name: s for s in self.available_strategy_types}

        for name, count in initial_counts.items():
            if name in strategy_map:
                strategy_class = strategy_map[name]
                # 建立 count 個實例
                agents_pool.extend([strategy_class() for _ in range(count)])

        # 2. 隨機打亂
        random.shuffle(agents_pool)

        # 3. 填入網格 (如果有剩餘空間則留空，如果格子不夠則截斷)
        idx = 0
        for r in range(self.size):
            for c in range(self.size):
                if idx < len(agents_pool):
                    self.grid[r][c] = agents_pool[idx]
                    idx += 1
                else:
                    self.grid[r][c] = None

    def get_neighbors(self, r: int, c: int) -> List[tuple]:
        """
        取得周圍 8 格鄰居的座標 (Moore Neighborhood)。
        使用 Toroidal (環狀/甜甜圈) 邊界，避免邊緣效應。
        """
        neighbors = []
        for i in [-1, 0, 1]:
            for j in [-1, 0, 1]:
                if i == 0 and j == 0:
                    continue

                # 環狀邊界計算 (Wrap-around)
                nr = (r + i) % self.size
                nc = (c + j) % self.size
                neighbors.append((nr, nc))
        return neighbors

    def run_generation(self):
        """
        執行一輪演化：
        1. 互動 (Interaction): 決定誰死掉
        2. 繁殖 (Reproduction): 倖存者填補空位
        """
        # --- Phase 1: 互動與死亡 ---
        # 我們需要一個標記「誰死了」，而不能直接改 self.grid，
        # 否則會影響同一輪後面的人的互動 (Synchronous update)
        survivors_mask = [[True for _ in range(
            self.size)] for _ in range(self.size)]

        for r in range(self.size):
            for c in range(self.size):
                agent = self.grid[r][c]
                if agent is None:
                    survivors_mask[r][c] = False  # 本來就是死的
                    continue

                # 找鄰居
                neighbors_coords = self.get_neighbors(r, c)
                # 過濾出活著的鄰居
                living_neighbors = [
                    (nr, nc) for nr, nc in neighbors_coords
                    if self.grid[nr][nc] is not None
                ]

                # 如果孤單一人，假設沒有警報遊戲發生 (或者假設必定生存/必定死亡，這裡假設安全)
                if not living_neighbors:
                    continue

                # 隨機挑一個鄰居進行互動
                target_r, target_c = random.choice(living_neighbors)
                neighbor = self.grid[target_r][target_c]

                # 判定生死 (Play the game)
                me_survived = self._interact_and_check_survival(
                    agent, neighbor)

                if not me_survived:
                    survivors_mask[r][c] = False

        # 應用死亡：將死掉的格子設為 None
        for r in range(self.size):
            for c in range(self.size):
                if not survivors_mask[r][c]:
                    self.grid[r][c] = None

        # --- Phase 2: 繁殖 (Reproduction) ---
        # 再次掃描，這次找空格子，讓它被鄰居填滿
        next_grid_state = [row[:] for row in self.grid]  # Copy current state

        for r in range(self.size):
            for c in range(self.size):
                if self.grid[r][c] is None:  # 如果這裡是空地
                    # 找周圍活著的鄰居
                    neighbors_coords = self.get_neighbors(r, c)
                    living_neighbors = [
                        self.grid[nr][nc] for nr, nc in neighbors_coords
                        if self.grid[nr][nc] is not None
                    ]

                    if living_neighbors:
                        # 【繁殖規則】：隨機選一個鄰居的後代填補
                        # 這模擬了生物擴散 (Propagate)
                        parent = random.choice(living_neighbors)
                        # 產生新後代 (複製策略)
                        child = type(parent)()
                        next_grid_state[r][c] = child

        # 更新網格
        self.grid = next_grid_state

    def _interact_and_check_survival(self, me: BaseStrategy, neighbor: BaseStrategy) -> bool:
        """
        單次互動邏輯：決定 'me' 是否存活。

        修正後的邏輯：
        1. 威脅來襲 (Event start)。
        2. 'me' 嘗試察覺危險。
        3. 'neighbor' 嘗試察覺危險。
        4. 如果 'me' 沒察覺，就必須依賴 'neighbor' 的警告。
        5. 加入雜訊：Neighbor 發出警告，但可能被環境音蓋過 (Communication Failure)。
        """

        # --- 步驟 1: 我自己有沒有發現危險？ ---
        i_spotted_danger = random.random() < GameConfig.PROB_SPOT_DANGER

        if i_spotted_danger:
            # === 情境 A: 我發現了危險 ===
            # 我掌握了自己的命運。我決定行動。

            # (這裡暫時移除了身份誤判的雜訊，因為您定義雜訊為溝通失敗)
            # 但 Selective 還是會根據對方是誰來決定要不要救對方
            # 不過，這裡計算的是「我」的存活。

            # 如果我選擇 RUN -> 我存活率 100% (SURVIVAL_SPOTTER_RUN)
            # 如果我選擇 NOTIFY -> 我有死亡風險 (SURVIVAL_SPOTTER_NOTIFY)

            my_action = me.decide(type(neighbor))

            if my_action == Action.NOTIFY:
                # 我選擇犧牲/冒險
                return random.random() < GameConfig.SURVIVAL_SPOTTER_NOTIFY
            else:
                # Action.RUN: 我選擇自保
                return random.random() < GameConfig.SURVIVAL_SPOTTER_RUN

        else:
            # === 情境 B: 我沒發現危險 (I am ignorant) ===
            # 我的命運完全掌握在鄰居手裡

            # 1. 鄰居發現了嗎？
            neighbor_spotted_danger = random.random() < GameConfig.PROB_SPOT_DANGER

            if not neighbor_spotted_danger:
                # 慘況：雙方都沒發現
                # 根據定義，不知情者存活率極低 (通常是 0.0)
                return random.random() < GameConfig.SURVIVAL_LISTENER_IGNORANT

            # 2. 鄰居發現了，他決定怎麼做？
            neighbor_action = neighbor.decide(type(me))

            if neighbor_action == Action.RUN:
                # 鄰居自私逃跑 -> 我不知情 -> 死亡
                return random.random() < GameConfig.SURVIVAL_LISTENER_IGNORANT

            else:
                # 鄰居選擇通知 (Action.NOTIFY)
                # === 關鍵修正：加入溝通雜訊 (Communication Noise) ===
                # 即使鄰居喊了，可能因為下雨我沒聽到

                message_lost = random.random() < self.noise_rate

                if message_lost:
                    # 悲劇：鄰居冒險喊了(他可能死)，但我沒聽到(我也死)
                    return random.random() < GameConfig.SURVIVAL_LISTENER_IGNORANT
                else:
                    # 成功接收訊號 -> 我活下來
                    return random.random() < GameConfig.SURVIVAL_LISTENER_WARNED

    def get_stats(self) -> dict:
        """統計當前各種族的數量"""
        counts = Counter()
        total_alive = 0
        for r in range(self.size):
            for c in range(self.size):
                agent = self.grid[r][c]
                if agent:
                    counts[agent.name] += 1
                    total_alive += 1

        return {
            "total_alive": total_alive,
            "details": dict(counts)
        }
