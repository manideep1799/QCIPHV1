"""
Algorithm 3: Quantum Circuit for A5-GMR-1 with relabelled shifts
"""

from qiskit import QuantumCircuit

from algorithm1_a5gmr1 import (
    r1, r2, r3, r4, key, mj, ck, me, ot, hs, y, allregs,
    keylen, mixrounds, kslen, framebits, kq,
)

R = [r1, r2, r3, r4]
L = [19, 22, 23, 17]
T = [[13, 16, 17], [12, 16, 20], [17, 18, 21], [8, 12, 13]]
P = [15, 6, 1]
M = [(1, 6, 15), (3, 8, 14), (4, 15, 19)]
X = [11, 1, 0]

off = [0, 0, 0, 0]


def reset():
    global off
    off = [0, 0, 0, 0]


def q(k, j):
    return R[k][(j - off[k]) % L[k]]


# QUANTUM CIRCUIT FOR f(R_t) -- unconditional update, shift is free
def f(qc, k):
    for i in T[k]:
        qc.cx(q(k, i), q(k, L[k] - 1))
    off[k] = (off[k] + 1) % L[k]


# QUANTUM CIRCUIT FOR cf(R_t, ctl) -- conditional update, offset frozen
def cf(qc, k, ctl):
    for i in T[k]:
        qc.ccx(q(k, i), ctl, q(k, L[k] - 1))
    for i in range(L[k] - 1, 0, -1):
        qc.cswap(ctl, R[k][i], R[k][i - 1])


# QUANTUM CIRCUIT FOR c(S_t)
def c(qc):
    qc.ccx(q(3, 15), q(3, 6), mj[0])
    qc.ccx(q(3, 15), q(3, 1), mj[0])
    qc.ccx(q(3, 6), q(3, 1), mj[0])
    for j in (0, 1, 2):
        qc.x(ck[j])
        qc.cx(q(3, P[j]), ck[j])
        qc.cx(mj[0], ck[j])


def unc(qc):
    for j in (2, 1, 0):
        qc.cx(mj[0], ck[j])
        qc.cx(q(3, P[j]), ck[j])
        qc.x(ck[j])
    qc.ccx(q(3, 6), q(3, 1), mj[0])
    qc.ccx(q(3, 15), q(3, 1), mj[0])
    qc.ccx(q(3, 15), q(3, 6), mj[0])


# QUANTUM CIRCUIT FOR y(t)
def yt(qc, trg):
    for j in (0, 1, 2):
        qc.ccx(q(j, M[j][0]), q(j, M[j][1]), me[j])
        qc.ccx(q(j, M[j][0]), q(j, M[j][2]), me[j])
        qc.ccx(q(j, M[j][1]), q(j, M[j][2]), me[j])
        qc.cx(q(j, X[j]), me[j])
    for j in (0, 1, 2):
        qc.cx(me[j], ot[0])
    qc.cx(ot[0], trg)
    for j in (2, 1, 0):
        qc.cx(me[j], ot[0])
    for j in (2, 1, 0):
        qc.cx(q(j, X[j]), me[j])
        qc.ccx(q(j, M[j][1]), q(j, M[j][2]), me[j])
        qc.ccx(q(j, M[j][0]), q(j, M[j][2]), me[j])
        qc.ccx(q(j, M[j][0]), q(j, M[j][1]), me[j])


# INITIALIZATION
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
            cf(qc, k, ck[k])
        unc(qc)
        f(qc, 3)


# KEY GENERATION
def keygeneration(qc):
    for i in range(kslen):
        c(qc)
        for k in (0, 1, 2):
            cf(qc, k, ck[k])
        yt(qc, y[i])
        unc(qc)
        f(qc, 3)


def loadkey(qc, k):
    kbits = [(b >> (7 - p)) & 1 for b in k for p in range(8)]
    for i in range(keylen):
        if kbits[i]:
            qc.x(key[i])


def build(k, fn):
    reset()
    qc = QuantumCircuit(*allregs)
    loadkey(qc, k)
    initialization(qc, fn)
    keygeneration(qc)
    return qc


if __name__ == "__main__":
    from qiskit_aer import AerSimulator

    K = bytes([0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF])
    FN = 42

    qc = build(K, FN)
    print("qubits", qc.num_qubits, "depth", qc.depth())
    print("gates", dict(qc.count_ops()))

    qc.measure_all()
    res = AerSimulator(method="matrix_product_state").run(qc, shots=1).result()
    bs = list(res.get_counts().keys())[0].replace(" ", "")[::-1]
    o = qc.find_bit(y[0]).index
    print("keystream", "".join(bs[o + i] for i in range(kslen)))
