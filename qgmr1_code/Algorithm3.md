**Algorithm 3:** Quantum Circuit for A5-GMR-1 with relabelled shifts

```
    off[0..3] ← 0                     -- classical rotation offsets
    q(k, j)  = R[k]_{(j - off[k]) mod L[k]}

    /* QUANTUM CIRCUIT FOR f(R_t)  -- unconditional, shift is free    */
 1  for i ← T[k] do
 2  |   CNOT ( q(k, i) , q(k, L[k]-1) )
 3  off[k] ← (off[k] + 1) mod L[k]                       /* no gates */

    /* QUANTUM CIRCUIT FOR cf(R_t, ctl)  -- conditional, off frozen   */
 4  for i ← T[k] do
 5  |   Toffoli ( q(k, i) , ctl , q(k, L[k]-1) )
 6  for i ← L[k]-1 down to 1 do
 7  |   Fredkin ( ctl , R[k]_i , R[k]_{i-1} )

    /* c(S_t) and y(t) as in Algorithm 1, every index taken through q */
 8  Toffoli ( q(3,15), q(3,6), mj ) ; ... ; CNOT ( q(3,P[j]), ck_j )
 9  Toffoli ( q(j,M[j]_0), q(j,M[j]_1), me_j ) ; ... ; CNOT ( q(j,X[j]), me_j )

    /* phases identical to Algorithm 2                                */
```

Line 3 replaces the `L[k]-1` SWAP chain of Algorithm 1 lines 3-4. The shift
is a classical index update performed while the circuit is being written, so
it emits no gates and adds no depth. It is valid only where the clock is
unconditional -- the 64 key-loading rounds and R4 on every cycle.

Lines 6-7 keep the Fredkin chain: whether a conditionally-clocked register
has advanced is quantum information, so it cannot be absorbed into a
classical `off`. The chain realises the fixed physical permutation
`p -> p+1 (mod L)`, which is independent of `off`, so R1/R2/R3 correctly
carry the constant offset they acquired during key loading.

| | Algorithm 1+2 | Algorithm 3 | |
|---|---|---|---|
| qubits | 189 | 189 | — |
| SWAP | 9,440 | **0** | −100% |
| Fredkin | 17,202 | 17,202 | — |
| CNOT | 5,678 | 5,678 | — |
| Toffoli | 4,806 | 4,806 | — |
| NOT | 1,731 | 1,731 | — |
| total gates | 38,857 | **29,417** | −24.3% |
| circuit depth | 15,498 | **10,632** | −31.4% |

Lowered to Clifford+T:

| | Algorithm 1+2 | Algorithm 3 | |
|---|---|---|---|
| Clifford | 246,197 | 217,877 | −11.5% |
| T count | 154,056 | 154,056 | **0%** |
| T depth | 34,968 | 34,694 | −0.8% |
| full depth | 120,558 | 106,803 | −11.4% |

The T metrics are unchanged, and necessarily so: SWAP is a Clifford gate, so
removing 9,440 of them cannot remove a single T gate. T count is fixed by the
22,008 Toffoli-class gates, which Algorithm 3 does not touch. The saving is
real for gate count and depth, and null for the metric that determines
magic-state cost.
