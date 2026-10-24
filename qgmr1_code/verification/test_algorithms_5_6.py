"""
verification/test_algorithms_5_6.py
==================================================

Verifies Algorithm 5 (parallel conditional shift) and Algorithm 6 (batched
mixing) against Algorithm 3 AND against the classical reference implementation.

Every gate here maps a computational basis state to a basis state, so the
circuits are walked with an exact bit-level simulator rather than Aer -- same
result, no simulator dependency, and it lets us inspect the state BETWEEN
gates, which is what the Gidney-AND precondition check needs.

Tests
  1  three-reversal shift == Fredkin chain              (exhaustive, L=19,22,23)
  2  fan-out tree restores control copies to |0>        (all copy counts 1..12)
  3  Alg.5 keystream == Alg.3, scratch left clean
  4  Gidney AND/AND-dagger preconditions at all 546 pairs
  5  step_phys == what A5.cf actually does to the qubits (exhaustive)
  6  250 conditional clocks == M^popcount               (random trials)
  7  Alg.6 keystream == Alg.3
  8  Alg.5 and Alg.6 == the CLASSICAL reference         (random key/frame)
  9  barrel == repeated clocking for EVERY count 0..255 (not just typical n)
 10  carry-save popcount exact                          (exhaustive to 10 bits)
 11  inside the real Alg.6 build: tree outputs, AND tags (one sim per key)
 12  cost accounting partitions every Toffoli exactly once

Run a subset with:  python test_algorithms_5_6.py 9 10 11
"""

import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "classical_ref"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "classical_ref", "a5_gmr1"))

from qiskit import QuantumCircuit, QuantumRegister

import algorithm1_a5gmr1 as A1
import algorithm3_a5gmr1_opt as A3
import algorithm5_a5gmr1_par as A5
import algorithm6_a5gmr1_batch as A6
from gf2_synth import mat_from_step, mat_apply, mat_mul, mat_pow2, tree_plan
from a5_gmr1.cipher import A5GMR1

FAILURES = []


def check(name, ok, detail=""):
    tag = "PASS" if ok else "FAIL"
    print("  " + tag + "  " + name + ("   " + detail if detail else ""))
    if not ok:
        FAILURES.append(name)


def compile_circuit(qc):
    """Flatten a circuit to (gate name, [qubit index]) once, for repeated runs."""
    idx = {b: i for i, b in enumerate(qc.qubits)}
    return [(ins.operation.name, [idx[b] for b in ins.qubits]) for ins in qc.data]


def apply_gate(st, n, q):
    if n == "x":
        st[q[0]] ^= 1
    elif n == "cx":
        st[q[1]] ^= st[q[0]]
    elif n == "ccx":
        st[q[2]] ^= st[q[0]] & st[q[1]]
    elif n == "swap":
        st[q[0]], st[q[1]] = st[q[1]], st[q[0]]
    elif n == "cswap":
        if st[q[0]]:
            st[q[1]], st[q[2]] = st[q[2]], st[q[1]]
    else:
        raise ValueError("unexpected gate " + n)


def sim(gates, st):
    for n, q in gates:
        apply_gate(st, n, q)
    return st


def run(qc, init=None):
    """Exact bit-level simulation of a basis-state circuit."""
    st = list(init) if init is not None else [0] * qc.num_qubits
    return sim(compile_circuit(qc), st)


def keystream(qc):
    st = run(qc)
    o = qc.find_bit(A1.y[0]).index
    return "".join(str(st[o + i]) for i in range(A1.kslen))


