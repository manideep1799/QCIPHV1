"""
Algorithm 7: Quantum Circuit for A5-GMR-1 at the proven minimum Toffoli count
per controlled clock

Builds on Algorithms 5 and 6. Every building block below meets a proven lower
bound on its Toffoli count:

  (a) Conditional clock in L Toffolis, still shallow.  The three feedback
      taps are folded into one qubit with CNOTs, so one Toffoli applies
      top ^= ctl*(x_a ^ x_b ^ x_c); Algorithm 5's two-reversal shift adds L-1.
      L = rank(M XOR I), the minimum (report, Section 5).

  (b) Minimum-Toffoli barrel.  Every controlled M^(2^w), w >= 1, is emitted
      with exactly rank(M^(2^w) XOR I) = L Toffolis (gf2_transvect), with
      log-depth CNOT folds.

  (c) One product for all three clock bits.  With a = s0^s1, b = s0^s2:
          ck0 = 1^ab,   ck1 = 1^a^ab,   ck2 = 1^b^ab
      In the mixing rounds a and b are loaded by CNOTs from R4's state at the
      start of the block (R4 evolves linearly), so all of a block's clock-bit
      Toffolis act in parallel and R4 is never rewound.

  (d) Carry-save popcount in rounds.  n - H(n) Toffolis, the multiplicative
      complexity of the Hamming weight (Boyar-Peralta), at logarithmic depth.

  (e) Output bit written straight into y: three Toffolis, no ancillas.

  (f) Chunked batched mixing that cleans up after itself.  Record a block's
      clock bits, popcount them, apply the barrel, play the recording
      backwards, then advance R4. With clean=True every ancilla returns to |0>.

build() parameters
  block        mixing rounds per batch (1..250)
  clean        True: uncompute every ancilla.  False: oracle-only, one block
               of 250, clock bits and trees left for ENC-dagger
  shift        conditional clock form: "reversal" (fold + reversals, shallow)
               or "min" (transvections). Both use exactly L Toffolis.
  fresh_clock  keystream clock bits into fresh qubits, never erased
               (oracle-only; one Toffoli per keystream round instead of two)
"""

from qiskit import QuantumCircuit, QuantumRegister

import algorithm1_a5gmr1 as A1
import algorithm5_a5gmr1_par as A5
import gf2_transvect as GT
from algorithm1_a5gmr1 import keylen, mixrounds, kslen, framebits, kq
from algorithm6_a5gmr1_batch import step_phys
from gf2_synth import mat_from_step, mat_pow2

L, T, P = A5.L, A5.T, A5.P
M_OUT, X_OUT = A5.M, A5.X

# Pareto-best settings from the cost sweep. "min" shifts are omitted: with the
# taps folded they tie on Toffolis and lose on depth.
PRESETS = {
    "clean_narrow":     dict(block=1, clean=True, shift="reversal", fresh_clock=False),
    "clean_balanced":   dict(block=31, clean=True, shift="reversal", fresh_clock=False),
    "clean":            dict(block=250, clean=True, shift="reversal", fresh_clock=False),
    "oracle":           dict(block=250, clean=False, shift="reversal", fresh_clock=False),
    "oracle_fresh":     dict(block=250, clean=False, shift="reversal", fresh_clock=True),
}

AND_C = []        # Gidney AND computes paired with an erase
AND_E = []        # Gidney AND erases
AND_OPEN = []     # Gidney AND computes never erased (target blank at compute)

_MATS = {}


class Rec:
    """Gate recorder so a sub-sequence can be emitted forwards and backwards."""

    def __init__(self):
        self.ops = []

    def x(self, a):
        self.ops.append(("x", (a,), False))

    def cx(self, a, b):
        self.ops.append(("cx", (a, b), False))

    def ccx(self, a, b, c, is_and=False):
        self.ops.append(("ccx", (a, b, c), is_and))


def emit(qc, rec, forward, tag):
    """tag "pair": ANDs are computes forwards and erases backwards. "open": never erased."""
    for name, qs, is_and in (rec.ops if forward else reversed(rec.ops)):
        if is_and:
            if tag == "open":
                AND_OPEN.append(len(qc.data))
            elif forward:
                AND_C.append(len(qc.data))
            else:
                AND_E.append(len(qc.data))
        getattr(qc, name)(*qs)


def tree_plan_rounds(n):
    """Carry-save plan for summing n bits: the same full/half adders as
    gf2_synth.tree_plan (n - H(n) of them), but each column is reduced in
    rounds of disjoint triples, so the depth is logarithmic, not linear."""
    counter = [0]

    def new():
        counter[0] += 1
        return counter[0] - 1

    cols = {0: [("in", i) for i in range(n)]}
    ops, carries, out = [], 0, {}
    w = 0
    while True:
        col = cols.get(w, [])
        while len(col) >= 3:
            k3 = len(col) // 3
            nxt = []
            for i in range(k3):
                a, b, c = col[3 * i], col[3 * i + 1], col[3 * i + 2]
                car = ("anc", new())
                carries += 1
                ops.append(("fa", a, b, c, car, w))
                cols.setdefault(w + 1, []).append(car)
                nxt.append(c)
            col = nxt + col[3 * k3:]
        if len(col) == 2:
            a, b = col
            car = ("anc", new())
            carries += 1
            ops.append(("ha", a, b, car, w))
            cols.setdefault(w + 1, []).append(car)
            col = [b]
        out[w] = col[0] if col else None
        cols[w] = col
        w += 1
        if not cols.get(w):
            break
    return ops, carries, out


