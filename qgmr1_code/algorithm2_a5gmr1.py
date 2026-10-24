"""
Algorithm 2: Quantum circuit of initialization and key generation phase
"""

from qiskit import QuantumCircuit

from algorithm1_a5gmr1 import (
    r1, r2, r3, r4, key, hs, y, ck, allregs,
    t1, t2, t3, t4,
    keylen, mixrounds, kslen,
    f, cf, c, unc, yt, kq, framebits,
)


# INITIALIZATION
def initialization(qc, fn):
    for i in framebits(fn):
        qc.x(kq(i))

    for i in range(keylen):
        f(qc, r1, t1)
        f(qc, r2, t2)
        f(qc, r3, t3)
        f(qc, r4, t4)
        qc.cx(kq(i), r1[0])
        qc.cx(kq(i), r2[0])
        qc.cx(kq(i), r3[0])
        qc.cx(kq(i), r4[0])

    for i, r in enumerate([r1, r2, r3, r4]):
        qc.cx(r[0], hs[i])
        qc.cx(hs[i], r[0])
        qc.x(r[0])

    for i in range(mixrounds):
        c(qc)
        cf(qc, r1, t1, ck[0])
        cf(qc, r2, t2, ck[1])
        cf(qc, r3, t3, ck[2])
        unc(qc)
        f(qc, r4, t4)


# KEY GENERATION
def keygeneration(qc):
    for i in range(kslen):
        c(qc)
        cf(qc, r1, t1, ck[0])
        cf(qc, r2, t2, ck[1])
        cf(qc, r3, t3, ck[2])
        yt(qc, y[i])
        unc(qc)
        f(qc, r4, t4)


def loadkey(qc, k):
    kbits = [(b >> (7 - p)) & 1 for b in k for p in range(8)]
    for i in range(keylen):
        if kbits[i]:
            qc.x(key[i])


if __name__ == "__main__":
    from qiskit_aer import AerSimulator

    K = bytes([0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF])
    FN = 42

    qc = QuantumCircuit(*allregs)
    loadkey(qc, K)
    initialization(qc, FN)
    keygeneration(qc)

    print("qubits", qc.num_qubits, "depth", qc.depth())
    print("gates", dict(qc.count_ops()))

    qc.measure_all()
    res = AerSimulator(method="matrix_product_state").run(qc, shots=1).result()
    bs = list(res.get_counts().keys())[0].replace(" ", "")[::-1]
    off = qc.find_bit(y[0]).index
    print("keystream", "".join(bs[off + i] for i in range(kslen)))