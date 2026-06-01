import abc
import random
import uuid
from typing import Tuple

from definitions import Action, GameConfig, Reputation


class BaseStrategy(abc.ABC):
    """
    Abstract contract for every strategy.

    Phase 1 design:
    - decide() receives ONLY 4 public fields about the opponent — never the
      opponent instance itself. This blocks any `type(opponent)` cheat and
      enforces the "you don't know friend from foe" research premise.
    - Reputation is binary (GOOD/BAD), updated by Standing Strategy rules.
    - Memory has two layers: my_history (public log) and opponent_history
      (private record keyed by opponent's unique_id).
    """

    def __init__(self):
        self.unique_id: str = str(uuid.uuid4())
        self.reset()

    def reset(self):
        """Called once when an agent is born (constructor)."""
        # Standing rule 4: a fresh agent starts GOOD (presumption of innocence).
        # This applies to the gen-0 founders. Later generations are bred via
        # spawn_offspring(), which OVERRIDES this to inherit the parent's
        # Standing — a lineage that earned BAD passes that stigma on.
        self.reputation: Reputation = Reputation.GOOD
        # Each entry: {"my_action": Action|None, "opponent_action": Action|None}
        # None = that party didn't spot danger this round.
        self.my_history: list[dict] = []
        self.opponent_history: dict[str, list[dict]] = {}
        # Capital replaces binary life/death: outcomes nudge it up or down,
        # it recovers slowly toward baseline, and hitting zero = bankruptcy
        # (a rare, real death). Reproduction is weighted by capital.
        self.capital: float = GameConfig.CAPITAL_BASELINE
        # Age in rounds. Mortality rises with age — long-lived but not immortal.
        self.age: int = 0

    # ------------------------------------------------------------------
    # Identity (each strategy must declare its public-facing identity)
    # ------------------------------------------------------------------

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Display name, e.g. 'Altruist'."""
        pass

    @property
    @abc.abstractmethod
    def color(self) -> Tuple[int, int, int]:
        """(R, G, B) for terminal output."""
        pass

    # ------------------------------------------------------------------
    # Decision (the only contract the engine cares about)
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def decide(
        self,
        opponent_unique_id: str,
        opponent_reputation: Reputation,
        opponent_history: list[dict],
    ) -> Action:
        """
        Called by the engine when this agent is the spotter.

        Args:
            opponent_unique_id: opaque ID — only useful for keying into
                self.opponent_history for private memory of this opponent.
            opponent_reputation: public Standing of the opponent (GOOD/BAD).
            opponent_history: opponent's full public log (their my_history).
                Each entry is a dict like {"my_action": ..., "opponent_action": ...}
                from the opponent's point of view.

        Returns:
            Action.NOTIFY or Action.RUN.
        """
        pass

    # ------------------------------------------------------------------
    # Noise (slip of tongue — slipped intent is treated as real intent)
    # ------------------------------------------------------------------

    def apply_internal_noise(self, intended: Action) -> Action:
        if random.random() < GameConfig.INTERNAL_NOISE_RATE:
            return Action.RUN if intended == Action.NOTIFY else Action.NOTIFY
        return intended

    # ------------------------------------------------------------------
    # Bookkeeping — called by the engine after every interaction
    # ------------------------------------------------------------------

    def record_round(
        self,
        opponent_unique_id: str,
        my_action: Action | None,
        opponent_action: Action | None,
    ):
        """
        Append this round to both the public log (my_history) and the private,
        per-opponent record (opponent_history). Capital is applied separately
        by the engine via apply_capital().
        """
        record = {
            "my_action": my_action,
            "opponent_action": opponent_action,
        }
        self.my_history.append(record)
        self.opponent_history.setdefault(opponent_unique_id, []).append(record)

    # ------------------------------------------------------------------
    # Capital — graded fortune that replaces binary survival
    # ------------------------------------------------------------------

    def apply_capital(self, delta: float):
        """Apply an interaction's gain/loss to this agent's capital."""
        self.capital += delta

    def recover(self):
        """
        Drift capital back toward baseline by a fixed fraction of the gap —
        a big loss heals slowly, so its shadow lingers (the 'shadow of the
        future' that lets reciprocity pay off). Called once per round.
        """
        self.capital += GameConfig.CAPITAL_RECOVERY * (
            GameConfig.CAPITAL_BASELINE - self.capital
        )

    def is_bankrupt(self) -> bool:
        """Capital exhausted — a rare, real death (ruin)."""
        return self.capital <= 0.0

    def update_reputation(
        self,
        my_action: Action,
        opponent_reputation_at_time: Reputation,
    ):
        """
        Apply Standing Strategy (Sugden 1986) — 4 rules total:

            1. NOTIFY                    -> GOOD (unconditional)
            2. RUN against GOOD opponent -> BAD
            3. RUN against BAD opponent  -> unchanged (justified defection)
            4. new agent                 -> GOOD (handled in reset())

        Called by the engine ONLY when this agent was the spotter
        (listeners don't make a moral choice).
        """
        if my_action == Action.NOTIFY:
            self.reputation = Reputation.GOOD
        elif my_action == Action.RUN:
            if opponent_reputation_at_time == Reputation.GOOD:
                self.reputation = Reputation.BAD
            # else: justified defection — no change

    # ------------------------------------------------------------------
    # Convenience helpers strategies may use
    # ------------------------------------------------------------------

    def private_history_with(self, opponent_unique_id: str) -> list[dict]:
        """Sugar: my private record of interactions with this specific opponent."""
        return self.opponent_history.get(opponent_unique_id, [])

    def spawn_offspring(self) -> "BaseStrategy":
        """
        Produce one fresh offspring of the same strategy type. The child is
        brand new (own unique_id, empty history, baseline capital, age 0)
        EXCEPT it inherits this parent's public Standing — the single bit of
        memory that crosses a generation.
        """
        child = type(self)()
        child.reputation = self.reputation
        return child

    def __str__(self):
        return self.name
