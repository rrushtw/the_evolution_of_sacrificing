from enum import Enum

# ==========================================
# 1. 遊戲物理法則 (Game Physics / Configuration)
# ==========================================


class GameConfig:
    """
    定義遊戲中的存活機率參數。
    """
    # --- [新增] 環境參數 ---
    # 每個個體在危險來臨時，自己能察覺到的機率
    # 如果設為 0.5，代表兩人都沒發現的機率是 0.25 (0.5 * 0.5)
    PROB_SPOT_DANGER: float = 0.5

    # --- 觀察者 (Spotter) 的命運 ---
    # 選擇「通知」: 暴露位置，有風險被捕食 (犧牲)
    SURVIVAL_SPOTTER_NOTIFY: float = 0.7
    # 選擇「逃跑」: 默默溜走，安全
    SURVIVAL_SPOTTER_RUN: float = 1.0

    # --- 聆聽者 (Listener) 的命運 ---
    # 若被通知: 成功躲藏
    SURVIVAL_LISTENER_WARNED: float = 1.0
    # 若沒被通知 (且自己也沒發現): 完全不知情，高機率死亡
    # 代表有 5% 的機率僥倖逃過一劫 (Lucky Escape)
    SURVIVAL_LISTENER_IGNORANT: float = 0.05


class Action(Enum):
    NOTIFY = "Notify"  # 發出警報 (合作/犧牲)
    RUN = "Run"  # 獨自逃跑 (背叛/自私)
