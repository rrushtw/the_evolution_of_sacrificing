import random

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


def _resolve_interaction(s1: BaseStrategy, s2: BaseStrategy, noise: float):
    """
    One Alarm Call round between two agents.

    Both independently roll for whether they detect danger; whoever spots
    makes a moral choice (NOTIFY/RUN). Internal noise may flip that choice
    before it manifests in the world. The outcome is a graded change in each
    agent's CAPITAL, not a life-or-death roll: the payoff (fraction kept) maps
    to delta = payoff − 1, so a missed warning (IGNORANT, 0.05) is a heavy
    −0.95 hit ('lost your shirt'), NOTIFY a small −0.1 cost, and being warned
    or running safely costs nothing. Capital recovers slowly elsewhere; ruin
    is rare. Reputation only updates for agents who actually had a choice.
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
    )
    s2.record_round(
        opponent_unique_id=s1.unique_id,
        my_action=s2_action,
        opponent_action=s1_action,
    )

    # Graded capital change: payoff is the fraction kept, so the loss is
    # (payoff − 1). Being warned / running safely → 0; NOTIFY → −0.1; a missed
    # warning → −0.95. Hurts, but you usually live to recover.
    s1.apply_capital(s1_survival - 1.0)
    s2.apply_capital(s2_survival - 1.0)

    if s1_spots:
        s1.update_reputation(s1_action, s2_rep_seen_by_s1)
    if s2_spots:
        s2.update_reputation(s2_action, s1_rep_seen_by_s2)


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


def run_round(
    population: list[BaseStrategy],
    noise: float,
    encounters_per_agent: int,
    assortment: float = 0.0,
):
    """
    Run one round of well-mixed Alarm Call encounters, mutating capital.

    Draws (encounters_per_agent × N // 2) random pairs (so each agent plays
    ~encounters_per_agent times) and resolves each — every interaction nudges
    both agents' capital. Nobody dies here: aging, mortality and reproduction
    are the caller's job (see simulation.run_evolution), which keeps the
    population intact for the whole round. Silent on purpose.
    """
    n = len(population)
    interactions = (n * encounters_per_agent) // 2
    for _ in range(interactions):
        s1, s2 = _draw_pair(population, assortment)
        _resolve_interaction(s1, s2, noise)
