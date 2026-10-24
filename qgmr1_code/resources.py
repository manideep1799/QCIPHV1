"""
Resource estimation for A5-GMR-1, reproducing Tables 1-4 of
Anand, Maitra, Maitra, Mukherjee, Mukhopadhyay, "Quantum Resource Estimation
for FSR Based Symmetric Ciphers and Related Grover's Attacks",
INDOCRYPT 2021, LNCS 13143, pp. 179-198.

Conventions taken from that paper:
  * gate set is NOT + CNOT + Toffoli; Toffoli is the only source of T gates
  * Toffoli -> 7 T, 8 Clifford, T-depth 4, total depth 8   (Amy et al. [3])
  * full parallelism: gates on disjoint qubits act simultaneously (Sect. 2.4)
  * keystream length rho = k + c with c = 10                (Sect. 2.2)
  * oracle       : Clifford = 2*Clifford(ENC)                        (Eq. 1)
                   T = (32*(k+10) - 84) + 2*T(ENC)                   (Eq. 3)
                   depth = 2*depth(ENC)                              (Eq. 5)
  * key search   : pi/4 * 2^(k/2) oracle iterations           (Table 3)
  * under MAXDEPTH: G_MD = (pi/4)^2 * 2^k * Og*Od / MAXDEPTH         (Eq. 9)

A5-GMR-1 additionally uses SWAP and Fredkin, which the paper's ciphers do
not. These are expanded into the paper's gate set before counting:
      SWAP(a,b)      = 3 CNOT
      Fredkin(c,a,b) = CNOT(b,a), Toffoli(c,a,b), CNOT(b,a)

Run:  python resources.py
"""

import math

from qiskit import QuantumCircuit

import algorithm1_a5gmr1 as A1
import algorithm2_a5gmr1 as A2
import algorithm3_a5gmr1_opt as A3

KEY = bytes([0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF])
FN = 42
K = A1.keylen                      # key size in bits
RHO = A1.kslen                     # keystream bits generated

T_PER_TOF = 7
CLIFF_PER_TOF = 8
TDEPTH_PER_TOF = 4
DEPTH_PER_TOF = 8


def build_baseline():
    qc = QuantumCircuit(*A1.allregs)
    A2.loadkey(qc, KEY)
    A2.initialization(qc, FN)
    A2.keygeneration(qc)
    return qc


def expand(qc):
    """Rewrite the circuit into (name, qubit-indices) over NOT/CNOT/Toffoli."""
    out = []
    for ins in qc.data:
        n = ins.operation.name
        q = [qc.find_bit(b).index for b in ins.qubits]
        if n == "swap":
            a, b = q
            out += [("cx", [a, b]), ("cx", [b, a]), ("cx", [a, b])]
        elif n == "cswap":
            c, a, b = q
            out += [("cx", [b, a]), ("ccx", [c, a, b]), ("cx", [b, a])]
        elif n in ("x", "cx", "ccx"):
            out.append((n, q))
        else:
            raise ValueError(f"unexpected gate {n}")
    return out


def weighted_depth(gates, weights):
    d = {}
    for name, idx in gates:
        base = max((d.get(i, 0) for i in idx), default=0)
        nd = base + weights.get(name, 1)
        for i in idx:
            d[i] = nd
    return max(d.values(), default=0)


def profile(name, qc):
    gates = expand(qc)
    tof = sum(1 for n, _ in gates if n == "ccx")
    cnot = sum(1 for n, _ in gates if n == "cx")
    npot = sum(1 for n, _ in gates if n == "x")

    # Amy et al. Toffoli = 7 T + 8 Clifford, the 8 being 6 CNOT + 2 one-qubit.
    n_cnot = 6 * tof + cnot
    n_1q = 2 * tof + npot
    n_t = T_PER_TOF * tof
    depth = weighted_depth(gates, {"ccx": DEPTH_PER_TOF, "cx": 1, "x": 1})

    return {
        "name": name,
        "qubits": qc.num_qubits,
        "toffoli": tof,
        "raw_cnot": cnot,
        "raw_not": npot,
        "cnot": n_cnot,
        "cliff1q": n_1q,
        "t": n_t,
        "clifford": n_cnot + n_1q,
        "t_depth": weighted_depth(gates, {"ccx": TDEPTH_PER_TOF, "cx": 0, "x": 0}),
        "full_depth": depth,
        "t_depth_seq": TDEPTH_PER_TOF * tof,
        "g_cost": n_cnot + n_1q + n_t,
        "dw_cost": depth * qc.num_qubits,
    }


