"""
Minimum-Toffoli controlled linear maps over GF(2).

Any circuit of NOT/CNOT/Toffoli gates that applies an invertible linear map A
under a control needs at least rank(A XOR I) Toffolis (report, Section 5).
This module meets that bound EXACTLY, for every invertible A.

1.  Transvection decomposition.  While A != I: pick x with A x != x, let
    y = (A XOR I) x, and choose a row vector w with
        w.(A x) = 1,   w.y = 0,   w.z = 0 for every z in ker(A XOR I).
    Such a w always exists, because A x lies outside span(y, ker(A XOR I)).
    t = I XOR y w^T is then a transvection (w.y = 0); t A fixes x and every
    vector A already fixed, so rank((t A) XOR I) = rank(A XOR I) - 1.
    After r = rank(A XOR I) steps, t_r ... t_1 A = I, so A = t_1 t_2 ... t_r
    (a transvection is its own inverse).

2.  One Toffoli per controlled transvection.  To apply x -> x XOR ctl*(w.x)*y:
    apply a CNOT fold G that leaves w.x in one coordinate s; in the folded
    basis the update is u' = G y, with u'_s = w.y = 0, so the fold qubit is
    untouched. Spread the single product along u' with a CNOT fan-out
    sandwich (F^-1, Toffoli, F) and unfold. With log_depth=True the fold and
    the fan-out are balanced trees, so the CNOT depth is O(log L), not O(L).

Nothing is trusted: every decomposition is multiplied back out, and every gate
list is simulated on all basis vectors for ctl = 0 and ctl = 1, before use.
"""

import random

_CACHE = {}


def _pc(v):
    return bin(v).count("1")


def _par(v):
    return _pc(v) & 1


def apply_matrix(A, x):
    """y = A x. A[i] is the bitmask of the inputs feeding output i."""
    y = 0
    for i, row in enumerate(A):
        if _par(row & x):
            y |= 1 << i
    return y


def rank_rows(rows, n):
    R = list(rows)
    r = 0
    for c in range(n):
        p = next((i for i in range(r, len(R)) if (R[i] >> c) & 1), None)
        if p is None:
            continue
        R[r], R[p] = R[p], R[r]
        for i in range(len(R)):
            if i != r and (R[i] >> c) & 1:
                R[i] ^= R[r]
        r += 1
    return r


def rank_minus_identity(A, n):
    """rank(A XOR I): the proven minimum Toffoli count of controlled-A."""
    return rank_rows([A[i] ^ (1 << i) for i in range(n)], n)


def _solve(cons, n):
    """All w with parity(w & c) == b for each (c, b), as (particular, null basis),
    or None if inconsistent."""
    R = [c | (b << n) for c, b in cons]
    piv, r = [], 0
    for col in range(n):
        p = next((i for i in range(r, len(R)) if (R[i] >> col) & 1), None)
        if p is None:
            continue
        R[r], R[p] = R[p], R[r]
        for i in range(len(R)):
            if i != r and (R[i] >> col) & 1:
                R[i] ^= R[r]
        piv.append(col)
        r += 1
    mask = (1 << n) - 1
    if any((row & mask) == 0 and (row >> n) & 1 for row in R[r:]):
        return None
    part = 0
    for row, pc in zip(R[:r], piv):
        if (row >> n) & 1:
            part |= 1 << pc
    null = []
    for f in (c for c in range(n) if c not in piv):
        v = 1 << f
        for row, pc in zip(R[:r], piv):
            if (row >> f) & 1:
                v |= 1 << pc
        null.append(v)
    return part, null


def _lightest(part, null, rng, budget=256):
    """A low-weight member of part + span(null) (exhaustive when small)."""
    best = part
    if len(null) <= 8:
        for m in range(1, 1 << len(null)):
            v = part
            for i, z in enumerate(null):
                if (m >> i) & 1:
                    v ^= z
            if _pc(v) < _pc(best):
                best = v
        return best
    for _ in range(budget):
        v = part
        for z in null:
            if rng.random() < 0.5:
                v ^= z
        if _pc(v) < _pc(best):
            best = v
    return best


