import random
from math import ceil

from definitions import Action, GameConfig, Reputation
from base_strategy import BaseStrategy


def _spotter_outcome(action: Action) -> float:
    """Survival probability for the agent that actually spotted danger."""
    if action == Action.NOTIFY:
        return GameConfig.SURVIVAL_SPOTTER_NOTIFY
    return GameConfig.SURVIVAL_SPOTTER_RUN


def _listener_outcome(spotter_action: Action | None, noise: float) -> float:
    """
    Survival probability for the agent who did NOT spot the danger,
    given what (if anything) their partner did.
    """
    if spotter_action is None:
        # No one detected danger — both fly blind.
        return GameConfig.SURVIVAL_LISTENER_IGNORANT

    if spotter_action == Action.NOTIFY:
        # External noise may swallow the warning.
        if random.random() < noise:
            return GameConfig.SURVIVAL_LISTENER_IGNORANT
        return GameConfig.SURVIVAL_LISTENER_WARNED

    # Spotter ran — listener might still notice them fleeing.
    if random.random() < noise:
        return GameConfig.SURVIVAL_LISTENER_WARNED
    return GameConfig.SURVIVAL_LISTENER_IGNORANT


def _resolve_interaction(
    s1: BaseStrategy, s2: BaseStrategy, noise: float
) -> tuple[bool, bool]:
    """
    One Alarm Call round between two agents.

    Both independently roll for whether they detect danger; whoever spots
    makes a moral choice (NOTIFY/RUN). Internal noise may flip that choice
    before it manifests in the world. Survival depends on each agent's own
    role + (for listeners) the spotter's actual action + external noise.
    Reputation only updates for agents who actually had a choice to make.

    The survival probability is a literal life-or-death roll: each agent
    rolls once and dies if it fails. Returns (s1_died, s2_died) so the
    caller can remove the dead from the living pool immediately — a single
    unlucky encounter can end an individual. This is the model's core
    cost: death, not a soft score penalty.
    """
    p_spot = GameConfig.PROB_SPOT_DANGER

    s1_spots = random.random() < p_spot
    s2_spots = random.random() < p_spot

    # Snapshot reputations at the moment of decision — Standing judges
    # based on what the opponent was perceived as right then.
    s1_rep_seen_by_s2 = s1.reputation
    s2_rep_seen_by_s1 = s2.reputation

    s1_action: Action | None = None
    s2_action: Action | None = None

    if s1_spots:
        intent = s1.decide(
            opponent_unique_id=s2.unique_id,
            opponent_reputation=s2_rep_seen_by_s1,
            opponent_history=s2.my_history,
        )
        s1_action = s1.apply_internal_noise(intent)

    if s2_spots:
        intent = s2.decide(
            opponent_unique_id=s1.unique_id,
            opponent_reputation=s1_rep_seen_by_s2,
            opponent_history=s1.my_history,
        )
        s2_action = s2.apply_internal_noise(intent)

    if s1_spots:
        s1_survival = _spotter_outcome(s1_action)
    else:
        s1_survival = _listener_outcome(s2_action, noise)

    if s2_spots:
        s2_survival = _spotter_outcome(s2_action)
    else:
        s2_survival = _listener_outcome(s1_action, noise)

    s1.record_round(
        opponent_unique_id=s2.unique_id,
        my_action=s1_action,
        opponent_action=s2_action,
        survival_score=s1_survival,
    )
    s2.record_round(
        opponent_unique_id=s1.unique_id,
        my_action=s2_action,
        opponent_action=s1_action,
        survival_score=s2_survival,
    )

    if s1_spots:
        s1.update_reputation(s1_action, s2_rep_seen_by_s1)
    if s2_spots:
        s2.update_reputation(s2_action, s1_rep_seen_by_s2)

    # Life-or-death roll: survival probability is the chance to live, not a score.
    s1_died = random.random() >= s1_survival
    s2_died = random.random() >= s2_survival
    return s1_died, s2_died


def _draw_pair(living: list[BaseStrategy], assortment: float):
    """
    Pick two distinct living agents for an encounter.

    With probability `assortment` the partner is drawn from those sharing the
    first agent's Standing (homophily / clustering); otherwise the partner is
    fully random. Falls back to random whenever no same-Standing partner
    exists (e.g. gen 0, when everyone is still GOOD). assortment=0 reproduces
    the well-mixed baseline exactly.
    """
    s1 = random.choice(living)
    pool = None
    if assortment > 0 and random.random() < assortment:
        pool = [a for a in living if a is not s1 and a.reputation == s1.reputation]
    if not pool:
        pool = [a for a in living if a is not s1]
    return s1, random.choice(pool)


def run_generation(
    population: list[BaseStrategy],
    noise: float,
    survival_floor_frac: float,
    max_encounters_per_agent: int,
    assortment: float = 0.0,
) -> list[BaseStrategy]:
    """
    Run one brutal, well-mixed Alarm Call generation and return the survivors.

    Repeatedly draw two living agents at random for a one-shot interaction;
    each interaction may kill one or both (see _resolve_interaction). The
    dead leave the living pool at once and can never be drawn again — so an
    individual's whole generation can end on a single bad encounter.

    The generation stops as soon as the living pool falls to the survival
    floor (ceil(N * survival_floor_frac)) — capping mortality so the species
    can persist across many generations instead of collapsing in one. A
    safety cap of (N * max_encounters_per_agent // 2) interactions ends a
    placid, low-death generation that never reaches the floor.

    Silent on purpose — the caller owns all UI.
    """
    living = list(population)
    n = len(living)
    floor = max(2, ceil(n * survival_floor_frac))
    interaction_cap = (n * max_encounters_per_agent) // 2

    for _ in range(interaction_cap):
        if len(living) <= floor:
            break
        s1, s2 = _draw_pair(living, assortment)
        s1_died, s2_died = _resolve_interaction(s1, s2, noise)
        if s2_died:
            living.remove(s2)
        if s1_died:
            living.remove(s1)

    return living
