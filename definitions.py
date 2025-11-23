import os
from enum import Enum, IntEnum


class Reputation(IntEnum):
    """
    使用 IntEnum 讓我們可以直接比較大小 (例如 LEGEND > GOOD)
    範圍縮小至 -2 ~ 3，讓背叛代價更顯著。
    """
    LEGEND = 3       # 傳說 (Prophet 門檻)
    TRUSTED = 2      # 信賴 (Meritocrat/Pragmatist 門檻)
    GOOD = 1         # 良民 (願意做一點好事的)
    NEUTRAL = 0      # 普通/排外者 (Xenophobe 預設)
    SUSPICIOUS = -1  # 可疑 (背叛過一次)
    EVIL = -2        # 惡棍 (Cheater 預設)


class Action(Enum):
    """
    行動列舉
    """
    NOTIFY = "Notify"
    RUN = "Run"


class GameConfig:
    """
    統一管理所有參數。
    優先讀取環境變數，若無則使用預設值。
    """

    # --- 基礎模擬設定 ---
    GRID_SIZE = int(os.getenv("GRID_SIZE", "60"))
    NOISE_RATE = float(os.getenv("NOISE_RATE", "0.01"))  # 注意：統一命名為 NOISE_RATE
    MAX_ROUNDS = int(os.getenv("MAX_ROUNDS", "3000"))
    INITIAL_COPIES = int(os.getenv("INITIAL_COPIES", "150"))

    # --- 穩態判定 ---
    STABILITY_WINDOW = int(os.getenv("STABILITY_WINDOW", "100"))
    STABILITY_TOLERANCE = int(os.getenv("STABILITY_TOLERANCE", "5"))

    # --- 生存機率參數 ---
    PROB_SPOT_DANGER = float(os.getenv("PROB_SPOT_DANGER", "0.5"))
    SURVIVAL_SPOTTER_NOTIFY = float(
        os.getenv("SURVIVAL_SPOTTER_NOTIFY", "0.9"))
    SURVIVAL_SPOTTER_RUN = float(os.getenv("SURVIVAL_SPOTTER_RUN", "1.0"))
    SURVIVAL_LISTENER_WARNED = float(
        os.getenv("SURVIVAL_LISTENER_WARNED", "1.0"))
    SURVIVAL_LISTENER_IGNORANT = float(
        os.getenv("SURVIVAL_LISTENER_IGNORANT", "0.05"))

    # --- 社會演化參數 ---
    # 遷徙率
    MIGRATION_RATE = float(os.getenv("MIGRATION_RATE", "0.10"))

    # 感化機制
    CONVERSION_RATE = float(os.getenv("CONVERSION_RATE", "0.05"))
    # 配合新的聲譽範圍 (-2~3)，門檻建議設為 2 (例如 0 變成 2)
    CONVERSION_REPUTATION_DIFF = int(
        os.getenv("CONVERSION_REPUTATION_DIFF", "2"))

    # 聲譽邊界 (用於 BaseStrategy 的 clamp)
    MAX_REPUTATION = Reputation.LEGEND  # 對應 Reputation.LEGEND
    MIN_REPUTATION = Reputation.EVIL  # 對應 Reputation.EVIL
