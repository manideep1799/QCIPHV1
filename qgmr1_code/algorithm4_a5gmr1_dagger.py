"""
Algorithm 4: Quantum Circuit for A5-GMR-1 without internal uncomputation

Oracle-only variant, following the Atom-dagger observation of Anand, Nandi,
Isobe, "Analysis of Atom against quantum attacks", IET Quantum Communication
5(1):88-102, 2024, Sect. 4.2.

Inside a Grover oracle the cipher is run as ENC followed by ENC-dagger, so any
uncomputation performed *inside* ENC purely to recycle scratch qubits is
redundant -- the oracle's own uncomputation restores them. Dropping it costs
one fresh ancilla set per round instead of reusing one set.

Here that removes, per cycle, the clock-control uncomputation unc() and, in
keystream cycles, the output-block uncomputation inside y(t). The register
evolution is untouched, so the keystream is identical to Algorithm 3.

Not valid as a standalone cipher circuit -- only inside an oracle.
"""

from qiskit import QuantumCircuit, QuantumRegister

from algorithm1_a5gmr1 import (
    r1, r2, r3, r4, key, hs, y,
    keylen, mixrounds, kslen, framebits, kq,
)

R = [r1, r2, r3, r4]
L = [19, 22, 23, 17]
T = [[13, 16, 17], [12, 16, 20], [17, 18, 21], [8, 12, 13]]
P = [15, 6, 1]
M = [(1, 6, 15), (3, 8, 14), (4, 15, 19)]
X = [11, 1, 0]

CYCLES = mixrounds + kslen
ANC = QuantumRegister(4 * CYCLES + 4 * kslen, name='a')
allregs = (r1, r2, r3, r4, key, hs, y, ANC)

off = [0, 0, 0, 0]


def q(k, j):
    return R[k][(j - off[k]) % L[k]]


def f(qc, k):
    for i in T[k]:
        qc.cx(q(k, i), q(k, L[k] - 1))
    off[k] = (off[k] + 1) % L[k]


def cf(qc, k, ctl):
    for i in T[k]:
        qc.ccx(q(k, i), ctl, q(k, L[k] - 1))
    for i in range(L[k] - 1, 0, -1):
        qc.cswap(ctl, R[k][i], R[k][i - 1])


def c(qc, mj, ck):
    qc.ccx(q(3, 15), q(3, 6), mj)
    qc.ccx(q(3, 15), q(3, 1), mj)
    qc.ccx(q(3, 6), q(3, 1), mj)
    for j in (0, 1, 2):
        qc.x(ck[j])
        qc.cx(q(3, P[j]), ck[j])
        qc.cx(mj, ck[j])


def yt(qc, trg, me, ot):
    for j in (0, 1, 2):
        qc.ccx(q(j, M[j][0]), q(j, M[j][1]), me[j])
        qc.ccx(q(j, M[j][0]), q(j, M[j][2]), me[j])
        qc.ccx(q(j, M[j][1]), q(j, M[j][2]), me[j])
        qc.cx(q(j, X[j]), me[j])
    for j in (0, 1, 2):
        qc.cx(me[j], ot)
    qc.cx(ot, trg)
    # no uncomputation -- ENC-dagger handles it


def build(k_bytes, fn):
    global off
    off = [0, 0, 0, 0]
    qc = QuantumCircuit(*allregs)

    kbits = [(b >> (7 - p)) & 1 for b in k_bytes for p in range(8)]
    for i in range(keylen):
        if kbits[i]:
            qc.x(key[i])

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

    ap = 0
    yp = 4 * CYCLES
    for i in range(CYCLES):
        mj = ANC[ap]
        ck = [ANC[ap + 1], ANC[ap + 2], ANC[ap + 3]]
        ap += 4
        c(qc, mj, ck)
        for k in (0, 1, 2):
            cf(qc, k, ck[k])
        if i >= mixrounds:
            me = [ANC[yp], ANC[yp + 1], ANC[yp + 2]]
            ot = ANC[yp + 3]
            yp += 4
            yt(qc, y[i - mixrounds], me, ot)
        f(qc, 3)
    return qc


if __name__ == "__main__":
    K = bytes([0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF])
    FN = 42
    qc = build(K, FN)
    print("qubits", qc.num_qubits)
    print("gates", dict(qc.count_ops()))
