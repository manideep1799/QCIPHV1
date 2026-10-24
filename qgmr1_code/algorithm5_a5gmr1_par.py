"""
Algorithm 5: Quantum Circuit for A5-GMR-1 with parallel conditional shift

Two changes on top of Algorithm 3, both leaving the keystream identical.

(a) The conditional cyclic shift cf() is the cost centre: 76% of all Toffoli
    gates and ~74% of the full depth. Its L-1 Fredkins form a *sequential*
    chain -- cswap(ctl, r_i, r_{i-1}) and cswap(ctl, r_{i-1}, r_{i-2}) share
    r_{i-1}, and all of them share ctl -- so the cascade costs depth L-1.

    A right-rotation by one is rewritten with the three-reversal identity
        rot(1) = rev(0..L-1) then rev(1..L-1)
    Each reversal is a set of *disjoint* transpositions, so it is one layer.
    The two reversals use floor(L/2) + floor((L-1)/2) = L-1 Fredkins, i.e.
    EXACTLY the same count as the cascade -- the T-count is unchanged, only
    the shape.  ctl is fanned out over a CNOT tree into floor(L/2) copies so
    the shared-control serialisation goes too.  Depth per shift: L-1 -> 2.

(b) MAJ(a,b,c) = a XOR ((a XOR b) AND (a XOR c)) needs one Toffoli, not three.
    Applied to the clock-control majority and to the three output majorities.
"""

from qiskit import QuantumCircuit, QuantumRegister

from algorithm1_a5gmr1 import (
    r1, r2, r3, r4, key, mj, ck, me, ot, hs, y,
    keylen, mixrounds, kslen, framebits, kq,
)

R = [r1, r2, r3, r4]
L = [19, 22, 23, 17]
T = [[13, 16, 17], [12, 16, 20], [17, 18, 21], [8, 12, 13]]
P = [15, 6, 1]
M = [(1, 6, 15), (3, 8, 14), (4, 15, 19)]
X = [11, 1, 0]