def popcount_rec(rec, bits, anc):
    """Carry-save sum of `bits` into a binary number; returns {weight: qubit}."""
    ops, _ncar, out = tree_plan_rounds(len(bits))

    def res(slot):
        kind, i = slot
        return bits[i] if kind == "in" else anc[i]

    for op in ops:
        if op[0] == "fa":
            _, sa, sb, sc, scar, _ = op
            a, b, c, car = res(sa), res(sb), res(sc), res(scar)
            rec.cx(a, b)
            rec.cx(a, c)
            rec.ccx(b, c, car, is_and=True)     # car := (a^b)(a^c)
            rec.cx(a, car)                      # car := MAJ(a,b,c)
            rec.cx(a, b)                        # restore b
            rec.cx(b, c)                        # c := a^b^c
        else:
            _, sa, sb, scar, _ = op
            a, b, car = res(sa), res(sb), res(scar)
            rec.ccx(a, b, car, is_and=True)     # car := ab
            rec.cx(a, b)                        # b := a^b
    return {w: (res(s) if s else None) for w, s in out.items()}


def r4_forms(nb):
    """For t = 0..nb-1, the linear forms (bitmask over R4's PHYSICAL qubits at the
    start of the block) of the three clock-control bits after t unconditional clocks."""
    n = L[3]
    state = [1 << i for i in range(n)]
    off = A5.off[3]
    forms = []
    for _t in range(nb):
        forms.append([state[(P[j] - off) % n] for j in range(3)])
        for i in T[3]:
            state[(n - 1 - off) % n] ^= state[(i - off) % n]
        off = (off + 1) % n
    return forms


def clock_bits_loaded(rec, c, s):
    """One mixing round's clock bits from linear forms s of R4 at block start:
    c1 := s0^s1 and c2 := s0^s2 by CNOTs, then ONE Toffoli, then fix-ups."""
    a_mask, b_mask = s[0] ^ s[1], s[0] ^ s[2]
    for i in range(L[3]):
        if (a_mask >> i) & 1:
            rec.cx(A5.R[3][i], c[1])
        if (b_mask >> i) & 1:
            rec.cx(A5.R[3][i], c[2])
    rec.ccx(c[1], c[2], c[0], is_and=True)      # c0 := ab
    rec.cx(c[0], c[1])                          # c1 := a ^ ab
    rec.cx(c[0], c[2])                          # c2 := b ^ ab
    rec.x(c[0])
    rec.x(c[1])
    rec.x(c[2])


def clock_bits_inplace(rec, c):
    """Keystream-round clock bits from R4's current bits: one Toffoli."""
    s0, s1, s2 = A5.q(3, P[0]), A5.q(3, P[1]), A5.q(3, P[2])
    rec.cx(s0, s1)                              # s1 := a = s0 ^ s1
    rec.cx(s0, s2)                              # s2 := b = s0 ^ s2
    rec.ccx(s1, s2, c[0], is_and=True)          # c0 := ab
    rec.cx(c[0], c[1])
    rec.cx(s1, c[1])                            # c1 := ab ^ a
    rec.cx(c[0], c[2])
    rec.cx(s2, c[2])                            # c2 := ab ^ b
    rec.x(c[0])
    rec.x(c[1])
    rec.x(c[2])
    rec.cx(s0, s2)
    rec.cx(s0, s1)


