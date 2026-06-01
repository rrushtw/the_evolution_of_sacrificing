# Phase 2 結果:private↔public 互惠的相圖

> 在一個沒有親緣、死亡罕見(代之以資本/影響力差距)的世界裡,維繫「犧牲」的善良
> 究竟靠 **private history(直接互惠)** 還是 **public reputation(間接互惠)**?
> 答案取決於社會有多流動 —— 而且有一道銳利的相變。

本目錄是 `experiments/phase_sweep.py` 的正式輸出快照(reboot-safe、納入版控)。

## 怎麼重現

```bash
docker compose run --rm \
  -e REPS=30 -e BATCH_GENERATIONS=300 \
  -e CHURN_GRID=0.0,0.1,0.3,0.6,1.0 \
  -e RANDOM_SEED=12345 -e JOBS=22 \
  simulator python -u experiments/phase_sweep.py
```

- **n=30** replicates/cell、**95% CI**、`RANDOM_SEED=12345`(replicate *i* 用 seed `12345+i`,可重現)。
- `CHURN_RATE` = 村莊↔都會旋鈕:0 = 固定圈子(常重逢)、→1 = 不斷重組(盡是陌生人)。
- knockout:`none` / `−reputation`(隱藏公共名聲+公開行為紀錄)/ `−private`(不記逐對手記憶)。
- 合作指標 = 「聲望型善良策略」的族群佔比(`nice%`)。

## 統一框架

合作演化三大機制同一道門檻 **`機制強度 > c/b`**,折扣因子:`r`(結伴)、`w`(再相遇/private)、
`q`(名聲/public)。奇異點 `r* = c/((1−s)b) ≈ 0.21`(= Hamilton 法則,把基因換成名聲)。

---

## 相圖 1 — 14 策略 baseline

`nice%`(mean ± 95% CI, n=30)。原始輸出:[`raw/sweep_14strategies.txt`](raw/sweep_14strategies.txt)、
資料:[`sweep_14strategies.json`](sweep_14strategies.json)。

| churn | 再相遇率 | none | −reputation | −private |
| :--: | :--: | :--: | :--: | :--: |
| 0.0 村莊 | 65% | 79%±12% | 78%±10% | 72%±11% |
| 0.1 | 30% | 74%±13% | 71%±11% | 68%±12% |
| 0.3 | 6% | 57%±16% | **2%±3%** | 42%±16% |
| 0.6 | 7% | 54%±16% | **7%±9%** | 45%±16% |
| 1.0 都會 | 7% | 59%±15% | **9%±10%** | 54%±17% |

**結論**:相變落在 churn 0.1→0.3 之間(再相遇率 30%→6%)。
- **村莊**(低 churn):關掉名聲或私人記憶,合作幾乎不掉 —— 穩定的人際網結構(固定圈子 +
  剝削就斷裂)本身就撐住合作。
- **都會**(高 churn):**公共名聲是唯一命脈** —— 關掉它,合作崩到 2–9%(CI 極窄);
  關掉私人記憶只小掉,因為你幾乎不重逢,private 記憶沒有對象可用。

→ **社會越流動,維繫合作的機制就從「結構/直接互惠」交棒給「名聲/間接互惠」。**

---

## 相圖 2 — 16 策略(加入 Clannish + Whitewasher)

新增兩個直擊 Phase 2 機制的策略:
- **Clannish(排外者)**:NOTIFY 給有私人交情者、RUN 給陌生人 → 村莊好鄰居 / 都會掠食者。
- **Whitewasher(洗白者)**:自己 GOOD 就 RUN 套現、變 BAD 就 NOTIFY 洗白 → 攻擊名聲管道本身。

`nice%`(mean ± 95% CI, n=30)。原始:[`raw/sweep_16strategies.txt`](raw/sweep_16strategies.txt)、
資料:[`sweep_16strategies.json`](sweep_16strategies.json)。

| churn | none | −reputation | −private | none 對比 14 策略 |
| :--: | :--: | :--: | :--: | :--: |
| 0.0 村莊 | 80%±10% | 80%±10% | 67%±11% | 持平 |
| 0.1 | 76%±10% | 72%±12% | 66%±13% | 持平 |
| 0.3 | 54%±15% | **1%±1%** | 46%±16% | 略降 |
| **0.6 北漂** | **31%±13%** | **1%±1%** | 49%±15% | **54%→31% 腰斬** |
| 1.0 都會 | 53%±15% | **0%±0%** | 43%±15% | 略降 |

剝削/回合(none):churn 0.6 由 14 策略的 **9.3 暴增到 22.9**。

**三個發現,兩個假設皆證實且更強**:

1. **Whitewasher 讓名聲更不可或缺。** 加入洗白者後,關掉名聲的都會合作從 ~9% **歸零(0%±0%)**。
   一個 gaming 名聲的掠食者,反而讓社會**更依賴**名聲系統 —— 防線一旦失守,合作蕩然無存。
   (對應現實:假訊息/洗評價時代,對「可信名聲」的依賴不減反增。)

2. **Clannish 把「北漂」中間態打成重災區。** churn 0.6 的合作 **54%→31%(腰斬)**、剝削率 **9→23**。
   **最慘的不是純都會,而是半流動的過渡帶** —— 流動性夠高讓掠食者一直找到新肥羊並逃逸,
   結構又還沒散到大家互不信任。呼應「北漂」直覺:**半流動社會最易被剝削。**

3. **村莊穩如泰山。** churn 0–0.1 幾乎不變 —— Clannish 在固定圈子裡乖乖當好鄰居,
   Whitewasher 也玩不太動。

---

## 注意

- 無 random seed 時 run-to-run 變異大(模型特性);本實驗以固定 base seed + n=30 取得統計顯著性。
- `nice%` 是「策略型別佔比」而非總福利;welfare(capital_mean)全程平穩 ~2.6,敏感指標是組成。