def oracle(p):
    """Grover oracle cost from the cipher cost (Eqs. 1, 3, 5)."""
    return {
        "name": p["name"],
        "clifford": 2 * p["clifford"],
        "t": (32 * (K + 10) - 84) + 2 * p["t"],
        "t_depth": 2 * p["t_depth"],
        "full_depth": 2 * p["full_depth"],
        "qubits": p["qubits"] + 1,
    }


def m2(x):
    """Format as  m . 2^e  the way the paper does."""
    if x <= 0:
        return "0"
    e = math.floor(math.log2(x))
    return f"{x / 2 ** e:.3f} * 2^{e}"


# Reference rows, verbatim from Anand et al., INDOCRYPT 2021, Table 1.
PAPER_2021 = [
    ("Grain-128-AEAD",        158679, 126812,  72464,  75951, 531),
    ("TinyJAMBU (k = 128)",   148817, 103936,  59392, 126209, 385),
    ("TinyJAMBU (k = 192)",   161617, 112896,  64512, 137089, 449),
    ("TinyJAMBU (k = 256)",   174417, 121856,  69632, 147969, 513),
    ("LIZARD (k = 120/80)",   314897, 253988, 145136, 210993, 392),
    ("Grain-v1 (k = 80)",     135410, 108500,  62000,  74886, 346),
]


def table_indocrypt(rows):
    """Exact column layout of Anand et al., INDOCRYPT 2021, Table 1."""
    print()
    print("Table 1. Cost of implementing the ciphers")
    print()
    h = (f"  {'Cipher':<24}{'Clifford gates':>16}{'T gates':>10}"
         f"{'T-depth':>10}{'Full depth':>12}{'qubits':>8}")
    print(h)
    print("  " + "-" * (len(h) - 2))
    for n, c, t, td, fd, w in PAPER_2021:
        print(f"  {n:<24}{c:>16,}{t:>10,}{td:>10,}{fd:>12,}{w:>8,}")
    print("  " + "-" * (len(h) - 2))
    for p in rows:
        print(f"  {p['name']:<24}{p['clifford']:>16,}{p['t']:>10,}"
              f"{p['t_depth']:>10,}{p['full_depth']:>12,}{p['qubits']:>8,}")

    print()
    print(r"  LaTeX:")
    print(r"  \begin{table}[t]")
    print(r"  \centering")
    print(r"  \caption{Cost of implementing the ciphers. Rows above the rule are"
          r" from~\cite{anand2021}.}")
    print(r"  \begin{tabular}{|l|r|r|r|r|r|}")
    print(r"  \hline")
    print(r"  Cipher & Clifford gates & $T$ gates & $T$-depth & Full depth & qubits \\")
    print(r"  \hline")
    for n, c, t, td, fd, w in PAPER_2021:
        print(f"  {n} & {c} & {t} & {td} & {fd} & {w} " + r"\\")
    print(r"  \hline")
    for p in rows:
        print(f"  {p['name']} & {p['clifford']} & {p['t']} & {p['t_depth']} & "
              f"{p['full_depth']} & {p['qubits']} " + r"\\")
    print(r"  \hline")
    print(r"  \end{tabular}")
    print(r"  \end{table}")


def table1(rows):
    """Format of Anand-Nandi-Isobe (IET QC 2024), Table 1."""
    print()
    print(f"Table 1. Cost of implementing quantum circuits to generate "
          f"rho = {RHO} keystream bits")
    print()
    h = (f"  {'Cipher':<24}{'#CNOT':>12}{'#1qCliff':>11}{'#T':>12}"
         f"{'T-depth':>10}{'Full-depth':>12}{'Width':>8}")
    print(h)
    print("  " + "-" * (len(h) - 2))
    for p in rows:
        print(f"  {p['name']:<24}{p['cnot']:>12,}{p['cliff1q']:>11,}{p['t']:>12,}"
              f"{p['t_depth']:>10,}{p['full_depth']:>12,}{p['qubits']:>8,}")
    print()
    print(f"  {'':24}{'G-cost':>14}{'DW-cost':>18}")
    for p in rows:
        print(f"  {p['name']:<24}{p['g_cost']:>14,}{p['dw_cost']:>18,}")


