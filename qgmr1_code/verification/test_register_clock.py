"""
verification/test_register_clock.py
======================================

Verifies blocks/register_clock.py against the classical
registers.LFSR.clock() -- the ground truth this whole project is built
to match.

Exhaustive testing at small register sizes; large random-sample testing
at REAL cipher register sizes (19, 22, 23, 17), since the circuit is
pure Clifford (X, CNOT, SWAP only -- no Toffoli in the unconditional
case), which Aer's stabilizer method simulates in time roughly linear
in qubit count rather than exponential.
"""

import sys
import os
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "classical_ref", "a5_gmr1"))

from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator

from blocks.register_clock import append_register_clock
from registers import LFSR
from constants import (
    R1_LENGTH, R1_TAPS, R2_LENGTH, R2_TAPS,
    R3_LENGTH, R3_TAPS, R4_LENGTH, R4_TAPS,
)

SIM = AerSimulator(method="stabilizer")


def tap_positions(taps: int, length: int):
    return sorted([i for i in range(length) if (taps >> i) & 1])


def run_one_trial(L: int, taps: list, initial_state: int):
    qc = QuantumCircuit(L, L)
    for i in range(L):
        if (initial_state >> i) & 1:
            qc.x(i)
    append_register_clock(qc, L, taps)
    qc.measure(range(L), range(L))

    result = SIM.run(qc, shots=1).result()
    (bitstring, _), = result.get_counts().items()
    bits = bitstring[::-1]
    quantum_state = 0
    for i in range(L):
        if bits[i] == "1":
            quantum_state |= (1 << i)

    lfsr = LFSR(length=L, taps=sum(1 << t for t in taps))
    lfsr.set_state(initial_state)
    lfsr.clock()
    classical_state = lfsr.get_state()

    return quantum_state == classical_state, quantum_state, classical_state


def exhaustive_test(L: int, taps: list, label: str) -> bool:
    print(f"--- Exhaustive: {label} (L={L}, taps={taps}) ---")
    all_pass = True
    for state in range(1 << L):
        ok, q, c = run_one_trial(L, taps, state)
        all_pass = all_pass and ok
        if not ok:
            print(f"  FAIL state={state}: quantum={q} classical={c}")
    print(f"  {1<<L}/{1<<L} states checked. Result:", "ALL PASS" if all_pass else "FAILURE")
    return all_pass


def random_sample_test(L: int, taps: list, label: str, n_trials: int, seed: int) -> bool:
    print(f"--- Random sample: {label} (L={L}, taps={taps}), {n_trials} trials ---")
    rng = random.Random(seed)
    all_pass = True
    for _ in range(n_trials):
        state = rng.randrange(1 << L)
        ok, q, c = run_one_trial(L, taps, state)
        all_pass = all_pass and ok
        if not ok:
            print(f"  FAIL state={state}: quantum={q} classical={c}")
    print(f"  {n_trials}/{n_trials} random states checked. Result:", "ALL PASS" if all_pass else "FAILURE")
    return all_pass


if __name__ == "__main__":
    results = []

    # Small exhaustive sanity checks first
    results.append(exhaustive_test(4, [0, 1, 2, 3], "small L=4, all taps"))
    results.append(exhaustive_test(5, [0, 1, 3, 4], "small L=5"))
    results.append(exhaustive_test(6, [0, 2, 4, 5], "small L=6"))

    print()
    print("=" * 70)
    print("REAL CIPHER REGISTER LENGTHS -- large random sample (2000 trials each)")
    print("=" * 70)

    real_registers = {
        "R1": (R1_LENGTH, R1_TAPS), "R2": (R2_LENGTH, R2_TAPS),
        "R3": (R3_LENGTH, R3_TAPS), "R4": (R4_LENGTH, R4_TAPS),
    }
    for name, (length, taps_mask) in real_registers.items():
        positions = tap_positions(taps_mask, length)
        results.append(random_sample_test(length, positions, f"REAL {name}", n_trials=2000, seed=hash(name) & 0xffff))

    print()
    print("=" * 70)
    print("REGISTER CLOCK VERIFICATION:", "PASS" if all(results) else "FAIL")
    print("=" * 70)
