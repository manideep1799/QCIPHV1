"""
verification/test_controlled_register_clock.py
==================================================

Verifies append_controlled_register_clock: control=1 must match
classical LFSR.clock(); control=0 must be the identity. This is the
piece R1/R2/R3's irregular clocking actually uses.

Uses Aer's matrix_product_state method (Toffoli/CSWAP present, not
Clifford-only) -- confirmed cheap here because these gates only ever
act on computational basis states, never creating real entanglement.
"""

import sys
import os
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "classical_ref", "a5_gmr1"))

from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator

from blocks.register_clock import append_controlled_register_clock
from registers import LFSR
from constants import (
    R1_LENGTH, R1_TAPS, R2_LENGTH, R2_TAPS,
    R3_LENGTH, R3_TAPS, R4_LENGTH, R4_TAPS,
)

SIM = AerSimulator(method="matrix_product_state")


def tap_positions(taps: int, length: int):
    return sorted([i for i in range(length) if (taps >> i) & 1])


def run_one_trial(L: int, taps: list, initial_state: int, control: int):
    qc = QuantumCircuit(L + 1, L + 1)
    for i in range(L):
        if (initial_state >> i) & 1:
            qc.x(i)
    ctrl = L
    if control:
        qc.x(ctrl)
    append_controlled_register_clock(qc, L, taps, control=ctrl)
    qc.measure(range(L + 1), range(L + 1))

    result = SIM.run(qc, shots=1).result()
    (bitstring, _), = result.get_counts().items()
    bits = bitstring[::-1]
    quantum_state = 0
    for i in range(L):
        if bits[i] == "1":
            quantum_state |= (1 << i)
    quantum_control_readback = int(bits[ctrl])

    if control:
        lfsr = LFSR(length=L, taps=sum(1 << t for t in taps))
        lfsr.set_state(initial_state)
        lfsr.clock()
        expected_state = lfsr.get_state()
    else:
        expected_state = initial_state

    ok = (quantum_state == expected_state) and (quantum_control_readback == control)
    return ok, quantum_state, expected_state


def exhaustive_test(L, taps, label):
    print(f"--- Exhaustive (both control values): {label} (L={L}, taps={taps}) ---")
    all_pass = True
    total = 0
    for control in (0, 1):
        for state in range(1 << L):
            ok, q, e = run_one_trial(L, taps, state, control)
            all_pass = all_pass and ok
            total += 1
            if not ok:
                print(f"  FAIL control={control} state={state}: quantum={q} expected={e}")
    print(f"  {total}/{total} checked. Result:", "ALL PASS" if all_pass else "FAILURE")
    return all_pass


def random_sample_test(L, taps, label, n_trials, seed):
    print(f"--- Random sample: {label} (L={L}), {n_trials} trials ---")
    rng = random.Random(seed)
    all_pass = True
    for _ in range(n_trials):
        state = rng.randrange(1 << L)
        control = rng.randrange(2)
        ok, q, e = run_one_trial(L, taps, state, control)
        all_pass = all_pass and ok
        if not ok:
            print(f"  FAIL control={control} state={state}: quantum={q} expected={e}")
    print(f"  {n_trials}/{n_trials} checked. Result:", "ALL PASS" if all_pass else "FAILURE")
    return all_pass


if __name__ == "__main__":
    results = []

    results.append(exhaustive_test(4, [0, 1, 2, 3], "small L=4"))
    results.append(exhaustive_test(5, [0, 1, 3, 4], "small L=5"))

    print()
    print("=" * 70)
    print("REAL CIPHER REGISTER LENGTHS -- large random sample (1000 trials each)")
    print("=" * 70)

    real_registers = {
        "R1": (R1_LENGTH, R1_TAPS), "R2": (R2_LENGTH, R2_TAPS),
        "R3": (R3_LENGTH, R3_TAPS), "R4": (R4_LENGTH, R4_TAPS),
    }
    for name, (length, taps_mask) in real_registers.items():
        positions = tap_positions(taps_mask, length)
        results.append(random_sample_test(length, positions, f"REAL {name}", n_trials=1000, seed=hash(name) & 0xffff))

    print()
    print("=" * 70)
    print("CONTROLLED REGISTER CLOCK VERIFICATION:", "PASS" if all(results) else "FAIL")
    print("=" * 70)