def table2(rows):
    print()
    print("Table 2. Cost of Grover oracle")
    print()
    h = (f"  {'Cipher':<24}{'Clifford':>12}{'T gates':>11}{'Og':>12}"
         f"{'T-depth':>11}{'Od':>12}{'qubits':>9}")
    print(h)
    print("  " + "-" * (len(h) - 2))
    for o in rows:
        og = o["clifford"] + o["t"]
        print(f"  {o['name']:<24}{o['clifford']:>12,}{o['t']:>11,}{og:>12,}"
              f"{o['t_depth']:>11,}{o['full_depth']:>12,}{o['qubits']:>9,}")


def table3(rows):
    it = math.pi / 4 * 2 ** (K / 2)
    print()
    print(f"Table 3. Cost of Grover's algorithm with pi/4 * 2^(k/2) = "
          f"{m2(it)} oracle iterations")
    print()
    h = (f"  {'Cipher':<24}{'Clifford':>16}{'T gates':>16}{'Gate cost G':>16}"
         f"{'T-depth':>16}{'Full depth D':>16}")
    print(h)
    print("  " + "-" * (len(h) - 2))
    for o in rows:
        og = o["clifford"] + o["t"]
        print(f"  {o['name']:<24}{m2(it * o['clifford']):>16}"
              f"{m2(it * o['t']):>16}{m2(it * og):>16}"
              f"{m2(it * o['t_depth']):>16}{m2(it * o['full_depth']):>16}")


def table4(o):
    print()
    print("Table 4. Cost of Grover search under MAXDEPTH   "
          "G_MD = (pi/4)^2 * 2^k * Og*Od / MAXDEPTH")
    print()
    og = o["clifford"] + o["t"]
    od = o["full_depth"]
    const = (math.pi / 4) ** 2 * 2 ** K * og * od

    h = f"  {'k':>4}  {'':<22}{'2^40':>18}{'2^64':>18}{'2^96':>18}{'G_MD x MAXDEPTH':>20}"
    print(h)
    print("  " + "-" * (len(h) - 2))
    print(f"  {128:>4}  {'NIST [25]':<22}{'2^130':>18}{'2^106':>18}{'2^74':>18}{'2^170':>20}")
    row = f"  {K:>4}  {'A5-GMR-1':<22}"
    for md_exp in (40, 64, 96):
        g = const / 2 ** md_exp
        # below the unparallelised cost the attack needs no parallelisation
        floor = (math.pi / 4) * 2 ** (K / 2) * og
        row += f"{m2(max(g, floor)):>18}"
    row += f"{m2(const):>20}"
    print(row)
    print()
    print("  Entries clamped at the single-machine cost pi/4 * 2^(k/2) * Og;")
    print("  at those MAXDEPTH values the attack needs no parallelisation")
    print("  (the * cases in the paper's Table 4).")


# ---------------------------------------------------------------------------
# Measurement-assisted Toffoli accounting  (SEPARATE convention -- see below)
# ---------------------------------------------------------------------------
# The tables above follow Anand et al.: gate set NOT + CNOT + Toffoli, and
# 1 Toffoli = 7 T (Amy et al.). That 7 is optimal for an EXACT Clifford+T
# circuit with no measurement.
#
# Two constructions beat it by using mid-circuit measurement and classically
# controlled Clifford correction:
#
#   Gidney, "Halving the cost of quantum addition", Quantum 2:74 (2018).
#       AND into a |0> target        : 4 T
#       AND-dagger (erase)           : 0 T  -- X-basis measurement + CZ fix-up
#     Valid only when the target starts |0>, the two controls are unchanged
#     between compute and erase, and the target holds exactly AND(controls)
#     at erase time. verify_and.py checks all three on every pair.
#
#   Jones, "Low-overhead constructions for the fault-tolerant Toffoli gate",
#       Phys. Rev. A 87, 022328 (2013).
#       any Toffoli, data targets included : 4 T, T-depth 1, 1 ancilla
#
# These are NOT comparable with the rows above -- they use gates outside that
# paper's gate set. They belong in their own table row with a footnote.
#
# SOURCE CHECK, 13 Sep 2026, against the full texts (arXiv 1709.06648v3, 1212.5069v1):
#   confirmed  Gidney AND compute 4 T, erase 0 T        (Quantum 2, 74, 2018)
#   confirmed  Jones Toffoli: 4 T, one ancilla, one z-basis measurement, and a
#              controlled-Z correction conditioned on it (Phys. Rev. A 87, 022328, 2013)
#   NOT confirmed from the text: T-depth 1 for either construction, and that a
#   Gidney erase uses exactly one measurement (drawn only in the paper's Fig. 3).
#   The t_depth field, and the erase part of the measurements field, of
#   profile_measured() rest on those unconfirmed figures.
#
# HONESTY NOTE ON CLIFFORD COUNTS: the exact CLIFFORD counts of both constructions are
# not something this script sources, so Clifford is carried over unchanged at
# 8 per Toffoli (the Amy et al. figure). Treat the Clifford column of the
# measured rows as INDICATIVE, not as a cited result. Full depth likewise does
# not model classical feed-forward latency.