FAN = [L[k] // 2 for k in range(3)]    # control copies each register's reversals use
FOFF = [sum(FAN[:k]) for k in range(3)]
fo = QuantumRegister(sum(FAN), name='fo')
allregs = (r1, r2, r3, r4, key, mj, ck, me, ot, hs, y, fo)

off = [0, 0, 0, 0]


def q(k, j):
    return R[k][(j - off[k]) % L[k]]


def fanout(qc, ctl, cps):
    """Copy ctl into cps[0..m-1] with a CNOT tree -- depth ceil(log2(m+1))."""
    src = [ctl]
    i = 0
    while i < len(cps):
        nxt = []
        for s in src:
            if i >= len(cps):
                break
            qc.cx(s, cps[i])
            nxt.append(cps[i])
            i += 1
        src = src + nxt


def unfanout(qc, ctl, cps):
    ops = []
    src = [ctl]
    i = 0
    while i < len(cps):
        nxt = []
        for s in src:
            if i >= len(cps):
                break
            ops.append((s, cps[i]))
            nxt.append(cps[i])
            i += 1
        src = src + nxt
    for s, t in reversed(ops):
        qc.cx(s, t)


AND_IDX = []          # all tagged Toffolis (compute + erase), for the pairing checker
AND_C = []            # Gidney AND computes   (4 T each)
AND_E = []            # Gidney AND erases     (0 T each, measurement based)


def maj(qc, a, b, c, trg):
    """trg ^= MAJ(a,b,c) with a single Toffoli.

    trg must be |0> here, so the Toffoli writes AND(a^b, a^c) into a blank
    qubit -- i.e. it is a legitimate Gidney AND.
    """
    qc.cx(a, b)
    qc.cx(a, c)
    AND_IDX.append(len(qc.data))
    AND_C.append(len(qc.data))
    qc.ccx(b, c, trg)
    qc.cx(a, trg)
    qc.cx(a, c)
    qc.cx(a, b)


def unmaj(qc, a, b, c, trg):
    """Inverse of maj(). Same XOR value, but cx(a,trg) is moved BEFORE the
    Toffoli, so at the instant the Toffoli fires trg holds exactly
    AND(a^b, a^c) -- the precondition for a Gidney AND-dagger (0 T gates).
    The symmetric ordering used by maj() would leave trg = AND ^ a and is
    NOT a valid AND-dagger.
    """
    qc.cx(a, b)
    qc.cx(a, c)
    qc.cx(a, trg)
    AND_IDX.append(len(qc.data))
    AND_E.append(len(qc.data))
    qc.ccx(b, c, trg)
    qc.cx(a, c)
    qc.cx(a, b)


def f(qc, k):
    for i in T[k]:
        qc.cx(q(k, i), q(k, L[k] - 1))
    off[k] = (off[k] + 1) % L[k]


def cf(qc, k, ctl, cps):
    """Conditional update: feedback taps, then a depth-2 conditional rotation."""
    for i in T[k]:
        qc.ccx(q(k, i), ctl, q(k, L[k] - 1))

    n = L[k]
    fanout(qc, ctl, cps)
    # layer 1: reverse the whole register
    for i in range(n // 2):
        qc.cswap(cps[i], R[k][i], R[k][n - 1 - i])
    # layer 2: reverse everything but position 0
    for i in range((n - 1) // 2):
        qc.cswap(cps[i], R[k][1 + i], R[k][n - 1 - i])
    unfanout(qc, ctl, cps)


def c(qc):
    maj(qc, q(3, 15), q(3, 6), q(3, 1), mj[0])
    for j in (0, 1, 2):
        qc.x(ck[j])
        qc.cx(q(3, P[j]), ck[j])
        qc.cx(mj[0], ck[j])


def unc(qc):
    for j in (2, 1, 0):
        qc.cx(mj[0], ck[j])
        qc.cx(q(3, P[j]), ck[j])
        qc.x(ck[j])
    unmaj(qc, q(3, 15), q(3, 6), q(3, 1), mj[0])


def yt(qc, trg):
    for j in (0, 1, 2):
        maj(qc, q(j, M[j][0]), q(j, M[j][1]), q(j, M[j][2]), me[j])
        qc.cx(q(j, X[j]), me[j])
    for j in (0, 1, 2):
        qc.cx(me[j], ot[0])
    qc.cx(ot[0], trg)
    for j in (2, 1, 0):
        qc.cx(me[j], ot[0])
    for j in (2, 1, 0):
        qc.cx(q(j, X[j]), me[j])
        unmaj(qc, q(j, M[j][0]), q(j, M[j][1]), q(j, M[j][2]), me[j])


def cps_for(k):
    return [fo[FOFF[k] + i] for i in range(FAN[k])]


def initialization(qc, fn):
    for i in framebits(fn):
        qc.x(kq(i))
    for i in range(keylen):
        for k in (0, 1, 2, 3):
            f(qc, k)
        for k in (0, 1, 2, 3):
            qc.cx(kq(i), q(k, 0))
    for k in (0, 1, 2, 3):
        qc.cx(q(k, 0), hs[k])
        qc.cx(hs[k], q(k, 0))
        qc.x(q(k, 0))
    for i in range(mixrounds):
        c(qc)
        for k in (0, 1, 2):
            cf(qc, k, ck[k], cps_for(k))
        unc(qc)
        f(qc, 3)


def keygeneration(qc):
    for i in range(kslen):
        c(qc)
        for k in (0, 1, 2):
            cf(qc, k, ck[k], cps_for(k))
        yt(qc, y[i])
        unc(qc)
        f(qc, 3)


def loadkey(qc, k):
    kbits = [(b >> (7 - p)) & 1 for b in k for p in range(8)]
    for i in range(keylen):
        if kbits[i]:
            qc.x(key[i])


def build(k, fn):
    global off, AND_IDX, AND_C, AND_E
    off = [0, 0, 0, 0]
    AND_IDX = []
    AND_C = []
    AND_E = []
    qc = QuantumCircuit(*allregs)
    loadkey(qc, k)
    initialization(qc, fn)
    keygeneration(qc)
    return qc
