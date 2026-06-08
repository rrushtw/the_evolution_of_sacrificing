import random


class Network:
    """
    An undirected social graph over agents.

    Agents interact with their current *contacts*, so the same pair meets
    again and again — which is what lets private, per-opponent history mean
    anything. Two forces reshape the graph:

    - **Churn** (the village↔metropolis dial): each round every tie has a
      `churn_rate` chance of dissolving, both ends drifting to new contacts.
      At 0 you keep your circle for life (a village — private memory rules);
      near 1 the graph reshuffles constantly (a metropolis — you mostly face
      strangers, so public reputation is the only guide).

    - **Exploitation flight**: when one agent RUNs on a GOOD contact (a
      betrayal), that tie snaps and the exploiter forms a fresh tie elsewhere
      — fleeing to a new circle. The victim can no longer find them to take
      private revenge; only the exploiter's BAD reputation can warn the next
      target. This is the hit-and-run (scam / one-off rival) that private
      history is powerless against.

    New ties prefer a same-Standing partner with probability `assortment`.
    """

    def __init__(self, agents, avg_degree, assortment):
        self.assortment = assortment
        # contacts[a] is an *insertion-ordered* set of a's neighbours — a dict
        # used as an ordered set (values are None). Ordinary sets iterate in
        # object-id (memory-address) order, which differs run-to-run and breaks
        # RANDOM_SEED reproducibility; a dict preserves the seed-determined
        # construction order, so a fixed seed replays identically.
        self.contacts: dict = {a: {} for a in agents}
        # Cached node list so draw/rewire are O(1) amortized, not O(N) — this
        # is what keeps high-churn runs (and 30× batch sweeps) tractable.
        self._nodes: list = list(agents)
        self._seed(self._nodes, avg_degree)

    # ------------------------------------------------------------------
    # Construction / turnover
    # ------------------------------------------------------------------

    def _seed(self, agents, avg_degree):
        target_edges = avg_degree * len(agents) // 2
        added = attempts = 0
        cap = target_edges * 20 + 1
        while added < target_edges and attempts < cap:
            attempts += 1
            a, b = random.sample(agents, 2)
            if b not in self.contacts[a]:
                self._link(a, b)
                added += 1

    def on_death(self, agent):
        """Remove a dead agent and all its ties."""
        for nb in list(self.contacts.get(agent, ())):
            self.contacts[nb].pop(agent, None)
        self.contacts.pop(agent, None)
        self._nodes.remove(agent)

    def on_birth(self, agent, degree):
        """Add a newborn (a stranger entering the network) with fresh ties."""
        self.contacts[agent] = {}
        self._nodes.append(agent)
        for _ in range(degree):
            self._rewire(agent)

    # ------------------------------------------------------------------
    # Interaction + dynamics
    # ------------------------------------------------------------------

    def draw_encounter(self):
        """Pick a random agent and one of its contacts. Returns (a, b) or None."""
        a = random.choice(self._nodes)
        if not self.contacts[a]:
            self._rewire(a)
            if not self.contacts[a]:
                return None
        b = random.choice(tuple(self.contacts[a]))
        return a, b

    def break_and_flee(self, exploiter, victim):
        """Sever an exploited tie; both ends drift to a new contact (the
        exploiter flees, the victim moves on) — so they no longer meet."""
        self._unlink(exploiter, victim)
        self._rewire(exploiter)
        self._rewire(victim)

    def churn(self, rate):
        """Each tie independently dissolves (both ends rewiring) with prob rate."""
        if rate <= 0:
            return
        for a, b in self._edges():
            if b in self.contacts[a] and random.random() < rate:
                self._unlink(a, b)
                self._rewire(a)
                self._rewire(b)

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def _link(self, a, b):
        if a is not b:
            self.contacts[a][b] = None
            self.contacts[b][a] = None

    def _unlink(self, a, b):
        self.contacts[a].pop(b, None)
        self.contacts[b].pop(a, None)

    def _rewire(self, a):
        """
        Give `a` one new contact, preferring same Standing w.p. assortment.

        Rejection sampling over the cached node list — O(1) amortized because
        degree ≪ N, so a random pick is almost always a valid non-contact.
        """
        if len(self._nodes) <= len(self.contacts[a]) + 1:
            return  # already tied to everyone available
        prefer_same = self.assortment > 0 and random.random() < self.assortment
        for _ in range(24):
            cand = random.choice(self._nodes)
            if cand is a or cand in self.contacts[a]:
                continue
            if prefer_same and cand.reputation != a.reputation:
                continue
            self._link(a, cand)
            return
        # Fallback: drop the same-Standing preference rather than fail.
        for _ in range(24):
            cand = random.choice(self._nodes)
            if cand is not a and cand not in self.contacts[a]:
                self._link(a, cand)
                return

    def _edges(self):
        """Snapshot of undirected edges as (a, b) pairs, each once."""
        seen = set()
        out = []
        for a, nbrs in self.contacts.items():
            for b in nbrs:
                key = frozenset((id(a), id(b)))
                if key not in seen:
                    seen.add(key)
                    out.append((a, b))
        return out
