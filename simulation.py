import collections
import importlib
import inspect
import pkgutil
import random
import time
from collections import deque
from typing import Iterable, Type

import engine
from base_strategy import BaseStrategy
from definitions import GameConfig


def load_all_strategies() -> list[Type[BaseStrategy]]:
    """Auto-discover every concrete subclass of BaseStrategy under strategies/."""
    found: list[Type[BaseStrategy]] = []
    package = importlib.import_module("strategies")
    prefix = package.__name__ + "."

    for _, module_name, _ in pkgutil.iter_modules(package.__path__, prefix):
        try:
            module = importlib.import_module(module_name)
        except Exception as e:
            print(f"⚠️  Skipping {module_name}: {e}")
            continue

        for _, obj in inspect.getmembers(module):
            if (
                inspect.isclass(obj)
                and issubclass(obj, BaseStrategy)
                and obj is not BaseStrategy
                and obj not in found
            ):
                found.append(obj)

    return found


def _build_population(
    strategy_types: Iterable[Type[BaseStrategy]],
    initial_copies: int,
) -> list[BaseStrategy]:
    population: list[BaseStrategy] = []
    for cls in strategy_types:
        for _ in range(initial_copies):
            population.append(cls())
    return population


def _breed(
    survivors: list[BaseStrategy], target_size: int
) -> list[BaseStrategy]:
    """
    Refill the population to `target_size` by cloning survivors.

    Parents are drawn with replacement, so a type's share of the next
    generation is proportional to how many of it survived — survival is the
    selection signal. Each newborn inherits its parent's Standing.
    """
    parents = random.choices(survivors, k=target_size)
    return [parent.spawn_offspring() for parent in parents]


def _count_by_type(population: Iterable[BaseStrategy]) -> collections.Counter:
    return collections.Counter(type(s).__name__ for s in population)


def _reputation_distribution(population: Iterable[BaseStrategy]) -> dict:
    counter: collections.Counter = collections.Counter()
    for s in population:
        counter[s.reputation.value] += 1
    return dict(counter)


def _max_swing(window: deque) -> int:
    """Largest (max - min) of any species' count within the window."""
    if not window:
        return 0
    species: set = set()
    for snap in window:
        species.update(snap.keys())
    max_diff = 0
    for sp in species:
        counts = [snap.get(sp, 0) for snap in window]
        diff = max(counts) - min(counts)
        if diff > max_diff:
            max_diff = diff
    return max_diff


def run_evolution(
    strategy_types: list[Type[BaseStrategy]],
    initial_copies: int = GameConfig.INITIAL_COPIES,
    survival_floor_frac: float = GameConfig.SURVIVAL_FLOOR_FRAC,
    max_encounters_per_agent: int = GameConfig.MAX_ENCOUNTERS_PER_AGENT,
    noise: float = GameConfig.NOISE_RATE,
    stability_threshold: int = GameConfig.STABILITY_THRESHOLD,
    stability_tolerance: int = GameConfig.STABILITY_TOLERANCE,
    max_generations: int = GameConfig.MAX_GENERATIONS,
    on_generation=None,
) -> dict:
    """
    Run a full evolutionary simulation.

    Each generation:
      1. Run a brutal one-shot tournament (engine.run_generation): agents
         die from the survival roll until the living pool hits the floor.
      2. The survivors breed back up to N (carrying capacity); each newborn
         inherits only its parent's Standing. The dead leave no descendants.
      3. Track extinctions and stability.

    Termination:
      - Stable: a window of the last `stability_threshold` generations, in
        which every species' count fluctuated by ≤ `stability_tolerance`.
        (This is stricter than species-set-stable: it requires both the set
        AND the counts to settle, so we don't stop while populations are
        still swinging.)
      - Only one strategy type remains (winner), OR
      - Everyone died in a generation (extinct), OR
      - `max_generations` reached.

    `on_generation(generation, snapshot)` is called every generation with a
    dict snapshot for callers that want to stream / log. The simulation
    itself is silent — the caller owns all UI.
    """
    population = _build_population(strategy_types, initial_copies)
    target_size = len(population)

    counts = _count_by_type(population)
    surviving = set(counts.keys())

    history: list[dict] = []
    extinction_order: list[tuple] = []
    stability_window: deque = deque(maxlen=stability_threshold)
    last_surviving = surviving
    generation = 0
    stopped_reason = "max_generations"

    stability_window.append(dict(counts))
    initial_snapshot = {
        "generation": 0,
        "counts": dict(counts),
        "reputation": _reputation_distribution(population),
        "max_swing": 0,
        "window_fill": len(stability_window),
    }
    history.append(initial_snapshot)
    if on_generation:
        on_generation(0, initial_snapshot)

    while generation < max_generations:
        generation += 1
        gen_started = time.time()

        survivors = engine.run_generation(
            population,
            noise=noise,
            survival_floor_frac=survival_floor_frac,
            max_encounters_per_agent=max_encounters_per_agent,
        )

        if not survivors:
            # Total wipe-out — nobody left to breed the next generation.
            stopped_reason = "extinct"
            counts = collections.Counter()
            surviving = set()
            just_extinct = last_surviving
            for name in just_extinct:
                extinction_order.append((generation, name))
            snapshot = {
                "generation": generation,
                "counts": {},
                "reputation": {},
                "extinct_this_gen": list(just_extinct),
                "max_swing": 0,
                "window_fill": len(stability_window),
                "duration_seconds": round(time.time() - gen_started, 3),
            }
            history.append(snapshot)
            if on_generation:
                on_generation(generation, snapshot)
            break

        # Selection + reproduction: only survivors breed, cloning back up to
        # carrying capacity. Composition follows who survived; each newborn
        # inherits its parent's Standing (the lone bit that crosses a gen).
        population = _breed(survivors, target_size)

        counts = _count_by_type(population)
        surviving = set(counts.keys())

        just_extinct = last_surviving - surviving
        for name in just_extinct:
            extinction_order.append((generation, name))
        last_surviving = surviving

        stability_window.append(dict(counts))
        max_swing = _max_swing(stability_window)

        snapshot = {
            "generation": generation,
            "counts": dict(counts),
            "reputation": _reputation_distribution(population),
            "extinct_this_gen": list(just_extinct),
            "max_swing": max_swing,
            "window_fill": len(stability_window),
            "duration_seconds": round(time.time() - gen_started, 3),
        }
        history.append(snapshot)
        if on_generation:
            on_generation(generation, snapshot)

        if (
            len(stability_window) == stability_threshold
            and max_swing <= stability_tolerance
        ):
            stopped_reason = "stable"
            break

        if len(surviving) <= 1:
            stopped_reason = "winner" if len(surviving) == 1 else "extinct"
            break

    return {
        "final_counts": dict(counts),
        "final_population": population,
        "extinction_order": extinction_order,
        "history": history,
        "generations_run": generation,
        "stopped_reason": stopped_reason,
    }
