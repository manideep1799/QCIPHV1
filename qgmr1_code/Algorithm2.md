**Algorithm 2:** Quantum circuit of initialization and key generation phase

```
    k_0..k_63 : key      h_0..h_3 : history      y_0..y_31 : keystream
    fn : frame number (classical)
    π(i) = 8·((i div 8) XOR 1) + (i mod 8)      -- byte-pair swap, no gates

    /* INITIALIZATION                                                 */
 1  for i ← FrameBits(fn) do
 2  |   NOT (k_{π(i)})

 3  for i ← {0, 63} do
 4  |   for k ← {0,1,2,3} do
 5  |   |   Implement f(R_t)
 6  |   for k ← {0,1,2,3} do
 7  |   |   CNOT (k_{π(i)} , R[k]_0)

 8  for k ← {0,1,2,3} do
 9  |   CNOT (R[k]_0 , h_k)
10  |   CNOT (h_k , R[k]_0)
11  |   NOT (R[k]_0)

12  for i ← {0, 249} do
13  |   Implement c(S_t)
14  |   for k ← {0,1,2} do
15  |   |   Implement cf(R_t, ck_k)
16  |   Implement c(S_t)^-1
17  |   Implement f(S_t)

    /* KEY GENERATION                                                 */
18  for i ← {0, 31} do
19  |   Implement c(S_t)
20  |   for k ← {0,1,2} do
21  |   |   Implement cf(R_t, ck_k)
22  |   Implement y(t) with y_t ← y_i
23  |   Implement c(S_t)^-1
24  |   Implement f(S_t)
```

`FrameBits(fn)` returns the bit positions where the frame number is XORed
into the reorganized key. Both it and `π` are classical index arithmetic
and emit no gates, so the circuit is unchanged when the key is unknown.

Lines 9–11 force `R[k]_0` to 1. The overwrite is irreversible, so line 9
copies the old value into `h_k`, which is never uncomputed.

Lines 16 and 23 must precede lines 17 and 24: uncomputing the clock control
reads `s_15, s_6, s_1`, which `f(S_t)` would destroy.
```
qubits 189   depth 15498
cswap 17202   swap 9440   cx 5678   ccx 4806   x 1731
keystream 00100010101011110010010101001010
```
