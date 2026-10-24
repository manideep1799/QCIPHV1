"""
Algorithm 6: Quantum Circuit for A5-GMR-1 with batched mixing

During the 250 mixing rounds, R1/R2/R3 are touched ONLY by their own cf() --
y(t) is not called, so no intermediate state of those registers is ever read.
Each is therefore a self-contained conditionally-clocked LFSR, and all 250 of
its steps are powers of the same matrix M_k, so they COMMUTE: the result
depends only on HOW MANY times it was clocked, not on when.

    250 conditional clocks of R_k  ==  M_k ^ (number of set clock bits)

So instead of 250 conditional shifts we:
  1. run R4 forward 250 steps (unconditional, deterministic) and record each
     clock bit c_k(t) in its own qubit,
  2. add the 250 bits up with a carry-save tree into an 8-bit number n_k,
  3. apply M_k^n_k with a barrel of controlled-M_k^(2^j), j = 0..7.

250 conditional shifts collapse to 8 controlled linear maps.

Like Algorithm 4 this is an ORACLE-ONLY circuit: the clock bits and the tree's
carry ancillas are left dirty, to be cleared by ENC-dagger. The keystream is
identical to Algorithms 3 and 5.
"""

from qiskit import QuantumCircuit, QuantumRegister

import algorithm5_a5gmr1_par as A5
from algorithm1_a5gmr1 import keylen, mixrounds, kslen, framebits, kq
from gf2_synth import mat_from_step, mat_pow2, synth_cnots, verify_synth, tree_plan

L, T, P = A5.L, A5.T, A5.P

CK = QuantumRegister(3 * mixrounds, name='ckb')
_, NCAR, _ = tree_plan(mixrounds)
TR = QuantumRegister(3 * NCAR, name='tr')
allregs = A5.allregs + (CK, TR)

AND_OPEN = []        # Gidney AND computes into a blank target, never uncomputed


def step_phys(bits, k, off):
    """One clock of register k in PHYSICAL qubit coordinates, exactly as
    A5.cf() performs it: taps XOR into the top logical bit, then the two
    reversals rotate the physical array right by one."""
    n = L[k]
    def qi(j):
        return (j - off) % n
    b = list(bits)
    for i in T[k]:
        b[qi(n - 1)] ^= b[qi(i)]
    return [b[-1]] + b[:-1]


def maj_open(qc, a, b, c, trg):
    """trg ^= MAJ(a,b,c), one Toffoli, target blank and never uncomputed."""
    qc.cx(a, b)
    qc.cx(a, c)
    AND_OPEN.append(len(qc.data))
    qc.ccx(b, c, trg)
    qc.cx(a, trg)
    qc.cx(a, c)
    qc.cx(a, b)


def popcount(qc, bits, anc, base):
    """Carry-save sum of `bits` into a binary number. Returns {weight: qubit}.
    Consumed inputs and carry ancillas are left dirty."""
    ops, ncar, out = tree_plan(len(bits))

    def res(slot):
        kind, i = slot
        return bits[i] if kind == "in" else anc[base + i]

    for op in ops:
        if op[0] == "fa":
            _, sa, sb, sc, scar, _ = op
            qa, qb, qcc, qcar = res(sa), res(sb), res(sc), res(scar)
            maj_open(qc, qa, qb, qcc, qcar)        # carry = MAJ(a,b,c)
            qc.cx(qa, qcc)
            qc.cx(qb, qcc)                          # sum  = a^b^c, in place
        else:
            _, sa, sb, scar, _ = op
            qa, qb, qcar = res(sa), res(sb), res(scar)
            AND_OPEN.append(len(qc.data))
            qc.ccx(qa, qb, qcar)                    # carry = a AND b
            qc.cx(qa, qb)                           # sum   = a^b, in place
    return {w: (res(s) if s else None) for w, s in out.items()}


def controlled_matrix(qc, A, reg, ctl, n):
    """Apply reg -> A reg when ctl = 1. Every CNOT of the linear circuit
    becomes a Toffoli."""
    ops = synth_cnots(A, n)
    assert verify_synth(A, ops, n)
    for c, t in ops:
        qc.ccx(ctl, reg[c], reg[t])
    return len(ops)


def build(k_bytes, fn, return_stats=False):
    A5.off = [0, 0, 0, 0]
    A5.AND_IDX = []
    A5.AND_C = []
    A5.AND_E = []
    global AND_OPEN
    AND_OPEN = []
    qc = QuantumCircuit(*allregs)

    # ---- identical to Algorithm 5 -------------------------------------
    A5.loadkey(qc, k_bytes)
    for i in framebits(fn):
        qc.x(kq(i))
    for i in range(keylen):
        for k in (0, 1, 2, 3):
            A5.f(qc, k)
        for k in (0, 1, 2, 3):
            qc.cx(kq(i), A5.q(k, 0))
    for k in (0, 1, 2, 3):
        qc.cx(A5.q(k, 0), A5.hs[k])
        qc.cx(A5.hs[k], A5.q(k, 0))
        qc.x(A5.q(k, 0))

    # ---- batched mixing ------------------------------------------------
    off0 = list(A5.off)                       # frozen for k = 0,1,2 during mixing
    for t in range(mixrounds):
        A5.maj(qc, A5.q(3, 15), A5.q(3, 6), A5.q(3, 1), A5.mj[0])
        for j in (0, 1, 2):
            b = CK[j * mixrounds + t]
            qc.x(b)
            qc.cx(A5.q(3, P[j]), b)
            qc.cx(A5.mj[0], b)
        A5.unmaj(qc, A5.q(3, 15), A5.q(3, 6), A5.q(3, 1), A5.mj[0])
        A5.f(qc, 3)

    barrel = 0
    for k in (0, 1, 2):
        n = L[k]
        bits = [CK[k * mixrounds + t] for t in range(mixrounds)]
        nb = popcount(qc, bits, TR, k * NCAR)
        M = mat_from_step(lambda e, k=k: step_phys(e, k, off0[k]), n)
        for w, ctl in sorted(nb.items()):
            if ctl is None:
                continue
            barrel += controlled_matrix(qc, mat_pow2(M, n, w), A5.R[k], ctl, n)

    # ---- identical to Algorithm 5 -------------------------------------
    A5.keygeneration(qc)

    if return_stats:
        return qc, {"barrel_toffoli": barrel, "tree_carries": NCAR}
    return qc
