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
    before it manifests in the world. Survival depends on each agent's own
    role + (for listeners) the spotter's actual action + external noise.
    Reputation only updates for agents who actually had a choice to make.
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


def run_tournament(
    strategies: list[BaseStrategy],
    rounds_per_game: int,
    avg_matches_per_strategy: int,
    noise: float,
) -> list[BaseStrategy]:
    """
    Interaction-based tournament (adapted from the_evolution_of_cooperation).

    Total interactions = (N * avg_matches / 2) * rounds_per_game,
    each one a random pair drawn without replacement from the population.

    Silent on purpose — the caller owns all UI (so we don't fight with the
    outer-loop progress bar in main.py).
    """
    for s in strategies:
        s.reset()

    n = len(strategies)
    total_matches = (n * avg_matches_per_strategy) // 2
    total_interactions = total_matches * rounds_per_game

    for _ in range(total_interactions):
        s1, s2 = random.sample(strategies, 2)
        _resolve_interaction(s1, s2, noise)

    return sorted(strategies, key=lambda s: s.total_score, reverse=True)
