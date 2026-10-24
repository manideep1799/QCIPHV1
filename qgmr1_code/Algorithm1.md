**Algorithm 1:** Quantum Circuit for A5-GMR-1

```
    Registers:  a = R1 (19)   b = R2 (22)   c = R3 (23)   s = R4 (17)
    Ancillas:   mj, ck0..ck2, me0..me2, ot
    R ← [a, b, c, s]        L ← [19, 22, 23, 17]

    /* QUANTUM CIRCUIT FOR f(R_t)  -- unconditional update            */
    T ← [{13,16,17}, {12,16,20}, {17,18,21}, {8,12,13}]
 1  for i ← T[k] do
 2  |   CNOT (R[k]_i , R[k]_{L[k]-1})
 3  for i ← L[k]-1 down to 1 do
 4  |   SWAP (R[k]_i , R[k]_{i-1})

    /* QUANTUM CIRCUIT FOR cf(R_t, ctl)  -- conditional update        */
 5  for i ← T[k] do
 6  |   Toffoli (R[k]_i , ctl , R[k]_{L[k]-1})
 7  for i ← L[k]-1 down to 1 do
 8  |   Fredkin (ctl , R[k]_i , R[k]_{i-1})

    /* QUANTUM CIRCUIT FOR c(S_t)  -- clock control                   */
    P ← [15, 6, 1]
 9  Toffoli (s_15, s_6, mj) ; Toffoli (s_15, s_1, mj) ; Toffoli (s_6, s_1, mj)
10  for j ← {0,1,2} do
11  |   NOT (ck_j) ; CNOT (s_{P[j]}, ck_j) ; CNOT (mj, ck_j)

    /* QUANTUM CIRCUIT FOR y(t)                                       */
    M ← [(1,6,15), (3,8,14), (4,15,19)]     X ← [11, 1, 0]
12  for j ← {0,1,2} do
13  |   Toffoli (R[j]_{M[j]_0}, R[j]_{M[j]_1}, me_j)
14  |   Toffoli (R[j]_{M[j]_0}, R[j]_{M[j]_2}, me_j)
15  |   Toffoli (R[j]_{M[j]_1}, R[j]_{M[j]_2}, me_j)
16  |   CNOT (R[j]_{X[j]}, me_j)
17  for j ← {0,1,2} do
18  |   CNOT (me_j, ot)
19  CNOT (ot, y_t)
20  for j ← {2,1,0} do
21  |   CNOT (me_j, ot)
22  for j ← {2,1,0} do
23  |   CNOT (R[j]_{X[j]}, me_j)
24  |   Toffoli (R[j]_{M[j]_1}, R[j]_{M[j]_2}, me_j)
25  |   Toffoli (R[j]_{M[j]_0}, R[j]_{M[j]_2}, me_j)
26  |   Toffoli (R[j]_{M[j]_0}, R[j]_{M[j]_1}, me_j)
```

Lines 1–2 use `L[k]-1 ∈ T[k]`, so the feedback parity accumulates into the
register's own top bit and needs no ancilla. Lines 3–4 rotate the register
cyclically, carrying that bit into position 0.

`c(S_t)^-1` is lines 9–11 in reverse order; it must be applied **before**
`f(S_t)`, since it re-reads `s_15, s_6, s_1`.

Lines 19 is the only gate that writes outside scratch; lines 20–26 return
`ot` and `me_0..me_2` to |0>.