T_GIDNEY_AND = 4        # compute
T_GIDNEY_ERASE = 0      # erase, measurement based
T_JONES = 4             # any Toffoli


def expand_tagged(qc, and_c=(), and_e=(), and_open=()):
    """expand(), but every emitted gate carries the role of the Toffoli it came
    from: 'c' Gidney AND compute (4 T), 'e' Gidney AND erase (0 T, measurement
    based), 'open' AND compute never erased (4 T, cleared by ENC-dagger), or
    None meaning a general Toffoli that needs the Jones construction (4 T).
    Roles are TAGGED at circuit-build time, never inferred."""
    rc, re_, ro = set(and_c), set(and_e), set(and_open)
    out = []
    for gi, ins in enumerate(qc.data):
        n = ins.operation.name
        q = [qc.find_bit(b).index for b in ins.qubits]
        role = "c" if gi in rc else "e" if gi in re_ else "open" if gi in ro else None
        if n == "swap":
            a, b = q
            out += [("cx", [a, b], None), ("cx", [b, a], None), ("cx", [a, b], None)]
        elif n == "cswap":
            c, a, b = q
            out += [("cx", [b, a], None), ("ccx", [c, a, b], None), ("cx", [b, a], None)]
        elif n in ("x", "cx", "ccx"):
            out.append((n, q, role))
        else:
            raise ValueError(f"unexpected gate {n}")
    return out


def profile_measured(name, qc, and_c=(), and_e=(), and_open=()):
    """Cost under the measurement-assisted convention (Gidney + Jones)."""
    gates = expand_tagged(qc, and_c, and_e, and_open)

    n_c = sum(1 for g in gates if g[2] == "c")
    n_e = sum(1 for g in gates if g[2] == "e")
    n_o = sum(1 for g in gates if g[2] == "open")
    n_p = sum(1 for g in gates if g[0] == "ccx" and g[2] is None)
    cnot = sum(1 for g in gates if g[0] == "cx")
    npot = sum(1 for g in gates if g[0] == "x")
    tof = n_c + n_e + n_o + n_p
    assert n_c == n_e, f"{n_c} AND computes but {n_e} erases -- unpaired"

    # erases are free; everything else that consumes T costs 4
    t = (n_c + n_o) * T_GIDNEY_AND + n_p * T_JONES
    tdw = {"c": 1, "open": 1, None: 1, "e": 0}
    d = {}
    for nm, idx, role in gates:
        w = tdw[role] if nm == "ccx" else 0
        base = max((d.get(i, 0) for i in idx), default=0)
        for i in idx:
            d[i] = base + w
    t_depth = max(d.values(), default=0)

    n_cnot = 6 * tof + cnot           # INDICATIVE only -- see honesty note
    n_1q = 2 * tof + npot
    return {
        "name": name, "qubits": qc.num_qubits, "toffoli": tof,
        "and_pairs": n_c, "and_open": n_o, "plain_tof": n_p,
        "t": t, "t_depth": t_depth, "clifford": n_cnot + n_1q,
        # a Gidney AND COMPUTE uses no measurement; only its erase does, and
        # every Jones Toffoli uses one. Open ANDs are never erased here.
        "measurements": n_e + n_p,
        "full_depth": weighted_depth([(g[0], g[1]) for g in gates],
                                     {"ccx": DEPTH_PER_TOF, "cx": 1, "x": 1}),
    }