def cf_fold(qc, k, ctl, cps):
    """Conditional clock of register k in L Toffolis: the three feedback taps
    folded into one Toffoli, then Algorithm 5's two-reversal shift."""
    n = L[k]
    a, b, c = (A5.q(k, i) for i in T[k])
    top = A5.q(k, n - 1)
    qc.cx(b, a)
    qc.cx(c, a)                                 # a := x_a ^ x_b ^ x_c
    qc.ccx(ctl, a, top)                         # top ^= ctl * (x_a ^ x_b ^ x_c)
    qc.cx(c, a)
    qc.cx(b, a)
    use = cps[: n // 2]
    A5.fanout(qc, ctl, use)
    for i in range(n // 2):
        qc.cswap(use[i], A5.R[k][i], A5.R[k][n - 1 - i])
    for i in range((n - 1) // 2):
        qc.cswap(use[i], A5.R[k][1 + i], A5.R[k][n - 1 - i])
    A5.unfanout(qc, ctl, use)
    return n


def barrel_matrix(k, off, w):
    key = (k, off, w)
    if key not in _MATS:
        n = L[k]
        M = mat_from_step(lambda e: step_phys(e, k, off), n)
        _MATS[key] = mat_pow2(M, n, w)
    return _MATS[key]


def controlled_power(qc, k, off, w, ctl, shift):
    """Controlled M_k^(2^w): L Toffolis either way."""
    if w == 0 and shift == "reversal":
        return cf_fold(qc, k, ctl, A5.cps_for(k))
    return GT.controlled_linear(qc, barrel_matrix(k, off, w), A5.R[k], ctl, L[k])


def output_bit(qc, trg):
    """trg := XOR_j (MAJ_j ^ x_j), written directly; three Toffolis, no ancillas."""
    for j in (0, 1, 2):
        a = A5.q(j, M_OUT[j][0])
        b = A5.q(j, M_OUT[j][1])
        c = A5.q(j, M_OUT[j][2])
        qc.cx(a, b)
        qc.cx(a, c)
        if j == 0:
            AND_OPEN.append(len(qc.data))       # target still blank: a Gidney AND
        qc.ccx(b, c, trg)
        qc.cx(a, trg)
        qc.cx(a, c)
        qc.cx(a, b)
        qc.cx(A5.q(j, X_OUT[j]), trg)


def build(k_bytes, fn, block=15, clean=True, shift="reversal", fresh_clock=False,
          return_stats=False):
    global AND_C, AND_E, AND_OPEN
    assert shift in ("reversal", "min")
    assert clean or block >= mixrounds, "dirty mode cannot reuse block qubits"
    assert not (clean and fresh_clock), "fresh_clock leaves qubits dirty"
    A5.off = [0, 0, 0, 0]
    AND_C, AND_E, AND_OPEN = [], [], []

    nblk = min(block, mixrounds)
    _ops, ncar, _out = tree_plan_rounds(nblk)
    CK = QuantumRegister(3 * nblk, "ckb")
    TR = QuantumRegister(max(3 * ncar, 1), "tr")
    regs = [A1.r1, A1.r2, A1.r3, A1.r4, A1.key, A1.hs, A1.y]
    if shift == "reversal":
        regs.append(A5.fo)
    if fresh_clock:
        CKK = QuantumRegister(3 * kslen, "ckk")
        regs.append(CKK)
    else:
        regs.append(A1.ck)
    regs += [CK, TR]
    qc = QuantumCircuit(*regs)
    stats = {"clock": 0, "tree": 0, "barrel": 0, "keystream": 0}

    # ---- identical to Algorithms 5 and 6 --------------------------------
    A5.loadkey(qc, k_bytes)
    for i in framebits(fn):
        qc.x(kq(i))
    for i in range(keylen):
        for k in (0, 1, 2, 3):
            A5.f(qc, k)
        for k in (0, 1, 2, 3):
            qc.cx(kq(i), A5.q(k, 0))
    for k in (0, 1, 2, 3):
        qc.cx(A5.q(k, 0), A1.hs[k])
        qc.cx(A1.hs[k], A5.q(k, 0))
        qc.x(A5.q(k, 0))

    # ---- batched mixing ---------------------------------------------------
    off0 = list(A5.off)
    t = 0
    while t < mixrounds:
        nb = min(nblk, mixrounds - t)
        rec = Rec()
        for i, s in enumerate(r4_forms(nb)):
            clock_bits_loaded(rec, [CK[0 * nblk + i], CK[1 * nblk + i], CK[2 * nblk + i]], s)
        n_clock = sum(1 for op in rec.ops if op[0] == "ccx")
        outs = []
        for k in (0, 1, 2):
            bits = [CK[k * nblk + i] for i in range(nb)]
            outs.append(popcount_rec(rec, bits, [TR[k * ncar + i] for i in range(ncar)]))
        n_tree = sum(1 for op in rec.ops if op[0] == "ccx") - n_clock
        emit(qc, rec, True, "pair" if clean else "open")
        for k in (0, 1, 2):
            for w, ctl in sorted(outs[k].items()):
                if ctl is not None:
                    stats["barrel"] += controlled_power(qc, k, off0[k], w, ctl, shift)
        if clean:
            emit(qc, rec, False, "pair")
        for _i in range(nb):
            A5.f(qc, 3)
        mult = 2 if clean else 1
        stats["clock"] += mult * n_clock
        stats["tree"] += mult * n_tree
        t += nb
    assert A5.off[:3] == off0[:3]

    # ---- keystream ----------------------------------------------------------
    before = len(qc.data)
    for i in range(kslen):
        ck3 = [CKK[3 * i + j] for j in range(3)] if fresh_clock else [A1.ck[0], A1.ck[1], A1.ck[2]]
        rc = Rec()
        clock_bits_inplace(rc, ck3)
        emit(qc, rc, True, "open" if fresh_clock else "pair")
        for k in (0, 1, 2):
            controlled_power(qc, k, off0[k], 0, ck3[k], shift)
        output_bit(qc, A1.y[i])
        if not fresh_clock:
            emit(qc, rc, False, "pair")
        A5.f(qc, 3)
    stats["keystream"] = sum(1 for ins in qc.data[before:]
                             if ins.operation.name in ("ccx", "cswap"))
    stats["width"] = qc.num_qubits

    if return_stats:
        return qc, stats
    return qc


def build_preset(name, k_bytes, fn, return_stats=False):
    return build(k_bytes, fn, return_stats=return_stats, **PRESETS[name])
