"""
verification/test_full_cycle.py
==================================

Verifies ONE complete cycle (cycle/full_cycle.py) at REAL cipher
register scale against classical clocking.ClockController.step() +
output.OutputFunction.compute() -- checking:
  - post-clock register states for R1, R2, R3, R4
  - the keystream output bit
  - that EVERY scratch ancilla (maj, clk_1..3, m_1..3, out) returns
    to |0> -- this is the exact check that failed 100% of the time
    before the Step 5/7 ordering fix.
"""

import sys
import os
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "classical_ref", "a5_gmr1"))

from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator

from registers import LFSR
from clocking import ClockController
from output import OutputFunction
from constants import (
    R1_LENGTH, R1_TAPS, R2_LENGTH, R2_TAPS,
    R3_LENGTH, R3_TAPS, R4_LENGTH, R4_TAPS,
    CONTROL_BIT_POSITIONS,
    R1_OUTPUT_MAJORITY_BITS, R1_OUTPUT_XOR_BIT,
    R2_OUTPUT_MAJORITY_BITS, R2_OUTPUT_XOR_BIT,
    R3_OUTPUT_MAJORITY_BITS, R3_OUTPUT_XOR_BIT,
)
from cycle.layout import CipherLayout
from cycle.full_cycle import append_full_cycle

SIM = AerSimulator(method="matrix_product_state")


def tap_positions(taps, length):
    return sorted([i for i in range(length) if (taps >> i) & 1])


REGISTER_LENGTHS = {"R1": R1_LENGTH, "R2": R2_LENGTH, "R3": R3_LENGTH, "R4": R4_LENGTH}
REGISTER_TAPS = {n: tap_positions(t, REGISTER_LENGTHS[n]) for n, t in
                  [("R1", R1_TAPS), ("R2", R2_TAPS), ("R3", R3_TAPS), ("R4", R4_TAPS)]}
OUTPUT_SPECS = {
    "R1": (R1_OUTPUT_MAJORITY_BITS, R1_OUTPUT_XOR_BIT),
    "R2": (R2_OUTPUT_MAJORITY_BITS, R2_OUTPUT_XOR_BIT),
    "R3": (R3_OUTPUT_MAJORITY_BITS, R3_OUTPUT_XOR_BIT),
}


def build_layout():
    return CipherLayout(REGISTER_LENGTHS, REGISTER_TAPS, CONTROL_BIT_POSITIONS, OUTPUT_SPECS)


def run_one_trial(states: dict):
    layout = build_layout()
    total_qubits = layout.total_qubits(n_keystream=1)
    ks_qubit = layout.keystream_qubit(0)

    qc = QuantumCircuit(total_qubits, total_qubits)
    for name in ("R1", "R2", "R3", "R4"):
        base = layout.register_offset[name]
        state = states[name]
        L = layout.register_lengths[name]
        for i in range(L):
            if (state >> i) & 1:
                qc.x(base + i)

    append_full_cycle(qc, layout, include_output=True, keystream_qubit=ks_qubit)
    qc.measure(range(total_qubits), range(total_qubits))

    result = SIM.run(qc, shots=1).result()
    (bitstring, _), = result.get_counts().items()
    bits = bitstring[::-1]

    def read_reg(name):
        base = layout.register_offset[name]
        L = layout.register_lengths[name]
        val = 0
        for i in range(L):
            if bits[base + i] == "1":
                val |= (1 << i)
        return val

    quantum_states = {name: read_reg(name) for name in ("R1", "R2", "R3", "R4")}
    quantum_keystream = int(bits[ks_qubit])
    scratch_qubits = {
        "maj": layout.maj, "clk1": layout.clk1, "clk2": layout.clk2, "clk3": layout.clk3,
        "m1": layout.m1, "m2": layout.m2, "m3": layout.m3, "out": layout.out,
    }
    scratch_values = {k: int(bits[v]) for k, v in scratch_qubits.items()}

    # classical reference
    regs = {
        "R1": LFSR(length=R1_LENGTH, taps=R1_TAPS),
        "R2": LFSR(length=R2_LENGTH, taps=R2_TAPS),
        "R3": LFSR(length=R3_LENGTH, taps=R3_TAPS),
        "R4": LFSR(length=R4_LENGTH, taps=R4_TAPS, clock_bit_positions=CONTROL_BIT_POSITIONS),
    }
    for name, reg in regs.items():
        reg.set_state(states[name])
    controller = ClockController(regs)
    controller.step()
    output_fn = OutputFunction(regs)
    output_trace = output_fn.compute()

    classical_states = {name: regs[name].get_state() for name in ("R1", "R2", "R3", "R4")}
    classical_keystream = output_trace.output_bit

    states_ok = quantum_states == classical_states
    keystream_ok = quantum_keystream == classical_keystream
    scratch_all_clean = all(v == 0 for v in scratch_values.values())

    return {
        "ok": states_ok and keystream_ok and scratch_all_clean,
        "states_ok": states_ok,
        "keystream_ok": keystream_ok,
        "scratch_all_clean": scratch_all_clean,
        "quantum_states": quantum_states,
        "classical_states": classical_states,
        "scratch_values": scratch_values,
    }


if __name__ == "__main__":
    random.seed(2026)
    n_trials = 30
    all_pass = True
    for trial in range(n_trials):
        states = {
            "R1": random.randrange(1 << R1_LENGTH), "R2": random.randrange(1 << R2_LENGTH),
            "R3": random.randrange(1 << R3_LENGTH), "R4": random.randrange(1 << R4_LENGTH),
        }
        r = run_one_trial(states)
        all_pass = all_pass and r["ok"]
        status = "PASS" if r["ok"] else "FAIL"
        print(f"trial {trial:2d}: states_ok={r['states_ok']} keystream_ok={r['keystream_ok']} "
              f"scratch_all_clean={r['scratch_all_clean']}  [{status}]")
        if not r["ok"]:
            print(f"    quantum:   {r['quantum_states']}")
            print(f"    classical: {r['classical_states']}")
            print(f"    scratch:   {r['scratch_values']}")

    print()
    print("=" * 70)
    print("FULL CYCLE VERIFICATION (real cipher scale):", "PASS" if all_pass else "FAIL")
    print("=" * 70)
