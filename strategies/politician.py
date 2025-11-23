from base_strategy import BaseStrategy
from definitions import Action, Reputation


class Politician(BaseStrategy):
    @property
    def name(self) -> str:
        return "Politician"

    @property
    def color(self) -> tuple:
        # 紫色 (代表權力、有時帶點邪惡)
        return (128, 0, 128)

    def decide(self, opponent: BaseStrategy) -> Action:
        # 1. 永遠幫自己人 (基本的政治結盟)
        if type(self) is type(opponent):
            return Action.NOTIFY

        # --- 核心邏輯：根據「我的民調 (Reputation)」決定嘴臉 ---

        # 2. 【競選期】還沒變成傳奇 (LEGEND) 之前
        # 我需要刷分！我要表現得像個大善人，這樣 Meritocrat 才會接納我。
        if self.reputation < Reputation.LEGEND:
            # 我要找誰刷分？
            # 找那些看起來像好人的人
            # 這樣做有兩個好處：
            # a. 救外人可以 +1 分 (刷分)。
            # b. 對方是好人，所以對方很可能也會救我 (安全)。
            if opponent.reputation >= Reputation.GOOD:
                return Action.NOTIFY

            # 如果對方名聲很臭 (Xenophobe/Cheater)，我不救，避免浪費性命
            return Action.RUN

        # 3. 【收割期】如果我的聲譽已經很高了
        # 我現在是「德高望重」的長老，Meritocrat 會自動救我 (因為他們看我分數高)。
        # 所以我可以開始自私了！為了保命，我選擇逃跑。
        else:
            return Action.RUN
