import random
import pkgutil
import importlib
import inspect
from typing import List, Optional, Dict, Type
from collections import Counter

# 引入定義
from definitions import GameConfig, Action
from base_strategy import BaseStrategy


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
        self.available_strategy_types = self._load_all_strategies()

    def _load_all_strategies(self) -> List[Type[BaseStrategy]]:
        """
        自動掃描 strategies 資料夾，載入所有繼承自 BaseStrategy 的類別
        """
        strategies = []
        package_name = "strategies"

        # 1. 取得 strategies 套件的資訊
        # 確保您的 strategies 資料夾內有 __init__.py (即使是空的)
        package = importlib.import_module(package_name)

        # 2. 遍歷該資料夾下的所有模組 (.py 檔)
        prefix = package.__name__ + "."
        for _, name, _ in pkgutil.iter_modules(package.__path__, prefix):
            try:
                module = importlib.import_module(name)

                # 3. 檢查模組內的所有成員
                for member_name, obj in inspect.getmembers(module):
                    # 篩選條件：
                    # a. 是個 Class
                    # b. 繼承自 BaseStrategy
                    # c. 不是 BaseStrategy 自己
                    if (inspect.isclass(obj) and
                        issubclass(obj, BaseStrategy) and
                            obj is not BaseStrategy):

                        # 避免重複加入 (有些策略可能會被 import 到其他檔案)
                        if obj not in strategies:
                            strategies.append(obj)
                            # print(f"Loaded strategy: {obj().name}") # Debug 用
            except Exception as e:
                print(f"⚠️ Warning: Failed to load module {name}: {e}")

        return strategies

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

        # --- Phase 3: 感化 (Cultural Transmission) ---
        # 這模擬了「觀念傳播」。我不死，但我改變想法。
        self._handle_cultural_transmission()

        # --- Phase 4: 遷徙 (Migration) ---
        # 這模擬了「人口流動」。
        self._handle_migration()

    def _interact_and_check_survival(self, me: BaseStrategy, neighbor: BaseStrategy) -> bool:
        """
        單次互動邏輯：決定 'me' 是否存活。
        包含：角色判定 -> 決策(傳入實例) -> 履歷更新 -> 生死判定
        """
        # 1. 判定角色：我有沒有發現危險？
        i_spotted_danger = random.random() < GameConfig.PROB_SPOT_DANGER

        if i_spotted_danger:
            return self._handle_spotter_scenario(me, neighbor)
        else:
            return self._handle_listener_scenario(me, neighbor)

    def _handle_spotter_scenario(self, me: BaseStrategy, neighbor: BaseStrategy) -> bool:
        """
        情境 A: 我發現了危險 (I am the Spotter)
        """
        # [關鍵修改 1] 傳入 neighbor【實例】，讓我可以查他的信譽/履歷
        my_action = me.decide(neighbor)

        # [關鍵修改 2] 更新我的履歷 (這會影響我的信譽分數)
        me.update_history(my_action, neighbor)

        if my_action == Action.NOTIFY:
            # 選擇犧牲
            return random.random() < GameConfig.SURVIVAL_SPOTTER_NOTIFY
        else:
            # 選擇逃跑
            return random.random() < GameConfig.SURVIVAL_SPOTTER_RUN

    def _handle_listener_scenario(self, me: BaseStrategy, neighbor: BaseStrategy) -> bool:
        """
        情境 B: 我沒發現危險 (I am the Listener)
        """
        # 1. 鄰居發現了嗎？
        neighbor_spotted = random.random() < GameConfig.PROB_SPOT_DANGER
        if not neighbor_spotted:
            # 雙盲 -> 聽天由命
            return random.random() < GameConfig.SURVIVAL_LISTENER_IGNORANT

        # 2. 鄰居決定怎麼做？
        neighbor_action = neighbor.decide(me)

        # 更新鄰居的履歷
        # 注意：即使他是不小心發出聲音救了我，他的【意圖】依然是 RUN，所以履歷照樣記 RUN (扣分)
        neighbor.update_history(neighbor_action, me)

        if neighbor_action == Action.RUN:
            # [新增雙向雜訊機制]
            # 鄰居選擇逃跑。理論上他想偷偷溜走...
            # 但環境雜訊(或他太笨拙)可能會導致他發出聲音被我發現

            accidental_alert = random.random() < self.noise_rate

            if accidental_alert:
                # 幸運！我看到他慌張逃跑，我也跟著逃 -> 視為被警告
                return random.random() < GameConfig.SURVIVAL_LISTENER_WARNED
            else:
                # 他跑得很安靜，我完全不知情 -> 聽天由命
                return random.random() < GameConfig.SURVIVAL_LISTENER_IGNORANT

        # 3. 鄰居通知，檢查雜訊
        else:  # neighbor_action == Action.NOTIFY
            message_lost = random.random() < self.noise_rate

            if message_lost:
                # 悲劇：鄰居喊了，環境太吵我沒聽到 -> 聽天由命
                return random.random() < GameConfig.SURVIVAL_LISTENER_IGNORANT
            else:
                # 成功接收訊號 -> 視為被警告
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

    # ======================================================
    # 新增的邏輯方法
    # ======================================================

    def _handle_cultural_transmission(self):
        """
        感化機制：
        遍歷所有活著的個體，檢查周圍鄰居。
        如果鄰居的聲譽 (Reputation) 顯著高於自己，
        自己有機會「拜師學藝」，轉變成鄰居的策略。
        """
        # 建立一個 copy 避免在遍歷時修改 grid 造成混亂
        # 但我們要改的是物件內部的狀態，或者直接替換物件
        # 為了簡單起見，我們記錄要變更的座標
        conversions = []

        for r in range(self.size):
            for c in range(self.size):
                me = self.grid[r][c]
                if me is None:
                    continue

                # 找鄰居
                neighbors_coords = self.get_neighbors(r, c)
                living_neighbors = [
                    self.grid[nr][nc] for nr, nc in neighbors_coords
                    if self.grid[nr][nc] is not None
                ]

                if not living_neighbors:
                    continue

                # 隨機挑一個鄰居來比較 (或者找最強的)
                target = random.choice(living_neighbors)

                if (random.random() < GameConfig.CONVERSION_RATE):
                    # 記錄這筆感化：(座標, 新策略類別)
                    conversions.append((r, c, type(target)))

        # 應用感化
        for r, c, new_strategy_class in conversions:
            old_agent = self.grid[r][c]
            # 建立新策略實例
            new_agent = new_strategy_class()
            # [重要] 是否要繼承舊的記憶/聲譽？
            # 通常「改過自新」代表聲譽重置，或者是繼承部分？
            # 這裡我們先設定為：重新做人 (Reputation 重置, 但繼承 Last Action 以防作弊)
            new_agent.last_action = old_agent.last_action
            # new_agent.reputation = 0 # 新身分從 0 開始

            self.grid[r][c] = new_agent

    def _handle_migration(self):
        """
        遷徙機制：
        活著的個體有機會移動到鄰近的「空格」。
        這模擬了難民、移民、尋找資源。
        """
        # 為了公平，隨機決定移動順序
        all_coords = [(r, c) for r in range(self.size)
                      for c in range(self.size)]
        random.shuffle(all_coords)

        for r, c in all_coords:
            agent = self.grid[r][c]
            if agent is None:
                continue

            # 擲骰子決定是否想搬家
            if random.random() < GameConfig.MIGRATION_RATE:
                # 找周圍的空格
                neighbors_coords = self.get_neighbors(r, c)
                empty_spots = [
                    (nr, nc) for nr, nc in neighbors_coords
                    if self.grid[nr][nc] is None
                ]

                if empty_spots:
                    # 隨機選一個空位搬過去
                    target_r, target_c = random.choice(empty_spots)

                    # 移動！
                    self.grid[target_r][target_c] = agent
                    self.grid[r][c] = None