if __name__ == "__main__":
    print("=" * 96)
    print(f"  A5-GMR-1  --  k = {K}, rho = k + 10 = {RHO} keystream bits, "
          f"{A1.mixrounds} mixing rounds")
    print("=" * 96)

    import algorithm4_a5gmr1_dagger as A4
    import algorithm5_a5gmr1_par as A5
    import algorithm6_a5gmr1_batch as A6

    qc1, qc3, qc4 = build_baseline(), A3.build(KEY, FN), A4.build(KEY, FN)
    qc5 = A5.build(KEY, FN)
    and_c5, and_e5 = list(A5.AND_C), list(A5.AND_E)      # capture before A6 resets them
    qc6 = A6.build(KEY, FN)
    and_c6, and_e6, and_o6 = list(A5.AND_C), list(A5.AND_E), list(A6.AND_OPEN)

    base = profile("A5-GMR-1 (Alg. 1+2)", qc1)
    opt = profile("A5-GMR-1 (Alg. 3)", qc3)
    dag = profile("A5-GMR-1+ (Alg. 4)", qc4)
    par = profile("A5-GMR-1 (Alg. 5)", qc5)
    bat = profile("A5-GMR-1+ (Alg. 6)", qc6)
    rows = [base, opt, dag, par, bat]

    print()
    print("  raw gate counts before expansion into NOT/CNOT/Toffoli")
    for p, qc in ((base, qc1), (opt, qc3), (dag, qc4), (par, qc5), (bat, qc6)):
        print(f"    {p['name']:<24}{dict(qc.count_ops())}")
    print()
    print("  after expansion")
    for p in rows:
        print(f"    {p['name']:<24}Toffoli {p['toffoli']:>8,}   "
              f"CNOT {p['raw_cnot']:>8,}   NOT {p['raw_not']:>8,}")

    table_indocrypt(rows)
    table1(rows)

    orc = [oracle(p) for p in rows]
    table2(orc)
    table3(orc)
    table4(orc[2])

    print()
    print("  T-depth convention: computed under the full-parallelism assumption,")
    print("  matching Anand-Nandi-Isobe (IET QC 2024) Table 1, which revises the")
    print("  INDOCRYPT 2021 T-depths downward (Grain-128-AEAD 72,464 -> 3,960).")
    print("  The sequential upper bound 4 x #Toffoli, used implicitly in the 2021")
    print("  table, would instead give:")
    for p in rows:
        print(f"    {p['name']:<24}T-depth (sequential) {p['t_depth_seq']:>10,}")
    print()
    print("  A5-GMR-1+ rows (Alg. 4, Alg. 6) omit internal uncomputation and are valid")
    print("  ONLY inside a Grover oracle where ENC-dagger restores the ancillas -- the")
    print("  Atom-dagger trick of Anand-Nandi-Isobe, Sect. 4.2. Alg. 6 additionally")
    print("  leaves the 250 clock bits and the carry-save tree dirty, which is what")
    print("  buys the Toffoli reduction; it costs width, and its DW-cost is WORSE than")
    print("  Alg. 5's. Alg. 5 remains the best NARROW circuit.")

    m5 = profile_measured("A5-GMR-1 (Alg. 5)", qc5, and_c5, and_e5)
    m6 = profile_measured("A5-GMR-1+ (Alg. 6)", qc6, and_c6, and_e6, and_o6)
    h = (f"  {'Cipher':<22}{'AND pairs':>11}{'open AND':>10}{'Jones Tof':>11}"
         f"{'T gates':>11}{'T-depth':>10}{'measure':>10}{'qubits':>9}")
    print()
    print("=" * len(h))
    print("  Table 5. SEPARATE CONVENTION -- measurement-assisted Toffolis")
    print("  Gidney AND (4 T compute / 0 T erase) + Jones Toffoli (4 T, T-depth 1).")
    print("  NOT comparable with the tables above: those forbid measurement.")
    print("  Clifford counts are omitted here on purpose -- see the honesty note in")
    print("  the source; only T-count and T-depth are sourced for these constructions.")
    print("=" * len(h))
    print(h)
    print("  " + "-" * (len(h) - 2))
    for p in (m5, m6):
        print(f"  {p['name']:<22}{p['and_pairs']:>11,}{p['and_open']:>10,}"
              f"{p['plain_tof']:>11,}{p['t']:>11,}{p['t_depth']:>10,}"
              f"{p['measurements']:>10,}{p['qubits']:>9,}")
    print()
    print(f"  Alg. 3 baseline {opt['t']:,} T  ->  Alg. 5 measured {m5['t']:,} T "
          f"(x{opt['t']/m5['t']:.2f})  ->  Alg. 6 measured {m6['t']:,} T "
          f"(x{opt['t']/m6['t']:.2f})")
