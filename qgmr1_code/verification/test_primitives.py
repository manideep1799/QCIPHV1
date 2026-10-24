"""
verification/test_primitives.py
==================================

Exhaustive verification of blocks/primitives.py against the classical
majority.majority() function and Python's `==` (what clocking.py
actually uses for its clock-decision comparison), plus forward/inverse
identity checks.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "classical_ref", "a5_gmr1"))

from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator

from blocks.primitives import append_majority, append_unmajority, append_equality, append_unequality
from majority import majority as classical_majority

SIM = AerSimulator(method="stabilizer")  # equality is Clifford; majority needs statevector-equiv, see below


def test_majority():
    print("=== Majority: exhaustive truth table + forward/inverse ===")
    all_pass = True
    for a in (0, 1):
        for b in (0, 1):
            for c in (0, 1):
                qc = QuantumCircuit(4, 4)
                if a: qc.x(0)
                if b: qc.x(1)
                if c: qc.x(2)
                append_majority(qc, 0, 1, 2, 3)
                qc.measure(range(4), range(4))
                sim = AerSimulator(method="matrix_product_state")
                result = sim.run(qc, shots=1).result()
                (bs, _), = result.get_counts().items()
                bits = bs[::-1]
                out_val = int(bits[3])
                expected = classical_majority(a, b, c)
                ok = out_val == expected and int(bits[0]) == a and int(bits[1]) == b and int(bits[2]) == c
                all_pass = all_pass and ok
                print(f"  a={a} b={b} c={c} -> out={out_val} (expected {expected})  [{'OK' if ok else 'FAIL'}]")

                # forward/inverse
                qc2 = QuantumCircuit(4, 4)
                if a: qc2.x(0)
                if b: qc2.x(1)
                if c: qc2.x(2)
                append_majority(qc2, 0, 1, 2, 3)
                append_unmajority(qc2, 0, 1, 2, 3)
                qc2.measure(range(4), range(4))
                result2 = sim.run(qc2, shots=1).result()
                (bs2, _), = result2.get_counts().items()
                bits2 = bs2[::-1]
                identity_ok = int(bits2[3]) == 0 and int(bits2[0]) == a and int(bits2[1]) == b and int(bits2[2]) == c
                all_pass = all_pass and identity_ok
                if not identity_ok:
                    print(f"  FORWARD/INVERSE FAIL a={a} b={b} c={c}")

    print("Majority result:", "ALL PASS" if all_pass else "FAILURE")
    return all_pass


def test_equality():
    print()
    print("=== Equality: exhaustive truth table + forward/inverse ===")
    all_pass = True
    for x in (0, 1):
        for y in (0, 1):
            qc = QuantumCircuit(3, 3)
            if x: qc.x(0)
            if y: qc.x(1)
            append_equality(qc, 0, 1, 2)
            qc.measure(range(3), range(3))
            result = SIM.run(qc, shots=1).result()
            (bs, _), = result.get_counts().items()
            bits = bs[::-1]
            out_val = int(bits[2])
            expected = int(x == y)
            ok = out_val == expected and int(bits[0]) == x and int(bits[1]) == y
            all_pass = all_pass and ok
            print(f"  x={x} y={y} -> out={out_val} (expected {expected})  [{'OK' if ok else 'FAIL'}]")

            qc2 = QuantumCircuit(3, 3)
            if x: qc2.x(0)
            if y: qc2.x(1)
            append_equality(qc2, 0, 1, 2)
            append_unequality(qc2, 0, 1, 2)
            qc2.measure(range(3), range(3))
            result2 = SIM.run(qc2, shots=1).result()
            (bs2, _), = result2.get_counts().items()
            bits2 = bs2[::-1]
            identity_ok = int(bits2[2]) == 0 and int(bits2[0]) == x and int(bits2[1]) == y
            all_pass = all_pass and identity_ok
            if not identity_ok:
                print(f"  FORWARD/INVERSE FAIL x={x} y={y}")

    print("Equality result:", "ALL PASS" if all_pass else "FAILURE")
    return all_pass


if __name__ == "__main__":
    r1 = test_majority()
    r2 = test_equality()
    print()
    print("=" * 50)
    print("PRIMITIVES VERIFICATION:", "PASS" if (r1 and r2) else "FAIL")
    print("=" * 50)
