import json
import os
import sys
import time
from datetime import datetime

from tqdm import tqdm

from definitions import GameConfig
from simulation import load_all_strategies, run_evolution


RESET = "\033[0m"
VERBOSE = os.getenv("VERBOSE", "0") == "1"


def _color(name: str, color_map: dict) -> str:
    rgb = color_map.get(name)
    if not rgb:
        return name
    r, g, b = rgb
    return f"\033[38;2;{r};{g};{b}m{name}{RESET}"


def _format_leaderboard(
    counts: dict,
    extinction_order: list,
    color_map: dict,
    multiline: bool = False,
) -> str:
    """Render the leaderboard with medals for top 3 and numeric ranks beyond.

    Args:
        multiline: True for one entry per line (final ranking); False for
            a single " | "-separated line (compact in-progress display).
    """
    alive = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    extinct_names = set(name for _, name in extinction_order) - set(counts.keys())
    extinct_lookup = {name: gen for gen, name in extinction_order}
    extinct_sorted = sorted(
        extinct_names, key=lambda n: extinct_lookup.get(n, 0), reverse=True)

    medals = ["🥇", "🥈", "🥉"]
    parts: list[str] = []
    rank = 0

    for name, count in alive:
        rank += 1
        prefix = medals[rank - 1] if rank <= 3 else f"{rank:>2}."
        parts.append(f"{prefix} {_color(name, color_map)}: {count}")

    for name in extinct_sorted:
        rank += 1
        gen = extinct_lookup.get(name, "?")
        prefix = medals[rank - 1] if rank <= 3 else f"{rank:>2}."
        parts.append(f"{prefix} 💀 {_color(name, color_map)} (Gen {gen})")

    sep = "\n" if multiline else " | "
    return sep.join(parts)


def _print_header(strategy_types):
    """One-time configuration banner — scrolls off naturally as bar takes over."""
    print("🚀 Evolution started")
    print(f"  Strategies     : {len(strategy_types)}  (× {GameConfig.INITIAL_COPIES} copies each = "
          f"{len(strategy_types) * GameConfig.INITIAL_COPIES} agents)")
    print(f"  Capital        : baseline {GameConfig.CAPITAL_BASELINE}, "
          f"recover {GameConfig.CAPITAL_RECOVERY:.0%}/round toward it "
          f"(loss → graded, not death)")
    print(f"  Mortality      : {GameConfig.BASE_DEATH:.1%} + "
          f"{GameConfig.AGE_DEATH:.2%}×age per round, or bankruptcy "
          f"(long-but-finite lives)")
    print(f"  Encounters     : ~{GameConfig.ENCOUNTERS_PER_AGENT} per agent/round")
    print(f"  Assortment     : {GameConfig.ASSORTMENT:.2f} "
          f"(new-tie same-Standing bias)")
    print(f"  Network        : ~{GameConfig.AVG_DEGREE} contacts/agent, "
          f"churn {GameConfig.CHURN_RATE:.0%}/round "
          f"(0=village→private, 1=metropolis→reputation)")
    if GameConfig.BLIND_REPUTATION or GameConfig.BLIND_PRIVATE:
        off = (("reputation " if GameConfig.BLIND_REPUTATION else "")
               + ("private-history " if GameConfig.BLIND_PRIVATE else ""))
        print(f"  Knockout       : {off}ablated")
    print(f"  Noise (external/internal): {GameConfig.NOISE_RATE * 100:.1f}% / "
          f"{GameConfig.INTERNAL_NOISE_RATE * 100:.1f}%")
    print(f"  Stop on stability: window={GameConfig.STABILITY_THRESHOLD} gens, "
          f"each species' swing ≤ {GameConfig.STABILITY_TOLERANCE}")
    print(f"  Max generations: {GameConfig.MAX_GENERATIONS}")
    print(f"  Verbose per-gen: {'ON' if VERBOSE else 'OFF (set VERBOSE=1 to enable)'}")
    print()
    sys.stdout.flush()


