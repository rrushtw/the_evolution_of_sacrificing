import random

from definitions import Action, GameConfig, OpponentView, Reputation
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

    Returns True if an EXPLOITATION occurred — a spotter RAN on a GOOD partner
    — so the caller can snap that tie (the exploiter flees).
    """
    p_spot = GameConfig.PROB_SPOT_DANGER

    s1_spots = random.random() < p_spot
    s2_spots = random.random() < p_spot

    # True Standing drives the network mechanic + the reputation update; what
    # each decider SEES is forced to GOOD when reputation is knocked out.
    s1_rep_true = s1.reputation
    s2_rep_true = s2.reputation
    if GameConfig.BLIND_REPUTATION:
        s1_rep_seen_by_s2 = s2_rep_seen_by_s1 = Reputation.GOOD
    else:
        s1_rep_seen_by_s2 = s1_rep_true
        s2_rep_seen_by_s1 = s2_rep_true

    s1_action: Action | None = None
    s2_action: Action | None = None

    # Public channel = Standing bit + the opponent's public action log. The
    # reputation knockout hides BOTH (a stranger you know nothing public about).
    blind_pub = GameConfig.BLIND_REPUTATION
    s2_pub_hist = [] if blind_pub else s2.my_history
    s1_pub_hist = [] if blind_pub else s1.my_history

    # Capital is the Phase 2.5 channel — always visible (no BLIND_CAPITAL yet).
    if s1_spots:
        intent = s1.decide(OpponentView(
            unique_id=s2.unique_id,
            reputation=s2_rep_seen_by_s1,
            history=s2_pub_hist,
            capital=s2.capital,
        ))
        s1_action = s1.apply_internal_noise(intent)

    if s2_spots:
        intent = s2.decide(OpponentView(
            unique_id=s1.unique_id,
            reputation=s1_rep_seen_by_s2,
            history=s1_pub_hist,
            capital=s1.capital,
        ))
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
        s1.update_reputation(s1_action, s2_rep_true)
    if s2_spots:
        s2.update_reputation(s2_action, s1_rep_true)

    # Exploitation = a spotter RAN on a partner whose true Standing was GOOD.
    return (
        (s1_spots and s1_action == Action.RUN and s2_rep_true == Reputation.GOOD)
        or (s2_spots and s2_action == Action.RUN and s1_rep_true == Reputation.GOOD)
    )


def run_round(population, network, noise, encounters_per_agent, churn_rate):
    """
    Run one round of Alarm Call encounters over the social network.

    Each of (encounters_per_agent × N // 2) interactions is drawn between an
    agent and one of its current contacts — so the same pair meets repeatedly
    and private history accrues. An exploited tie (a spotter running on a GOOD
    contact) snaps and the exploiter flees (network.break_and_flee), then the
    whole graph churns by churn_rate. Only capital is mutated here; aging,
    mortality and reproduction are the caller's job.

    Returns per-round stats: total encounters, how many were REPEATS (both
    parties had prior private history = realised re-encounter rate), and how
    many exploitations occurred.
    """
    n = len(population)
    interactions = (n * encounters_per_agent) // 2
    encounters = repeats = exploitations = 0
    for _ in range(interactions):
        pair = network.draw_encounter()
        if pair is None:
            continue
        s1, s2 = pair
        is_repeat = bool(s1.private_history_with(s2.unique_id)) or bool(
            s2.private_history_with(s1.unique_id))
        exploited = _resolve_interaction(s1, s2, noise)
        encounters += 1
        repeats += is_repeat
        if exploited:
            network.break_and_flee(s1, s2)
            exploitations += 1
    network.churn(churn_rate)
    return {"encounters": encounters, "repeats": repeats,
            "exploitations": exploitations}
