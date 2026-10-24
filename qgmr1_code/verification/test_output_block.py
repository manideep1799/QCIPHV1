"""
verification/test_output_block.py
====================================

Verifies blocks/output.py against classical output.OutputFunction, at
REAL register lengths (R1=19, R2=22, R3=23) and real tap positions.
Exhaustive over all 16^3 = 4096 combinations of the 4 relevant bits per
register (output depends only on these positions). Also confirms all
scratch ancillas (m_1, m_2, m_3, out) return to |0>.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "classical_ref", "a5_gmr1"))

from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator

from blocks.output import append_output_block
from registers import LFSR
from output import OutputFunction
from constants import (
    R1_LENGTH, R1_OUTPUT_MAJORITY_BITS, R1_OUTPUT_XOR_BIT,
    R2_LENGTH, R2_OUTPUT_MAJORITY_BITS, R2_OUTPUT_XOR_BIT,
    R3_LENGTH, R3_OUTPUT_MAJORITY_BITS, R3_OUTPUT_XOR_BIT,
)

SIM = AerSimulator(method="matrix_product_state")

R1_OFFSET = 0
R2_OFFSET = R1_LENGTH
R3_OFFSET = R1_LENGTH + R2_LENGTH
M1, M2, M3 = R3_OFFSET + R3_LENGTH, R3_OFFSET + R3_LENGTH + 1, R3_OFFSET + R3_LENGTH + 2
OUT = M3 + 1
KEYSTREAM = OUT + 1
TOTAL_QUBITS = KEYSTREAM + 1

REGISTER_OUTPUT_SPECS = [
    (tuple(R1_OFFSET + b for b in R1_OUTPUT_MAJORITY_BITS), R1_OFFSET + R1_OUTPUT_XOR_BIT),
    (tuple(R2_OFFSET + b for b in R2_OUTPUT_MAJORITY_BITS), R2_OFFSET + R2_OUTPUT_XOR_BIT),
    (tuple(R3_OFFSET + b for b in R3_OUTPUT_MAJORITY_BITS), R3_OFFSET + R3_OUTPUT_XOR_BIT),
]
M_ANCILLAS = [M1, M2, M3]


def classical_output_bit(r1_bits: dict, r2_bits: dict, r3_bits: dict) -> int:
    r1 = LFSR(length=R1_LENGTH, taps=0)
    r2 = LFSR(length=R2_LENGTH, taps=0)
    r3 = LFSR(length=R3_LENGTH, taps=0)
    for pos, val in r1_bits.items():
        if val:
            r1.set_bit(pos, 1)
    for pos, val in r2_bits.items():
        if val:
            r2.set_bit(pos, 1)
    for pos, val in r3_bits.items():
        if val:
            r3.set_bit(pos, 1)
    output_fn = OutputFunction({"R1": r1, "R2": r2, "R3": r3})
    return output_fn.compute().output_bit


def run_one_trial(r1_combo: int, r2_combo: int, r3_combo: int):
    qc = QuantumCircuit(TOTAL_QUBITS, TOTAL_QUBITS)

    combos = [r1_combo, r2_combo, r3_combo]
    offsets = [R1_OFFSET, R2_OFFSET, R3_OFFSET]
    bit_dicts = []
    for combo, offset, (maj_bits, xor_bit) in zip(
        combos, offsets,
        [(R1_OUTPUT_MAJORITY_BITS, R1_OUTPUT_XOR_BIT),
         (R2_OUTPUT_MAJORITY_BITS, R2_OUTPUT_XOR_BIT),
         (R3_OUTPUT_MAJORITY_BITS, R3_OUTPUT_XOR_BIT)]
    ):
        values = [(combo >> i) & 1 for i in range(4)]
        bit_dict = {}
        for i, b in enumerate(maj_bits):
            bit_dict[b] = values[i]
            if values[i]:
                qc.x(offset + b)
        bit_dict[xor_bit] = values[3]
        if values[3]:
            qc.x(offset + xor_bit)
        bit_dicts.append(bit_dict)

    append_output_block(qc, REGISTER_OUTPUT_SPECS, M_ANCILLAS, OUT, KEYSTREAM)
    qc.measure(range(TOTAL_QUBITS), range(TOTAL_QUBITS))

    result = SIM.run(qc, shots=1).result()
    (bitstring, _), = result.get_counts().items()
    bits = bitstring[::-1]

    quantum_keystream = int(bits[KEYSTREAM])
    ancillas_clean = all(int(bits[q]) == 0 for q in (M1, M2, M3, OUT))
    expected_keystream = classical_output_bit(*bit_dicts)

    return quantum_keystream == expected_keystream, ancillas_clean, quantum_keystream, expected_keystream


if __name__ == "__main__":
    print("=== Exhaustive Output block verification: 16^3 = 4096 combinations ===")
    print("    (real R1=19, R2=22, R3=23 register lengths and real tap positions)")
    all_keystream_ok = True
    all_ancillas_clean = True
    count = 0
    for r1c in range(16):
        for r2c in range(16):
            for r3c in range(16):
                keystream_ok, ancillas_clean, q, e = run_one_trial(r1c, r2c, r3c)
                all_keystream_ok = all_keystream_ok and keystream_ok
                all_ancillas_clean = all_ancillas_clean and ancillas_clean
                count += 1
                if not keystream_ok:
                    print(f"  KEYSTREAM FAIL: r1={r1c:04b} r2={r2c:04b} r3={r3c:04b} quantum={q} expected={e}")
                if not ancillas_clean:
                    print(f"  ANCILLA-LEAK FAIL: r1={r1c:04b} r2={r2c:04b} r3={r3c:04b}")

    print(f"  {count}/4096 combinations checked")
    print("  Keystream bit correctness:", "ALL PASS" if all_keystream_ok else "FAILURE DETECTED")
    print("  Ancilla uncomputation (m1,m2,m3,out all -> |0>):", "ALL CLEAN" if all_ancillas_clean else "LEAK DETECTED")
    print()
    print("=" * 50)
    print("OUTPUT BLOCK VERIFICATION:", "PASS" if (all_keystream_ok and all_ancillas_clean) else "FAIL")
    print("=" * 50)
