"""
GF(2) linear-circuit synthesis helpers for Algorithm 6.

A cyclic-LFSR clock is a GF(2)-linear map y = A x, so it can be built from
CNOTs alone. Its *controlled* version replaces every CNOT by a Toffoli, which
is what the batched-mixing barrel needs.

Nothing here is approximate: synth_cnots() is checked against the matrix it
came from by verify_synth(), on every basis vector.
"""


def mat_apply(A, x, n):
    """y = A x over GF(2). A[i] is a bitmask of the inputs feeding output i."""
    return [bin(A[i] & x).count("1") & 1 for i in range(n)]


def mat_from_step(step, n):
    """Build A from a function mapping a bit-list to a bit-list."""
    cols = []
    for j in range(n):
        e = [1 if i == j else 0 for i in range(n)]
        cols.append(step(e))
    return [sum(cols[j][i] << j for j in range(n)) for i in range(n)]


def mat_mul(A, B, n):
    """(A B)[i] = XOR of B[j] for j in A[i]."""
    out = []
    for i in range(n):
        v = 0
        for j in range(n):
            if (A[i] >> j) & 1:
                v ^= B[j]
        out.append(v)
    return out


def mat_pow2(A, n, e):
    """A^(2^e) by repeated squaring."""
    P = list(A)
    for _ in range(e):
        P = mat_mul(P, P, n)
    return P


def synth_cnots(A, n):
    """Return [(control, target), ...] whose circuit, applied in list order,
    realises x -> A x.

    Gauss-Jordan reduces A to I with row ops Op_p...Op_1 A = I, hence
    A = Op_1...Op_p. A circuit G_1..G_m equals G_m...G_1 as a matrix, so the
    row ops must be emitted in REVERSE elimination order.
    Row op "row i += row r" is CNOT(control=r, target=i).
    """
    M = list(A)
    ops = []

    def rowadd(r, i):
        M[i] ^= M[r]
        ops.append((r, i))

    r = 0
    for col in range(n):
        p = next((i for i in range(r, n) if (M[i] >> col) & 1), None)
        if p is None:
            continue
        if p != r:
            rowadd(p, r)          # row swap via 3 additions
            rowadd(r, p)
            rowadd(p, r)
        for i in range(n):
            if i != r and (M[i] >> col) & 1:
                rowadd(r, i)
        r += 1
    assert all(M[i] == (1 << i) for i in range(n)), "elimination did not reach I"
    return list(reversed(ops))


def verify_synth(A, ops, n):
    """Run the CNOT list on every basis vector and compare against A."""
    for j in range(n):
        x = [1 if i == j else 0 for i in range(n)]
        for c, t in ops:
            x[t] ^= x[c]
        if x != mat_apply(A, 1 << j, n):
            return False
    return True


def tree_plan(n):
    """Column-reduction plan for summing n single bits.

    Yields ops as ('fa', a, b, c) or ('ha', a, b) over abstract slot ids, plus
    the final output slot per weight. Returns (ops, n_carries, out_weights).
    Only the SHAPE matters here -- used to size the ancilla register.
    """
    nxt = [0]
    def new():
        nxt[0] += 1
        return nxt[0] - 1

    cols = {0: [("in", i) for i in range(n)]}
    ops, carries, out = [], 0, {}
    w = 0
    while True:
        col = cols.get(w, [])
        while len(col) >= 3:
            a, b, c = col.pop(), col.pop(), col.pop()
            car = ("anc", new()); carries += 1
            ops.append(("fa", a, b, c, car, w))
            cols.setdefault(w + 1, []).append(car)
            col.append(c)
        if len(col) == 2:
            a, b = col.pop(), col.pop()
            car = ("anc", new()); carries += 1
            ops.append(("ha", a, b, car, w))
            cols.setdefault(w + 1, []).append(car)
            col.append(b)
        out[w] = col[0] if col else None
        cols[w] = col
        w += 1
        if not cols.get(w):
            break
    return ops, carries, out
