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
        self.contacts: dict = {a: set() for a in agents}
        self._seed(list(agents), avg_degree)

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
            self.contacts[nb].discard(agent)
        self.contacts.pop(agent, None)

    def on_birth(self, agent, degree):
        """Add a newborn (a stranger entering the network) with fresh ties."""
        self.contacts[agent] = set()
        for _ in range(degree):
            self._rewire(agent)

    # ------------------------------------------------------------------
    # Interaction + dynamics
    # ------------------------------------------------------------------

    def draw_encounter(self):
        """Pick a random agent and one of its contacts. Returns (a, b) or None."""
        a = random.choice(list(self.contacts.keys()))
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
            self.contacts[a].add(b)
            self.contacts[b].add(a)

    def _unlink(self, a, b):
        self.contacts[a].discard(b)
        self.contacts[b].discard(a)

    def _rewire(self, a):
        """Give `a` one new contact, preferring same Standing w.p. assortment."""
        candidates = [x for x in self.contacts
                      if x is not a and x not in self.contacts[a]]
        if not candidates:
            return
        if self.assortment > 0 and random.random() < self.assortment:
            same = [x for x in candidates if x.reputation == a.reputation]
            if same:
                candidates = same
        self._link(a, random.choice(candidates))

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
