"""不變量(6):社會網路一致性 —— 對稱、無自環、無 dangling、生死同步。"""
import random

from network import Network
from tests.conftest import AlwaysNotify


def _build(n=40, degree=6, assortment=0.0):
    random.seed(123)
    agents = [AlwaysNotify() for _ in range(n)]
    return agents, Network(agents, avg_degree=degree, assortment=assortment)


def _assert_symmetric_no_selfloop(net):
    for a, nbrs in net.contacts.items():
        assert a not in nbrs, "出現自環"
        for b in nbrs:
            assert a in net.contacts[b], "ties 不對稱"


def test_initial_graph_symmetric_no_selfloop():
    _, net = _build()
    _assert_symmetric_no_selfloop(net)


def test_draw_encounter_never_self_and_is_a_contact():
    _, net = _build()
    for _ in range(200):
        pair = net.draw_encounter()
        if pair is None:
            continue
        a, b = pair
        assert a is not b
        assert b in net.contacts[a]


def test_on_death_removes_agent_and_all_back_references():
    agents, net = _build()
    victim = agents[0]
    neighbors = list(net.contacts[victim])
    net.on_death(victim)
    assert victim not in net.contacts          # 自身節點移除
    assert victim not in net._nodes
    for nb in neighbors:
        assert victim not in net.contacts[nb]  # 反向 tie 也清掉(無 dangling)
    _assert_symmetric_no_selfloop(net)


def test_on_birth_adds_node_with_ties_and_stays_symmetric():
    agents, net = _build()
    newborn = AlwaysNotify()
    net.on_birth(newborn, degree=6)
    assert newborn in net._nodes
    assert newborn in net.contacts
    assert len(net.contacts[newborn]) > 0
    _assert_symmetric_no_selfloop(net)


def test_break_and_flee_severs_tie_and_rewires():
    agents, net = _build()
    # 找一條現存的邊
    a = next(x for x in agents if net.contacts[x])
    b = next(iter(net.contacts[a]))
    assert b in net.contacts[a]
    net.break_and_flee(a, b)
    assert b not in net.contacts[a]  # 原 tie 斷開
    assert a not in net.contacts[b]
    _assert_symmetric_no_selfloop(net)
