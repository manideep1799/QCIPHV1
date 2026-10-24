# Quantum Reversible A5-GMR-1 — Verified Implementation

A full reversible-circuit (Qiskit) implementation of the A5-GMR-1
stream cipher, mirroring the module structure of the verified classical
reference implementation module-for-module.

## Structure (mirrors the classical code exactly)

| Quantum module | Classical counterpart | What it does |
|---|---|---|
| `blocks/register_clock.py` | `registers.py` | Reversible LFSR clock (Construction B: in-place feedback accumulator, no ancilla) |
| `blocks/primitives.py` | `majority.py` | Reversible majority + equality gates |
| `blocks/output.py` | `output.py` | Reversible keystream output combination |
| `cycle/layout.py`, `cycle/full_cycle.py` | `clocking.py` | One complete irregular clock cycle |
| `reversible_init/full_initialization.py` | `initialization.py` | All 4 init stages (key/frame reorg, key loading, forced bit, warmup) |
| `quantum_cipher_pkg/quantum_cipher.py` | `cipher.py` | Top-level `A5GMR1Quantum` class, mirrors `A5GMR1`'s public API |

## Requirements

```
pip install qiskit qiskit-aer

```


Also requires the classical reference implementation (from `a5_gmr1.zip`,
already produced by this project) importable on your Python path — the
quantum code cross-checks against it directly in every test file.



## Running

```bash
cd verification
python3 test_full_cipher_api.py   # the main end-to-end test
```

Or use the module directly:

```python
from quantum_cipher_pkg.quantum_cipher import A5GMR1Quantum

cipher = A5GMR1Quantum(key=bytes([0x01,0x23,0x45,0x67,0x89,0xAB,0xCD,0xEF]), frame_number=42)
cipher.initialize()
downlink = cipher.generate_downlink(114)
uplink = cipher.generate_uplink(114)
```

## Resource requirements

Verified at real cipher scale (271 qubits for 114 keystream bits, up to
385 qubits for 228 bits): runs in a few seconds using **under 1 GB RAM**.

This works because the circuit never enters superposition — every gate
(X, CNOT, Toffoli, SWAP, Fredkin) maps a definite bitstring to another
definite bitstring when fed a classical-basis-state input, so
`AerSimulator(method="stabilizer")` / `method="matrix_product_state")`
represent the state compactly instead of as a dense `2^n`-entry vector.
This is exact simulation, not an approximation — but it is **only**
cheap for verifying correctness on concrete keys. Running this circuit
with the key in actual superposition (a real Grover attack) is a
fundamentally different, exponentially expensive problem that this
project has not attempted.

## Verification summary

| Module | Trials | Result |
|---|---|---|
| Register clock (unconditional) | 8,112 (exhaustive small + 2000/register real-scale) | PASS |
| Register clock (controlled) | 4,096 (exhaustive small + 1000/register real-scale) | PASS |
| Majority / Equality primitives | 12 (exhaustive + forward/inverse) | PASS |
| Output block | 4,096 (exhaustive, real register lengths) | PASS |
| Full cycle (single) | 30 (real scale) | PASS |
| Full cycle (chained, 2/5/10/20 cycles) | 60 (real scale) | PASS |
| Full initialization + keystream | 6 keys (real scale, incl. history-qubit edge case) | PASS |
| Full cipher public API (DL/UL) | reproduces exact known reference vectors | PASS |

Every test compares directly against the classical reference
(`registers.py`, `clocking.py`, `output.py`, `initialization.py`,
`cipher.py`), not against other quantum code.

## Design basis

Built per the corrected design documents (Docs 01–10), specifically:
- Construction B (Doc 03 §3.1a, Doc 09 D8): in-place feedback into the
  register's own top-bit qubit — valid because `(L-1) ∈ T` for every
  register, checked in code (`register_clock.check_precondition`), not
  assumed.
- Step 5→7½ ordering (Doc 05, Doc 09 D9): R4's unconditional clock is
  applied *after* all uncomputation depending on R4's control bits, not
  before — verified by explicit ancilla-cleanliness checks in every test.
