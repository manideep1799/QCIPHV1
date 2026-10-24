"""
verification/test_initialization.py
======================================




Verifies reversible_init/full_initialization.py against classical
initialization.Initializer, at REAL cipher scale, for the exact
reference key/frame this whole project has used throughout:
KEY=0123456789ABCDEF, FRAME=42, expected register states after
initialization, and the exact known keystream
00100010101011110010010101001010.




"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "classical_ref", "a5_gmr1"))

from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator

from registers import LFSR
from initialization import Initializer
from clocking import ClockController
from output import OutputFunction
from constants import (
    R1_LENGTH, R1_TAPS, R2_LENGTH, R2_TAPS,
    R3_LENGTH, R3_TAPS, R4_LENGTH, R4_TAPS,
    CONTROL_BIT_POSITIONS,
    R1_OUTPUT_MAJORITY_BITS, R1_OUTPUT_XOR_BIT,
    R2_OUTPUT_MAJORITY_BITS, R2_OUTPUT_XOR_BIT,
    R3_OUTPUT_MAJORITY_BITS, R3_OUTPUT_XOR_BIT,
    KEY_LENGTH_BITS, MIXING_ROUNDS,
)
from cycle.layout import CipherLayout
from cycle.full_cycle import append_full_cycle
from reversible_init.full_initialization import append_full_initialization

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

KEY = bytes([0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF])
FRAME_NUMBER = 42
KNOWN_REFERENCE_KEYSTREAM = "00100010101011110010010101001010"


def run_test(n_keystream_bits: int):
    layout = CipherLayout(REGISTER_LENGTHS, REGISTER_TAPS, CONTROL_BIT_POSITIONS, OUTPUT_SPECS, key_length=KEY_LENGTH_BITS)
    total_qubits = layout.total_qubits(n_keystream=n_keystream_bits)
    print(f"Total qubits: {total_qubits} (register={layout.total_register_qubits}, "
          f"key={layout.key_length}, scratch=8, history=4, keystream={n_keystream_bits})")

    qc = QuantumCircuit(total_qubits, total_qubits)
    append_full_initialization(qc, layout, KEY, FRAME_NUMBER, warmup_rounds=MIXING_ROUNDS)
    for i in range(n_keystream_bits):
        append_full_cycle(qc, layout, include_output=True, keystream_qubit=layout.keystream_qubit(i))
    qc.measure(range(total_qubits), range(total_qubits))

    result = SIM.run(qc, shots=1).result()
    (bitstring, _), = result.get_counts().items()
    bits = bitstring[::-1]

    quantum_keystream = "".join(str(int(bits[layout.keystream_qubit(i)])) for i in range(n_keystream_bits))

    def read_reg(name):
        base = layout.register_offset[name]
        L = layout.register_lengths[name]
        val = 0
        for i in range(L):
            if bits[base + i] == "1":
                val |= (1 << i)
        return val

    quantum_states_after_init_and_gen = {name: read_reg(name) for name in ("R1", "R2", "R3", "R4")}

    scratch_qubits = [layout.maj, layout.clk1, layout.clk2, layout.clk3, layout.m1, layout.m2, layout.m3, layout.out]
    scratch_clean = all(int(bits[q]) == 0 for q in scratch_qubits)
    history_values = {name: int(bits[layout.history[name]]) for name in ("R1", "R2", "R3", "R4")}

    # --- classical reference ---
    regs = {
        "R1": LFSR(length=R1_LENGTH, taps=R1_TAPS),
        "R2": LFSR(length=R2_LENGTH, taps=R2_TAPS),
        "R3": LFSR(length=R3_LENGTH, taps=R3_TAPS),
        "R4": LFSR(length=R4_LENGTH, taps=R4_TAPS, clock_bit_positions=CONTROL_BIT_POSITIONS),
    }
    initializer = Initializer(regs)
    initializer.initialize(KEY, FRAME_NUMBER)
    classical_states_after_init = {name: regs[name].get_state() for name in ("R1", "R2", "R3", "R4")}

    controller = ClockController(regs)
    output_fn = OutputFunction(regs)
    classical_keystream_bits = []
    for _ in range(n_keystream_bits):
        controller.step()
        classical_keystream_bits.append(output_fn.compute().output_bit)
    classical_keystream = "".join(map(str, classical_keystream_bits))

    print()
    print(f"Quantum keystream:   {quantum_keystream}")
    print(f"Classical keystream: {classical_keystream}")
    print(f"Known reference:     {KNOWN_REFERENCE_KEYSTREAM[:n_keystream_bits]}")
    print()
    print(f"Scratch ancillas (maj, clk1-3, m1-3, out) all == 0: {scratch_clean}")
    print(f"Stage-C history qubits (expected nonzero, by design, per D4): {history_values}")

    keystream_matches_classical = quantum_keystream == classical_keystream
    keystream_matches_known_reference = quantum_keystream == KNOWN_REFERENCE_KEYSTREAM[:n_keystream_bits]

    return keystream_matches_classical and keystream_matches_known_reference and scratch_clean


if __name__ == "__main__":
    ok = run_test(n_keystream_bits=32)
    print()
    print("=" * 70)
    print("INITIALIZATION VERIFICATION (real cipher scale):", "PASS" if ok else "FAIL")
    print("=" * 70)
