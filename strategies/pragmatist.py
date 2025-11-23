from base_strategy import BaseStrategy
from definitions import Action


class Pragmatist(BaseStrategy):
    @property
    def name(self) -> str:
        return "Pragmatist"

    @property
    def color(self) -> tuple:
        # 藍綠色 / 鴨翅綠 (Teal)
        # 代表理性、平衡、接地氣
        return (0, 128, 128)

    def decide(self, opponent: BaseStrategy) -> Action:
        # 1. 族群團結
        if type(self) is type(opponent):
            return Action.NOTIFY

        # 2. 基礎互動：以牙還牙 (Tit-for-Tat)
        # 只要你釋出善意，我也一定回報，不管你聲譽多少
        # (這讓即使是聲譽歸零的政客，只要肯改過自新，也能獲得幫助)
        if opponent.last_action == Action.NOTIFY:
            return Action.NOTIFY

        # 3. 寬恕機制：針對「略有瑕疵」的判斷
        # 對方上一輪是 RUN (可能是雜訊，也可能是偶爾自私)

        # Prophet 要求 Rep >= 3 (聖人)
        # Meritocrat 直接拒絕 (零容忍)
        # Pragmatist 只要 Rep >= 1 (證明你總體來說是個好人)
        if opponent.reputation >= 1:
            return Action.NOTIFY

        # 4. 對於平庸 (Rep=0, Xenophobe) 或 邪惡 (Rep<0, Cheater)
        # 拒絕浪費資源
        return Action.RUN
