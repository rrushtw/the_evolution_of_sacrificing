import os
from enum import Enum


class Reputation(Enum):
    """
    Binary Standing Reputation (Sugden 1986).

    GOOD: presumed cooperative; refusing to help me is now bad.
    BAD : presumed defector; refusing to help me is justified.

    New agents start as GOOD (presumption of innocence).
    """
    GOOD = "Good"
    BAD = "Bad"


class Action(Enum):
    """
    Spotter's choice when danger is detected.
    """
    NOTIFY = "Notify"
    RUN = "Run"


class GameConfig:
    """
    All tunables in one place. ENV vars override defaults.
    """

    # --- Noise ---
    # External noise: signal lost / accidentally tipped off
    NOISE_RATE = float(os.getenv("NOISE_RATE", "0.01"))
    # Internal noise: slip of tongue / fumble; the engine still treats
    # the slipped action as the agent's "intent" for reputation purposes.
    INTERNAL_NOISE_RATE = float(os.getenv("INTERNAL_NOISE_RATE", "0.02"))

    # --- Alarm Call mechanics ---
    PROB_SPOT_DANGER = float(os.getenv("PROB_SPOT_DANGER", "0.5"))

    # --- Society presets (A1: c/b 社會旋鈕) ---
    # 「不同社會」的本質就是門檻 c/b 不同 (c = NOTIFY 的發聲成本, b = 被警告的
    # 好處)。每個 preset 只覆寫四個 SURVIVAL_* 的「預設值」, s = PROB_SPOT_DANGER
    # 固定, 讓奇異點 r* = c/((1−s)b) 在同一條 churn 軸上平移。個別 SURVIVAL_* ENV
    # 仍可再覆寫 preset。各 preset 只列出與 default 不同的鍵。
    #   default     : c=0.10 b=0.95 → r*≈0.21 (現狀基準)
    #   cheap_voice : NOTIFY 0.9→0.97 (c↓) → c=0.03 r*≈0.06  低成本發聲
    #   safety_net  : IGNORANT 0.05→0.55 (b↓) → b=0.45 r*≈0.42  現代安全網
    #   ancient     : NOTIFY 0.9→0.75 (c↑) → c=0.25 r*≈0.53  殘酷古代
    SOCIETY_PRESETS = {
        "default": {},
        "cheap_voice": {"spotter_notify": 0.97},
        "safety_net": {"listener_ignorant": 0.55},
        "ancient": {"spotter_notify": 0.75},
    }
    # 四個 SURVIVAL_* 的出廠預設 (= default preset)。
    _SURVIVAL_DEFAULTS = {
        "spotter_notify": 0.9,
        "spotter_run": 1.0,
        "listener_warned": 1.0,
        "listener_ignorant": 0.05,
    }
    SOCIETY_PRESET = os.getenv("SOCIETY_PRESET", "default")
    _preset = {**_SURVIVAL_DEFAULTS, **SOCIETY_PRESETS.get(SOCIETY_PRESET, {})}

    SURVIVAL_SPOTTER_NOTIFY = float(
        os.getenv("SURVIVAL_SPOTTER_NOTIFY", _preset["spotter_notify"]))
    SURVIVAL_SPOTTER_RUN = float(
        os.getenv("SURVIVAL_SPOTTER_RUN", _preset["spotter_run"]))
    SURVIVAL_LISTENER_WARNED = float(
        os.getenv("SURVIVAL_LISTENER_WARNED", _preset["listener_warned"]))
    SURVIVAL_LISTENER_IGNORANT = float(
        os.getenv("SURVIVAL_LISTENER_IGNORANT", _preset["listener_ignorant"]))

    @classmethod
    def society_params(cls):
        """門檻框架的衍生量, 由當前四個 SURVIVAL_* 即時算出 (單一真相來源)。

        c = 發聲成本 (RUN − NOTIFY), b = 被警告的好處 (WARNED − IGNORANT),
        s = P(發現危險), 奇異點 r* = c/((1−s)b) —— 維繫合作所需的最低機制強度。
        """
        s = cls.PROB_SPOT_DANGER
        c = cls.SURVIVAL_SPOTTER_RUN - cls.SURVIVAL_SPOTTER_NOTIFY
        b = cls.SURVIVAL_LISTENER_WARNED - cls.SURVIVAL_LISTENER_IGNORANT
        denom = (1.0 - s) * b
        r_star = c / denom if denom else float("inf")
        return {"preset": cls.SOCIETY_PRESET, "s": s,
                "c": round(c, 4), "b": round(b, 4), "r_star": round(r_star, 4)}

    # --- Evolution (capital + overlapping generations) ---
    # Death is no longer binary: outcomes become capital gains/losses. Agents
    # are long-lived, age, and only die of old age or bankruptcy; each death is
    # replaced by an offspring of a capital-weighted parent (population stays N).
    INITIAL_COPIES = int(os.getenv("INITIAL_COPIES", "10"))
    # Each round runs ENCOUNTERS_PER_AGENT × N // 2 interactions, then everyone
    # recovers + ages, then mortality is rolled.
    ENCOUNTERS_PER_AGENT = int(os.getenv("ENCOUNTERS_PER_AGENT", "2"))
    # Capital each agent starts (and recovers toward). Outcomes are applied as
    # delta = (payoff − 1): a missed warning (IGNORANT) is a −0.95 hit, NOTIFY a
    # −0.1 cost — see _resolve_interaction. Baseline must sit well ABOVE a single
    # hit so a bad encounter HURTS but rarely bankrupts you in one round (that's
    # what makes lives long & capital graded); 5 keeps a strong influence gap.
    CAPITAL_BASELINE = float(os.getenv("CAPITAL_BASELINE", "5.0"))
    # Fraction of the gap to baseline that heals each round. Lower = a loss
    # lingers longer = a longer 'shadow of the future' (reciprocity pays more).
    CAPITAL_RECOVERY = float(os.getenv("CAPITAL_RECOVERY", "0.1"))
    # Mortality per round = BASE_DEATH + AGE_DEATH × age (clamped to 1), plus
    # instant death on bankruptcy (capital ≤ 0). Tuned for long-but-finite lives.
    BASE_DEATH = float(os.getenv("BASE_DEATH", "0.002"))
    AGE_DEATH = float(os.getenv("AGE_DEATH", "0.0010"))
    # ASSORTMENT: when an agent forms a NEW tie, P(it prefers a same-Standing
    # partner). 0 = unbiased rewiring; 1 = GOOD only befriends GOOD.
    ASSORTMENT = float(os.getenv("ASSORTMENT", "0.0"))
    MAX_GENERATIONS = int(os.getenv("MAX_GENERATIONS", "3000"))

    # --- Social network (Stage B) ---
    # Agents sit on a graph and interact with their contacts → repeated
    # encounters → private history. AVG_DEGREE = how many contacts each holds.
    AVG_DEGREE = int(os.getenv("AVG_DEGREE", "6"))
    # CHURN_RATE = per-round probability each tie reshuffles. The village↔metropolis
    # dial: 0 = a fixed village (you keep contacts for life → private history rules);
    # →1 = a churning metropolis (you rarely re-meet → reputation rules). Independent
    # of this, EXPLOITATION (running on a GOOD partner) always breaks that tie and
    # the exploiter flees to a new circle — so a hit-and-run escapes private revenge.
    CHURN_RATE = float(os.getenv("CHURN_RATE", "0.05"))

    # --- Knockout flags (for private-vs-public causal experiments) ---
    # BLIND_REPUTATION: deciders always see opponents as GOOD (reputation ablated).
    BLIND_REPUTATION = os.getenv("BLIND_REPUTATION", "0") == "1"
    # BLIND_PRIVATE: per-opponent memory is never recorded (private history ablated).
    BLIND_PRIVATE = os.getenv("BLIND_PRIVATE", "0") == "1"

    # --- Third-party institutional punishment (Nowak 第五法則) ---
    # 自發機制(結伴 r / 私記憶 w / 名聲 q)之外的第四條:由「系統」主動執法。每 round
    # 把被判 BAD 的人以 INSTITUTION_STRENGTH 的機率直接淘汰(法律/平台封號/信用黑名單),
    # 不必等受害者自己報復 —— 名聲從「警告下一個受害者」升級成「直接執法」。
    # 0 = 無制度,完全向後相容(等同現狀)。淘汰走既有 mortality → on_death → repopulate。
    INSTITUTION_STRENGTH = float(os.getenv("INSTITUTION_STRENGTH", "0.0"))
    # 誤判率:每 round 把 GOOD 冤枉淘汰的機率(0 = 完美執法)。掃這條看制度何時反噬合作。
    INSTITUTION_FALSE_POSITIVE = float(os.getenv("INSTITUTION_FALSE_POSITIVE", "0.0"))

    # --- Reproducibility ---
    # RANDOM_SEED: if set, main() seeds the global RNG once for a reproducible
    # single run. Unset (default) = fresh randomness each run. (The batch
    # experiment seeds per-replicate itself; see experiments/phase_sweep.py.)
    RANDOM_SEED = int(os.getenv("RANDOM_SEED")) if os.getenv("RANDOM_SEED") else None

    # --- Stability ---
    # Stable = every species' count has fluctuated by ≤ TOLERANCE for the
    # last THRESHOLD generations. (Species-set-only stability is too lax —
    # counts can still swing wildly while the set is unchanged.)
    STABILITY_THRESHOLD = int(os.getenv("STABILITY_THRESHOLD", "100"))
    STABILITY_TOLERANCE = int(os.getenv("STABILITY_TOLERANCE", "5"))