def transvections(A, n, seed=0):
    """[(y, w), ...] with A = t_1 t_2 ... t_r, t_i = I XOR y_i w_i^T, w_i.y_i = 0,
    and r = rank(A XOR I) exactly. Deterministic for a given seed."""
    key = (tuple(A), n, seed)
    if key in _CACHE:
        return list(_CACHE[key])
    rng = random.Random(seed)
    A0, A = list(A), list(A)
    r = rank_minus_identity(A, n)
    target = r
    out = []
    while r:
        D = [A[i] ^ (1 << i) for i in range(n)]
        ker = _solve([(row, 0) for row in D], n)[1]
        best = None
        for x in [1 << i for i in range(n)] + [rng.getrandbits(n) for _ in range(8)]:
            y = apply_matrix(D, x)
            if y == 0:
                continue
            sol = _solve([(apply_matrix(A, x), 1), (y, 0)] + [(z, 0) for z in ker], n)
            assert sol is not None, "no admissible w: construction invariant violated"
            w = _lightest(sol[0], sol[1], rng)
            cost = _pc(w) + _pc(y)
            if best is None or cost < best[0]:
                best = (cost, y, w)
        _, y, w = best
        assert _par(w & y) == 0
        wA = 0
        for j in range(n):
            if (w >> j) & 1:
                wA ^= A[j]
        A = [A[i] ^ (wA if (y >> i) & 1 else 0) for i in range(n)]
        r_next = rank_minus_identity(A, n)
        assert r_next == r - 1, "rank did not drop by exactly one"
        r = r_next
        out.append((y, w))
    assert all(A[i] == (1 << i) for i in range(n)) and len(out) == target
    for j in range(n):
        x = 1 << j
        for y, w in reversed(out):
            if _par(w & x):
                x ^= y
        assert x == apply_matrix(A0, 1 << j), "decomposition does not reproduce A"
    _CACHE[key] = list(out)
    return list(out)


def _fold_tree(nodes):
    """CNOTs leaving the parity of `nodes` in nodes[0], in ceil(log2) rounds."""
    ops, cur = [], list(nodes)
    while len(cur) > 1:
        nxt = []
        for i in range(0, len(cur) - 1, 2):
            ops.append((cur[i + 1], cur[i]))
            nxt.append(cur[i])
        if len(cur) % 2:
            nxt.append(cur[-1])
        cur = nxt
    return ops


def _fanout_tree(root, targets):
    """CNOTs copying `root` into every target, holders doubling each round."""
    ops, holders, rest = [], [root], list(targets)
    while rest:
        new = []
        for h in holders:
            if not rest:
                break
            g = rest.pop(0)
            ops.append((h, g))
            new.append(g)
        holders += new
    return ops


def controlled_ops(ts, n, log_depth=True):
    """Gate list for controlled-(t_1 ... t_r), in application order.
    ('cx', c, t) is CNOT(reg[c] -> reg[t]); ('ccx', s, t) is Toffoli(ctl, reg[s], reg[t]).
    Contains exactly len(ts) Toffolis."""
    ops = []
    for y, w in reversed(ts):
        sw = [i for i in range(n) if (w >> i) & 1]
        best = None
        for s in sw:
            nodes = [s] + [i for i in sw if i != s]
            fold = _fold_tree(nodes) if log_depth else [(i, s) for i in nodes[1:]]
            u = y
            for c, g in fold:                       # u' = G y
                if (u >> c) & 1:
                    u ^= 1 << g
            if best is None or _pc(u) < _pc(best[2]):
                best = (s, fold, u)
        s, fold, u = best
        assert not (u >> s) & 1 and u
        su = [i for i in range(n) if (u >> i) & 1]
        t = su[0]
        others = su[1:]
        spread = _fanout_tree(t, others) if log_depth else [(t, i) for i in others]
        ops += [("cx", c, g) for c, g in fold]
        ops += [("cx", c, g) for c, g in reversed(spread)]
        ops += [("ccx", s, t)]
        ops += [("cx", c, g) for c, g in spread]
        ops += [("cx", c, g) for c, g in reversed(fold)]
    return ops


def simulate_ops(ops, x, ctl):
    for op in ops:
        if op[0] == "cx":
            if (x >> op[1]) & 1:
                x ^= 1 << op[2]
        elif ctl and (x >> op[1]) & 1:
            x ^= 1 << op[2]
    return x


def controlled_linear(qc, A, reg, ctl, n, seed=0, log_depth=True):
    """Emit controlled-A onto qc with exactly rank(A XOR I) Toffolis, after
    checking the gate list on every basis vector for both control values.
    Returns the number of Toffolis emitted."""
    ts = transvections(A, n, seed)
    ops = controlled_ops(ts, n, log_depth)
    for j in range(n):
        e = 1 << j
        assert simulate_ops(ops, e, 0) == e, "ctl=0 is not the identity"
        assert simulate_ops(ops, e, 1) == apply_matrix(A, e), "ctl=1 is not A"
    for op in ops:
        if op[0] == "cx":
            qc.cx(reg[op[1]], reg[op[2]])
        else:
            qc.ccx(ctl, reg[op[1]], reg[op[2]])
    return len(ts)