def main():
    strategy_types = load_all_strategies()
    if not strategy_types:
        print("❌ No strategies found in strategies/")
        return

    color_map = {cls().name: cls().color for cls in strategy_types}
    type_to_name = {cls.__name__: cls().name for cls in strategy_types}

    _print_header(strategy_types)

    pbar = tqdm(
        total=GameConfig.MAX_GENERATIONS,
        desc="Generations",
        unit="gen",
        mininterval=0.2,
        smoothing=0.3,
        dynamic_ncols=True,
    )

    def on_gen(gen: int, snap: dict):
        counts_display = {
            type_to_name.get(k, k): v for k, v in snap["counts"].items()
        }
        rep = snap["reputation"]
        good = rep.get("Good", 0)
        bad = rep.get("Bad", 0)
        total = good + bad
        bad_pct = (bad / total * 100) if total else 0

        # Top 3 for live postfix — compact, no ANSI (tqdm garbles them).
        top3 = sorted(counts_display.items(), key=lambda kv: kv[1], reverse=True)[:3]
        top_str = ", ".join(f"{n}:{c}" for n, c in top3)

        swing = snap.get("max_swing", 0)
        fill = snap.get("window_fill", 0)
        gini = snap.get("capital_gini", 0)
        reenc = snap.get("re_encounter_rate", 0)
        pbar.set_postfix_str(
            f"top=[{top_str}] bad={bad_pct:.0f}% gini={gini:.2f} "
            f"reenc={reenc:.0%} "
            f"swing={swing}/{GameConfig.STABILITY_TOLERANCE} "
            f"window={fill}/{GameConfig.STABILITY_THRESHOLD}",
            refresh=False,
        )
        if gen > 0:
            pbar.update(1)

        # Milestones scroll cleanly above the bar via tqdm.write.
        for name in snap.get("extinct_this_gen", []):
            display = type_to_name.get(name, name)
            tqdm.write(
                f"  Generation {gen:>4}: {_color(display, color_map)} extinct 💀")

        if VERBOSE:
            ext_display = [(gen, type_to_name.get(n, n))
                           for n in snap.get("extinct_this_gen", [])]
            leaderboard = _format_leaderboard(
                counts_display, ext_display, color_map)
            duration = snap.get("duration_seconds")
            timing = f" {duration}s" if duration is not None else ""
            tqdm.write(f"  Gen {gen:>4}{timing} | {leaderboard}")

    start = time.time()
    try:
        result = run_evolution(strategy_types=strategy_types, on_generation=on_gen)
    finally:
        pbar.close()
    duration = time.time() - start

    print()
    print("=" * 60)
    print(f"🏁 Done in {duration:.2f}s "
          f"({result['generations_run']} generations, stopped: {result['stopped_reason']})")

    final_counts_display = {
        type_to_name.get(k, k): v for k, v in result["final_counts"].items()
    }
    final_extinction_display = [
        (gen, type_to_name.get(name, name))
        for gen, name in result["extinction_order"]
    ]
    print("👑 Final ranking:")
    print(_format_leaderboard(
        final_counts_display, final_extinction_display, color_map, multiline=True))

    _save_json(result, type_to_name, duration)


def _save_json(result: dict, type_to_name: dict, duration: float):
    output_dir = os.getenv("OUTPUT_DIR", "./output")
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(output_dir, f"sim_result_{timestamp}.json")

    history_clean = []
    for snap in result["history"]:
        history_clean.append({
            **snap,
            "counts": {type_to_name.get(k, k): v for k, v in snap["counts"].items()},
            "extinct_this_gen": [
                type_to_name.get(n, n) for n in snap.get("extinct_this_gen", [])
            ],
        })

    payload = {
        "meta": {
            "timestamp": timestamp,
            "duration_seconds": duration,
            "generations_run": result["generations_run"],
            "stopped_reason": result["stopped_reason"],
        },
        "config": {
            "noise_rate": GameConfig.NOISE_RATE,
            "internal_noise_rate": GameConfig.INTERNAL_NOISE_RATE,
            "prob_spot_danger": GameConfig.PROB_SPOT_DANGER,
            "initial_copies": GameConfig.INITIAL_COPIES,
            "encounters_per_agent": GameConfig.ENCOUNTERS_PER_AGENT,
            "capital_baseline": GameConfig.CAPITAL_BASELINE,
            "capital_recovery": GameConfig.CAPITAL_RECOVERY,
            "base_death": GameConfig.BASE_DEATH,
            "age_death": GameConfig.AGE_DEATH,
            "assortment": GameConfig.ASSORTMENT,
            "avg_degree": GameConfig.AVG_DEGREE,
            "churn_rate": GameConfig.CHURN_RATE,
            "blind_reputation": GameConfig.BLIND_REPUTATION,
            "blind_private": GameConfig.BLIND_PRIVATE,
            "stability_threshold": GameConfig.STABILITY_THRESHOLD,
            "stability_tolerance": GameConfig.STABILITY_TOLERANCE,
        },
        "final": {
            "counts": {type_to_name.get(k, k): v for k, v in result["final_counts"].items()},
            "extinction_order": [
                {"generation": g, "name": type_to_name.get(n, n)}
                for g, n in result["extinction_order"]
            ],
        },
        "history": history_clean,
    }

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"✅ Saved → {path}")
    except Exception as e:
        print(f"❌ Failed to save: {e}")


if __name__ == "__main__":
    main()