# --- 1 ----------------------------------------------------------------------
def t1_reversal_equals_chain():
    ok = True
    for L in (19, 22, 23):
        for j in range(L):
            e = [1 if i == j else 0 for i in range(L)]
            chain = list(e)
            for i in range(L - 1, 0, -1):
                chain[i], chain[i - 1] = chain[i - 1], chain[i]
            rev = list(e)
            for i in range(L // 2):
                rev[i], rev[L - 1 - i] = rev[L - 1 - i], rev[i]
            for i in range((L - 1) // 2):
                rev[1 + i], rev[L - 1 - i] = rev[L - 1 - i], rev[1 + i]
            ok = ok and chain == rev
    check("three-reversal shift == Fredkin chain (L=19,22,23, all basis states)", ok)


# --- 2 ----------------------------------------------------------------------
def t2_fanout_clean():
    ok = True
    for m in range(1, 13):
        for ctlval in (0, 1):
            ctl = QuantumRegister(1, "c")
            cps = QuantumRegister(m, "p")
            qc = QuantumCircuit(ctl, cps)
            if ctlval:
                qc.x(ctl[0])
            A5.fanout(qc, ctl[0], list(cps))
            mid = run(qc)
            if any(mid[1 + i] != ctlval for i in range(m)):
                ok = False
            A5.unfanout(qc, ctl[0], list(cps))
            end = run(qc)
            if any(end[1 + i] != 0 for i in range(m)) or end[0] != ctlval:
                ok = False
    check("fan-out copies control then restores copies to |0> (m=1..12)", ok)


# --- 3 ----------------------------------------------------------------------
def t3_alg5_matches_alg3(pairs):
    ok = True
    for K, FN in pairs:
        q3, q5 = A3.build(K, FN), A5.build(K, FN)
        s5 = run(q5)
        dirty = [x for reg in (A1.mj, A1.ck, A1.me, A1.ot, A5.fo) for x in reg
                 if s5[q5.find_bit(x).index]]
        ok = ok and keystream(q3) == keystream(q5) and not dirty
    check("Alg.5 keystream == Alg.3 and scratch clean (%d pairs)" % len(pairs), ok)


# --- 4 ----------------------------------------------------------------------
def t4_gidney_preconditions(pairs):
    ok = True
    npairs = 0
    for K, FN in pairs:
        qc = A5.build(K, FN)
        comp, era = set(A5.AND_C), set(A5.AND_E)
        npairs = len(comp)
        idx = {b: i for i, b in enumerate(qc.qubits)}
        st = [0] * qc.num_qubits
        live = {}
        for gi, ins in enumerate(qc.data):
            n = ins.operation.name
            q = [idx[b] for b in ins.qubits]
            if gi in comp:
                if st[q[2]] != 0:
                    ok = False                       # target must be |0>
                live[q[2]] = (q[0], q[1], st[q[0]], st[q[1]])
            elif gi in era:
                c0, c1, v0, v1 = live.pop(q[2], (None, None, None, None))
                if (c0, c1) != (q[0], q[1]):
                    ok = False                       # different control qubits
                if (v0, v1) != (st[q[0]], st[q[1]]):
                    ok = False                       # control VALUES changed
                if st[q[2]] != (st[q[0]] & st[q[1]]):
                    ok = False                       # target must hold the AND
            if n == "x":
                st[q[0]] ^= 1
            elif n == "cx":
                st[q[1]] ^= st[q[0]]
            elif n == "ccx":
                st[q[2]] ^= st[q[0]] & st[q[1]]
            elif n == "cswap":
                if st[q[0]]:
                    st[q[1]], st[q[2]] = st[q[2]], st[q[1]]
            elif n == "swap":
                st[q[0]], st[q[1]] = st[q[1]], st[q[0]]
            if gi in era and st[q[2]] != 0:
                ok = False                           # target must end |0>
        ok = ok and not live and len(comp) == len(era)
    check("Gidney AND/AND-dagger preconditions hold at all %d pairs" % npairs, ok)


# --- 5 ----------------------------------------------------------------------
def t5_step_phys_matches_cf():
    ok = True
    for k in (0, 1, 2):
        n = A5.L[k]
        for off in range(n):
            for j in range(n):
                A5.off = [0, 0, 0, 0]
                A5.off[k] = off
                ctl = QuantumRegister(1, "c")
                cps = QuantumRegister(n // 2, "p")
                qc = QuantumCircuit(A5.R[k], ctl, cps)
                qc.x(ctl[0])
                qc.x(A5.R[k][j])
                A5.cf(qc, k, ctl[0], [cps[i] for i in range(n // 2)])
                e = [1 if i == j else 0 for i in range(n)]
                ok = ok and run(qc)[:n] == A6.step_phys(e, k, off)
    check("step_phys == the real A5.cf circuit (all offsets x basis states)", ok)


# --- 6 ----------------------------------------------------------------------
def t6_commutativity(trials=200):
    random.seed(11)
    ok = True
    for k in (0, 1, 2):
        n = A5.L[k]
        off = A1.keylen % n
        M = mat_from_step(lambda e, k=k, off=off: A6.step_phys(e, k, off), n)
        for _ in range(trials):
            x = [random.randint(0, 1) for _ in range(n)]
            bits = [random.randint(0, 1) for _ in range(A1.mixrounds)]
            a = list(x)
            for b in bits:
                if b:
                    a = A6.step_phys(a, k, off)
            d, nn, Mp = list(x), sum(bits), list(M)
            while nn:
                if nn & 1:
                    d = mat_apply(Mp, sum(v << i for i, v in enumerate(d)), n)
                Mp = mat_mul(Mp, Mp, n)
                nn >>= 1
            ok = ok and a == d
    check("250 conditional clocks == M^popcount (%d trials/register)" % trials, ok)


# --- 7 ----------------------------------------------------------------------
def t7_alg6_matches_alg3(pairs):
    ok = all(keystream(A3.build(K, FN)) == keystream(A6.build(K, FN)) for K, FN in pairs)
    check("Alg.6 keystream == Alg.3 (%d pairs)" % len(pairs), ok)


# --- 8 ----------------------------------------------------------------------
def t8_vs_classical(pairs):
    ok = True
    for K, FN in pairs:
        c = A5GMR1(key=K, frame_number=FN)
        c.initialize()
        ref = "".join(str(b) for b in c.generate_keystream(A1.kslen))
        ok = ok and keystream(A5.build(K, FN)) == ref
        ok = ok and keystream(A6.build(K, FN)) == ref
    check("Alg.5 and Alg.6 == CLASSICAL reference (%d pairs)" % len(pairs), ok)


# --- 9 ----------------------------------------------------------------------
def t9_barrel_every_count():
    """The barrel must realise M^n for EVERY n the 8-bit counter can hold.
    Random keys only produce n ~ 187 +- 7, so bit 7 of n is always 1 and the
    ctl=0 branch of controlled-M^128 is never exercised by keystream tests.
    Reference here is plain repeated clocking, not matrix powering."""
    random.seed(9)
    ok = True
    for k in (0, 1, 2):
        n = A5.L[k]
        off = A1.keylen % n
        M = mat_from_step(lambda e, k=k, off=off: A6.step_phys(e, k, off), n)
        reg = QuantumRegister(n, "r")
        ctl = QuantumRegister(8, "c")
        qc = QuantumCircuit(reg, ctl)
        for w in range(8):
            A6.controlled_matrix(qc, mat_pow2(M, n, w), list(reg), ctl[w], n)
        gates = compile_circuit(qc)
        for cnt in range(256):
            for _trial in range(2):
                x = [random.randint(0, 1) for _i in range(n)]
                cbits = [(cnt >> w) & 1 for w in range(8)]
                got = sim(gates, x + cbits)
                want = list(x)
                for _step in range(cnt):
                    want = A6.step_phys(want, k, off)
                ok = ok and got[:n] == want and got[n:] == cbits
    check("barrel == repeated clocking for every count n = 0..255 (3 registers)", ok)


# --- 10 ---------------------------------------------------------------------
def t10_popcount_tree():
    """Carry-save popcount returns exactly the number of set input bits.
    Exhaustive for 1..10 inputs; all-0, all-1, and random at density 1/2 and
    3/4 (the real clock-bit density) for 11..32 inputs and for 250."""
    random.seed(10)
    ok = True
    cases = 0
    for nb in list(range(1, 33)) + [A1.mixrounds]:
        _ops, ncar, _out = tree_plan(nb)
        breg = QuantumRegister(nb, "b")
        areg = QuantumRegister(max(ncar, 1), "a")
        qc = QuantumCircuit(breg, areg)
        out = A6.popcount(qc, list(breg), list(areg), 0)
        pos = {q: i for i, q in enumerate(qc.qubits)}
        gates = compile_circuit(qc)
        if nb <= 10:
            pats = [[(v >> i) & 1 for i in range(nb)] for v in range(2 ** nb)]
        else:
            pats = [[0] * nb, [1] * nb]
            pats += [[random.randint(0, 1) for _i in range(nb)] for _j in range(100)]
            pats += [[1 if random.random() < 0.75 else 0 for _i in range(nb)]
                     for _j in range(100)]
        for bits in pats:
            st = sim(gates, bits + [0] * len(areg))
            val = sum(st[pos[q]] << w for w, q in out.items() if q is not None)
            ok = ok and val == sum(bits)
            cases += 1
    check("carry-save popcount exact (%d input patterns, 1..32 and 250 bits)" % cases, ok)


# --- 11 ---------------------------------------------------------------------
def t11_alg6_inside_the_build(pairs):
    """Checks on the REAL Algorithm 6 circuit, one simulation per key:
      - each carry-save tree, as built, outputs exactly the number of clock
        bits that are set at the moment it starts
      - every Gidney AND pair is valid (same conditions as test 4)
      - every open AND writes into a |0> target
      - the three tag sets are disjoint and tag only Toffolis
    Also reports which bits of n_k random keys actually exercise."""
    ok_tree = True
    ok_and = True
    trees = 0
    seen = [set() for _w in range(8)]
    lo, hi = 10 ** 9, -1
    for K, FN in pairs:
        taps = []
        orig = A6.popcount

        def spy(qc, bits, anc, base, taps=taps, orig=orig):
            start = len(qc.data)
            out = orig(qc, bits, anc, base)
            taps.append((start, len(qc.data), list(bits), out))
            return out

        A6.popcount = spy
        try:
            qc = A6.build(K, FN)
        finally:
            A6.popcount = orig

        comp, era, opn = set(A5.AND_C), set(A5.AND_E), set(A6.AND_OPEN)
        if (comp & era) or (comp & opn) or (era & opn) or len(taps) != 3:
            ok_and = False
        pos = {b: i for i, b in enumerate(qc.qubits)}
        starts = {t[0]: i for i, t in enumerate(taps)}
        ends = {t[1]: i for i, t in enumerate(taps)}
        nk = [None, None, None]
        st = [0] * qc.num_qubits
        live = {}
        for gi, (nm, q) in enumerate(compile_circuit(qc)):
            if gi in starts:
                k = starts[gi]
                nk[k] = sum(st[pos[bq]] for bq in taps[k][2])
            if gi in ends:
                k = ends[gi]
                val = sum(st[pos[xq]] << w for w, xq in taps[k][3].items() if xq is not None)
                ok_tree = ok_tree and nk[k] is not None and val == nk[k]
                trees += 1
                for w in range(8):
                    seen[w].add((nk[k] >> w) & 1)
                lo, hi = min(lo, nk[k]), max(hi, nk[k])
            if gi in comp or gi in era or gi in opn:
                if nm != "ccx":
                    ok_and = False
                elif gi in opn:
                    if st[q[2]] != 0:
                        ok_and = False
                elif gi in comp:
                    if st[q[2]] != 0:
                        ok_and = False
                    live[q[2]] = (q[0], q[1], st[q[0]], st[q[1]])
                else:
                    c0, c1, v0, v1 = live.pop(q[2], (None, None, None, None))
                    if (c0, c1) != (q[0], q[1]) or (v0, v1) != (st[q[0]], st[q[1]]):
                        ok_and = False
                    if st[q[2]] != (st[q[0]] & st[q[1]]):
                        ok_and = False
            apply_gate(st, nm, q)
            if gi in era and st[q[2]] != 0:
                ok_and = False
        if live:
            ok_and = False
    stuck = [w for w in range(8) if len(seen[w]) < 2]
    check("Alg.6 as built: every carry-save tree outputs the true clock count (%d trees)"
          % trees, ok_tree and trees == 3 * len(pairs))
    check("Alg.6 as built: AND pairs valid, open ANDs hit |0>, tag sets disjoint", ok_and)
    print("        info: n_k observed in [%d, %d]; bits of n_k never toggled by these keys: %s"
          % (lo, hi, stuck if stuck else "none"))


# --- 12 ---------------------------------------------------------------------
def t12_cost_accounting():
    """profile_measured() must put every Toffoli in exactly one category, and
    its total must agree with the independent count from profile(). The
    measurement check is a regression guard for a bug found and fixed on
    13 Sep 2026 (open AND computes were wrongly charged a measurement)."""
    import resources as RS
    ok = True
    q5 = A5.build(RS.KEY, RS.FN)
    c5, e5 = list(A5.AND_C), list(A5.AND_E)
    q6 = A6.build(RS.KEY, RS.FN)
    c6, e6, o6 = list(A5.AND_C), list(A5.AND_E), list(A6.AND_OPEN)
    for qc, c, e, o in ((q5, c5, e5, []), (q6, c6, e6, o6)):
        p = RS.profile("x", qc)
        m = RS.profile_measured("x", qc, c, e, o)
        cats = 2 * m["and_pairs"] + m["and_open"] + m["plain_tof"]
        ok = ok and cats == p["toffoli"] == m["toffoli"]
        ok = ok and m["measurements"] == m["and_pairs"] + m["plain_tof"]
    check("cost accounting: categories partition every Toffoli; measurements = erases + Jones", ok)


if __name__ == "__main__":
    random.seed(20260908)
    PAIRS = [
        (bytes([0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF]), 42),
        (bytes([0x00] * 8), 0),
        (bytes([0xFF] * 8), 0x7FFFF),
        (bytes([0xDE, 0xAD, 0xBE, 0xEF, 0xCA, 0xFE, 0xBA, 0xBE]), 12345),
    ] + [(bytes(random.getrandbits(8) for _ in range(8)), random.getrandbits(19))
         for _ in range(6)]

    tests = {
        1: t1_reversal_equals_chain,
        2: t2_fanout_clean,
        3: lambda: t3_alg5_matches_alg3(PAIRS),
        4: lambda: t4_gidney_preconditions(PAIRS[:4]),
        5: t5_step_phys_matches_cf,
        6: t6_commutativity,
        7: lambda: t7_alg6_matches_alg3(PAIRS),
        8: lambda: t8_vs_classical(PAIRS),
        9: t9_barrel_every_count,
        10: t10_popcount_tree,
        11: lambda: t11_alg6_inside_the_build(PAIRS),
        12: t12_cost_accounting,
    }
    sel = [int(v) for v in sys.argv[1:]] or sorted(tests)

    print("")
    print("Algorithm 5 / Algorithm 6 verification  "
          "(rho=%d, %d mixing rounds, %d key/frame pairs)  tests %s"
          % (A1.kslen, A1.mixrounds, len(PAIRS), sel))
    print("")
    for i in sel:
        tests[i]()

    print("")
    if FAILURES:
        print("  *** %d FAILURE(S): %s" % (len(FAILURES), FAILURES))
        sys.exit(1)
    print("  ALL TESTS PASS")
