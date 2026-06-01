import collections
import importlib
import inspect
import pkgutil
import random
import time
from collections import deque
from typing import Iterable, Type

import engine
import network
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


def _repopulate(
    survivors: list[BaseStrategy], n_deaths: int
) -> list[BaseStrategy]:
    """
    Breed `n_deaths` newborns to replace the dead, keeping the population at N.

    Parents are drawn with replacement, weighted by CAPITAL — the rich /
    influential reproduce more, so capital is the selection signal (the
    'influence gap' driving who propagates). Each newborn inherits its
    parent's Standing; survivors all have capital > 0 (bankrupts already died).
    """
    if n_deaths <= 0:
        return []
    weights = [max(0.0, s.capital) for s in survivors]
    if sum(weights) <= 0:
        weights = None  # degenerate: fall back to uniform
    parents = random.choices(survivors, weights=weights, k=n_deaths)
    return [parent.spawn_offspring() for parent in parents]


def _gini(values: list[float]) -> float:
    """Gini coefficient (0 = equal, →1 = unequal). Assumes non-negative values."""
    vals = sorted(values)
    n = len(vals)
    total = sum(vals)
    if n == 0 or total <= 0:
        return 0.0
    weighted = sum((2 * (i + 1) - n - 1) * v for i, v in enumerate(vals))
    return weighted / (n * total)


def _capital_stats(population: Iterable[BaseStrategy]) -> dict:
    """Capital + age summary — the observable 'influence gap' of the society."""
    pop = list(population)
    n = len(pop) or 1
    caps = [a.capital for a in pop]
    return {
        "capital_mean": round(sum(caps) / n, 4),
        "capital_gini": round(_gini(caps), 4),
        "age_mean": round(sum(a.age for a in pop) / n, 2),
    }


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
    encounters_per_agent: int = GameConfig.ENCOUNTERS_PER_AGENT,
    assortment: float = GameConfig.ASSORTMENT,
    churn_rate: float = GameConfig.CHURN_RATE,
    noise: float = GameConfig.NOISE_RATE,
    stability_threshold: int = GameConfig.STABILITY_THRESHOLD,
    stability_tolerance: int = GameConfig.STABILITY_TOLERANCE,
    max_generations: int = GameConfig.MAX_GENERATIONS,
    on_generation=None,
) -> dict:
    """
    Run a full evolutionary simulation.

    Each round (= one "generation" tick for the UI/stability machinery):
      1. engine.run_round: well-mixed encounters nudge everyone's capital.
      2. Every agent recovers a little toward baseline and ages one round.
      3. Mortality: agents die of old age (rising with age) or bankruptcy.
      4. Each death is replaced by an offspring of a capital-weighted parent,
         inheriting its Standing — population stays at N (overlapping gens).
      5. Track extinctions, capital/age stats, and stability.

    Termination:
      - Stable: a window of the last `stability_threshold` generations, in
        which every species' count fluctuated by ≤ `stability_tolerance`.
        (This is stricter than species-set-stable: it requires both the set
        AND the counts to settle, so we don't stop while populations are
        still swinging.)
      - Only one strategy type remains (winner), OR
      - Everyone died in one round (extinct — rare), OR
      - `max_generations` reached.

    `on_generation(generation, snapshot)` is called every generation with a
    dict snapshot for callers that want to stream / log. The simulation
    itself is silent — the caller owns all UI.
    """
    population = _build_population(strategy_types, initial_copies)
    net = network.Network(population, GameConfig.AVG_DEGREE, assortment)

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
        **_capital_stats(population),
    }
    history.append(initial_snapshot)
    if on_generation:
        on_generation(0, initial_snapshot)

    while generation < max_generations:
        generation += 1
        gen_started = time.time()

        # 1. Encounters over the social network mutate capital; exploited ties
        #    snap (exploiter flees) and the graph churns. No deaths here.
        stats = engine.run_round(
            population,
            net,
            noise=noise,
            encounters_per_agent=encounters_per_agent,
            churn_rate=churn_rate,
        )

        # 2. Recover toward baseline + age one round.
        for agent in population:
            agent.recover()
            agent.age += 1

        # 3. Mortality: old age (rising with age) or bankruptcy.
        survivors, dead = [], []
        for agent in population:
            death_prob = min(1.0, GameConfig.BASE_DEATH
                             + GameConfig.AGE_DEATH * agent.age)
            if agent.is_bankrupt() or random.random() < death_prob:
                dead.append(agent)
            else:
                survivors.append(agent)

        if not survivors:
            # Everyone died this round — rare total wipe-out.
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
                "capital_mean": 0, "capital_gini": 0, "age_mean": 0,
            }
            history.append(snapshot)
            if on_generation:
                on_generation(generation, snapshot)
            break

        # 4. Replace each death with an offspring of a capital-weighted parent;
        #    keep the network in sync (dead drop out, newborns enter as strangers).
        for d in dead:
            net.on_death(d)
        newborns = _repopulate(survivors, len(dead))
        for nb in newborns:
            net.on_birth(nb, GameConfig.AVG_DEGREE)
        population = survivors + newborns

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
            "re_encounter_rate": round(
                stats["repeats"] / (stats["encounters"] or 1), 4),
            "exploitations": stats["exploitations"],
            **_capital_stats(population),
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
