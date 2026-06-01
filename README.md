# The Evolution of Sacrificing

> An evolutionary simulation of the **Alarm Call Game** asking a single question:
>
> **When agents cannot tell friend from foe, can niceness still win?**

Hamilton's classic kin-selection rule (`rB > C`) explains altruism between
genetic relatives. Strip the kinship away — set `r = 0` — and the puzzle
returns: why would anyone sacrifice for a stranger? Real-world examples
(humans feeding stray dogs, interspecies mutualism, anonymous donors) suggest
the answer involves **reputation** and **memory** rather than shared genes.
This repo is Phase 1 of that investigation.

---

## 🦁 The Alarm Call Game

Each interaction pairs two agents. Both independently roll for spotting
danger (default `50%`). Whoever spots makes a single choice:

| Spotter chooses | Spotter survives | Listener survives |
| :--- | :---: | :---: |
| **NOTIFY** (cry alarm, draws predator) | 90% | 100% (warned) |
| **RUN** (silent escape) | 100% | 5% (ignorant) |

Two layers of noise can flip the picture:

- **Internal noise** (`2%`): a slip — the agent's body fails to do what it
  intended. The world sees the slipped action and judges accordingly.
- **External noise** (`1%`): a `NOTIFY` may be lost in transit, or a `RUN`
  may accidentally tip off the listener.

Survival is a **literal life-or-death roll**, not a score: each interaction,
an agent lives or dies by its survival probability — one unlucky encounter
(an ignored listener survives just `5%`) can end it on the spot. A generation
runs these brutal one-shot encounters until the living pool is culled down to
a **survival floor** (`SURVIVAL_FLOOR_FRAC`, default `50%`). The survivors —
and only the survivors — breed back up to the starting size; each newborn
inherits **one bit** of its parent: its public Standing (a lineage that earned
a bad name passes that stigma on). Repeat until one strategy wins, a single
species remains, or the population settles into a stable mix. Crank
`SURVIVAL_FLOOR_FRAC` down for a crueler world.

---

## 🧠 The 14 Strategies

Three controls + eleven hypothesis-testers. **None** of them can see what
*type* another agent is — they only observe behavior and reputation.

### Controls (the corners of the space)

| Strategy | Behavior |
| :--- | :--- |
| 😇 **Altruist** | Always `NOTIFY`. Pure cooperator baseline. |
| 😈 **Cheater** | Always `RUN`. Pure defector baseline. |
| 🎲 **Chaotic** | 50/50 coin flip. Noise floor. |

### Reputation-driven (use the public Standing label only)

| Strategy | Behavior |
| :--- | :--- |
| ⚖️ **Sheriff** | Pure Standing executor — `NOTIFY` GOOD, `RUN` BAD. |
| 🔮 **Prophet** | Deep forgiver — helps anyone with *any* `NOTIFY` in their public log. |
| 🔨 **Jacobin** | Public Grim Trigger — one `RUN` ever recorded = no help, forever. |

### Private-memory (look up `opponent_history` for this specific opponent)

| Strategy | Behavior |
| :--- | :--- |
| 🪞 **Simpleton** | Private Tit-for-Tat — mirror what this specific opponent did to me last time. |
| 🤝 **Samaritan** | Private TFT + 10% random forgiveness (breaks noise-induced spirals). |
| ⛓️ **Grudger** | Private Grim Trigger — one `RUN` against me ever = no help, forever (the personal counterpart to Jacobin). |
| 🌿 **TitForTwoTats** | Forgiving TFT — only retaliate after *two consecutive* `RUN`s from the same opponent (treats the first as possible noise). |
| 🧠 **Pavlov** | Win-Stay, Lose-Shift — joint outcome with this opponent decides whether to repeat or flip my last action (Nowak & Sigmund 1993, adapted). |

### Public-memory (read the opponent's own public log)

| Strategy | Behavior |
| :--- | :--- |
| 🧭 **Pragmatist** | Public TFT — mirror the opponent's most recent public action. |

### Exploiters

| Strategy | Behavior |
| :--- | :--- |
| 🎩 **Politician** | Sucker hunter — `RUN` against opponents whose public log is dominated by `NOTIFY` (test: can unconditional cooperators be parasitized even under Standing?). |
| 🦊 **Prober** | Probe-and-adapt predator — `RUN` for the first 3 spotter rounds against each opponent; if they retaliate, switch to private TFT, otherwise keep exploiting. |

> Three earlier candidates were removed/skipped on purpose:
> - **Xenophobe**: relied on `isinstance(opponent, Xenophobe)` to recognize
>   kin — DNA cheat, violates the "unknown friend/foe" premise.
> - **Commoner**: required reputation tiers (LEGEND / TRUSTED / SUSPICIOUS …)
>   that don't exist under binary Standing.
> - **Loner**: was meant to be "unconditional `RUN` even toward same-type",
>   but with all `type()` checks removed, same-type detection no longer
>   exists for anyone — Loner is now indistinguishable from Cheater.

---

## 🧬 Reputation: Binary Standing (Sugden 1986)

Reputation is a single bit per agent, visible to everyone:

```
1. NOTIFY                 → GOOD (unconditional)
2. RUN against GOOD       → BAD
3. RUN against BAD        → unchanged   (justified defection)
4. New-born agent         → GOOD        (presumption of innocence)
```

That's all four rules. Refusing to help a known cheat is *not* a moral
failing — this is the key difference from naïve "first-order" image scoring
where every defection is equally bad regardless of the target.

---

## 🧠 Memory: Two Layers Per Agent

| Layer | Visibility | Purpose |
| :--- | :--- | :--- |
| `reputation` | Public, global | Standing — current GOOD/BAD label |
| `my_history` | Public, append-only | Every observable action this agent has taken |
| `opponent_history[id]` | Private to this agent | What each specific opponent has done **to me** |

The `decide()` API exposes the **opponent's public** layers plus their
`unique_id`. Strategies that want private grudge tracking look up their own
`opponent_history` against that id. The opponent **instance** is never
passed — by construction, strategies cannot read each other's class.

---

## 🚀 Quick Start

```bash
cp .env.example .env        # tweak parameters if you like
docker compose build        # first time only — installs tqdm into the image
```

### Interactive run (recommended — live progress bar)

```bash
docker compose run --rm simulator
```

A single tqdm bar anchors the bottom of the terminal, updating in place
with the current top 3 strategies, BAD-reputation %, and stability window
fill. Extinction events scroll cleanly above it. Final ranking prints on
completion.

> ⚠️ Use `compose run --rm`, **not** `compose up`. `compose up` pipes
> output through a log multiplexer that buffers on `\n`, so tqdm's
> in-place `\r` updates are swallowed and you see nothing until each
> generation completes. `run --rm` attaches directly — no buffering.

### Batch / detached mode (no live bar, JSON only)

```bash
docker compose up -d        # run in background
docker compose logs -f      # tail (tqdm \r will look ugly here)
docker compose down         # stop
```

JSON output (`./output/sim_result_<timestamp>.json`) is identical
either way — full per-generation history, config snapshot, and
extinction order.

### Per-generation verbose detail

The bar's `set_postfix` shows top 3 + bad-reputation %, but per-gen
leaderboards are silent by default. For research dives:

```bash
VERBOSE=1 docker compose run --rm simulator
```

### Dev container

`.devcontainer/devcontainer.json` shares the same `.env` via
`--env-file`, so `python -u main.py` inside the dev shell runs with
identical settings.

---

## ⚙️ Configuration

Every tunable lives in `.env` (copy from `.env.example`). Key groups:

| Group | Vars |
| :--- | :--- |
| Noise | `NOISE_RATE`, `INTERNAL_NOISE_RATE` |
| Alarm Call mechanics | `PROB_SPOT_DANGER`, `SURVIVAL_SPOTTER_NOTIFY`, `SURVIVAL_SPOTTER_RUN`, `SURVIVAL_LISTENER_WARNED`, `SURVIVAL_LISTENER_IGNORANT` |
| Evolution | `INITIAL_COPIES`, `SURVIVAL_FLOOR_FRAC`, `MAX_ENCOUNTERS_PER_AGENT`, `MAX_GENERATIONS` |
| Stability | `STABILITY_THRESHOLD`, `STABILITY_TOLERANCE` |
| Runtime | `VERBOSE` |

**Stability** (when to stop early): the last `STABILITY_THRESHOLD` generations
form a sliding window; every species' count must fluctuate by ≤ `STABILITY_TOLERANCE`
across that window. Stricter than "no species went extinct recently" — it
requires the population *counts* to settle, not just the *set*.

---

## 🛣️ Project Phases

This repo is staged. Phase 1 is what you're reading.

| Phase | Status | Focus |
| :--- | :--- | :--- |
| **Phase 1** — Cross-individual | ✅ Engine + strategies done | Well-mixed, no spatial structure, no species — pure individual-level test of "niceness without kinship" |
| **Phase 2** — Cross-species | 🔜 | Add `species` + `pair_kind` payoff matrix to test interspecies mutualism vs competition |
| **Phase 3** — Spatial | 🔜 | Bring back toroidal grid + migration + cultural transmission; see whether spatial structure amplifies or breaks Phase 1's conclusions |

---

## 📚 Theoretical Background

- Axelrod (1984), *The Evolution of Cooperation* — the well-mixed
  tournament model this repo's engine is adapted from.
- Hamilton (1964), *The Genetical Evolution of Social Behaviour* — the
  kin-selection rule whose premise this work deliberately strips away.
- Sugden (1986), *The Economics of Rights, Co-operation and Welfare* —
  the Standing Strategy implemented as the reputation update rules.
- Nowak & Sigmund (1998), *Evolution of Indirect Reciprocity by Image
  Scoring* — the precursor to Standing; first-order assessment.
- Ohtsuki & Iwasa (2004), *How should we define goodness?* — the
  "Leading Eight" stable social norms (Standing is one of them).

A companion repository `the_evolution_of_cooperation` runs the same
well-mixed framework on the classic Prisoner's Dilemma — useful for
contrasting "indefinite repeated PD" with "one-shot life-or-death".

---

## 📝 License

Apache License Version 2.0
