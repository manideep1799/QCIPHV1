"""
verification/test_full_cipher_api.py
=======================================

The final test: instantiate BOTH cipher.A5GMR1 (classical) and
quantum_cipher_pkg.quantum_cipher.A5GMR1Quantum (quantum) with the
SAME key/frame, using their PUBLIC APIs exactly as an end user would --
initialize(), generate_downlink(n), generate_uplink(n) -- matching the
DL/UL continuation convention this project has used since Phase 1
(verify_against_compiled_c.py / verify_against_reference.py), and
confirm bit-for-bit agreement, plus register-state agreement.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "classical_ref", "a5_gmr1"))

from cipher import A5GMR1
from quantum_cipher_pkg.quantum_cipher import A5GMR1Quantum

KEY = bytes([0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF])
FRAME_NUMBER = 42
DL_BITS = 32
UL_BITS = 32


def run():
    classical = A5GMR1(key=KEY, frame_number=FRAME_NUMBER)
    classical.initialize()
    classical_dl = classical.generate_keystream(DL_BITS)
    classical_ul = classical.generate_keystream(UL_BITS)

    quantum = A5GMR1Quantum(key=KEY, frame_number=FRAME_NUMBER)
    quantum.initialize()
    quantum_dl = quantum.generate_downlink(DL_BITS)
    quantum_ul = quantum.generate_uplink(UL_BITS)

    print(f"Classical DL: {''.join(map(str, classical_dl))}")
    print(f"Quantum   DL: {''.join(map(str, quantum_dl))}")
    print(f"Classical UL: {''.join(map(str, classical_ul))}")
    print(f"Quantum   UL: {''.join(map(str, quantum_ul))}")

    dl_match = classical_dl == quantum_dl
    ul_match = classical_ul == quantum_ul

    print()
    print(f"DL match: {dl_match}")
    print(f"UL match: {ul_match}")

    # Register-state agreement after the full DL+UL run
    reg_match = True
    for name in ("R1", "R2", "R3", "R4"):
        c_state = classical.get_register_state(name)
        q_state = quantum.get_register_state(name)
        ok = c_state == q_state
        reg_match = reg_match and ok
        print(f"  {name}: classical={c_state} quantum={q_state}  [{'OK' if ok else 'FAIL'}]")

    return dl_match and ul_match and reg_match


if __name__ == "__main__":
    ok = run()
    print()
    print("=" * 70)
    print("FULL CIPHER API TEST (classical A5GMR1 vs quantum A5GMR1Quantum):", "PASS" if ok else "FAIL")
    print("=" * 70)
