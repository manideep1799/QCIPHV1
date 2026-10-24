"""
run_all.py
============

Single-file runner for the entire A5-GMR-1 quantum reversible-circuit
verification suite. Runs every test in sequence and prints one clean
PASS/FAIL summary at the end.

USAGE:
    Place this file directly inside qgmr1_code/ (same level as blocks/,
    cycle/, reversible_init/, quantum_cipher_pkg/, verification/), next
    to your classical_ref/ folder, then run:

        python run_all.py

    No need to set PYTHONPATH manually -- this script sets it up itself,
    relative to wherever it is run from.

WHAT THIS RUNS (in order):
    1. Register clock (unconditional)          -- blocks/register_clock.py
    2. Register clock (controlled/conditional)  -- blocks/register_clock.py
    3. Majority + Equality primitives           -- blocks/primitives.py
    4. Output block                             -- blocks/output.py
    5. Full clock cycle (single + chained)      -- cycle/full_cycle.py
    6. Full initialization + keystream          -- reversible_init/full_initialization.py
    7. Full cipher public API (DL/UL)           -- quantum_cipher_pkg/quantum_cipher.py
    8. Encrypt/decrypt demo (ciphertext, not just keystream)
"""

import sys
import os
import random
import time

# ----------------------------------------------------------------------
# PATH SETUP -- adjust CLASSICAL_REF_PATH below if your classical_ref
# folder is somewhere other than right next to this file.
# ----------------------------------------------------------------------
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(THIS_DIR)  # the folder containing qgmr1_code/

CLASSICAL_REF_PATH = os.path.join(PROJECT_ROOT, "classical_ref", "a5_gmr1")

sys.path.insert(0, THIS_DIR)
sys.path.insert(0, CLASSICAL_REF_PATH)

if not os.path.exists(os.path.join(CLASSICAL_REF_PATH, "cipher.py")):
    print(f"ERROR: could not find cipher.py at {CLASSICAL_REF_PATH}")
    print("Edit CLASSICAL_REF_PATH at the top of this file to point at")
    print("your unzipped a5_gmr1/ folder (the one containing cipher.py).")
    sys.exit(1)

from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator

from blocks.register_clock import append_register_clock, append_controlled_register_clock, check_precondition
from blocks.primitives import append_majority, append_unmajority, append_equality, append_unequality
from blocks.output import append_output_block
from cycle.layout import CipherLayout
from cycle.full_cycle import append_full_cycle
from reversible_init.full_initialization import append_full_initialization
from quantum_cipher_pkg.quantum_cipher import A5GMR1Quantum

from registers import LFSR
from majority import majority as classical_majority
from clocking import ClockController
from output import OutputFunction
from initialization import Initializer
from cipher import A5GMR1
from constants import (
    R1_LENGTH, R1_TAPS, R2_LENGTH, R2_TAPS,
    R3_LENGTH, R3_TAPS, R4_LENGTH, R4_TAPS,
    CONTROL_BIT_POSITIONS,
    R1_OUTPUT_MAJORITY_BITS, R1_OUTPUT_XOR_BIT,
    R2_OUTPUT_MAJORITY_BITS, R2_OUTPUT_XOR_BIT,
    R3_OUTPUT_MAJORITY_BITS, R3_OUTPUT_XOR_BIT,
    KEY_LENGTH_BITS, MIXING_ROUNDS,
)

STABILIZER_SIM = AerSimulator(method="stabilizer")
MPS_SIM = AerSimulator(method="matrix_product_state")


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

RESULTS = []


def record(name, ok):
    RESULTS.append((name, ok))
    print(f"  ==> {name}: {'PASS' if ok else 'FAIL'}")
    print()


# ========================================================================
# 1. Register clock (unconditional)
# ========================================================================
def test_register_clock():
    print("=" * 70)
    print("1. REGISTER CLOCK (unconditional) -- vs registers.LFSR.clock()")
    print("=" * 70)

    for name, L, taps_mask in [("R1", R1_LENGTH, R1_TAPS), ("R2", R2_LENGTH, R2_TAPS),
                                 ("R3", R3_LENGTH, R3_TAPS), ("R4", R4_LENGTH, R4_TAPS)]:
        T = tap_positions(taps_mask, L)
        check_precondition(L, T)
    print("  Precondition (L-1 in T) verified for all 4 real registers.")

    all_pass = True
    real_registers = {"R1": (R1_LENGTH, R1_TAPS), "R2": (R2_LENGTH, R2_TAPS),
                       "R3": (R3_LENGTH, R3_TAPS), "R4": (R4_LENGTH, R4_TAPS)}
    rng = random.Random(1234)
    for name, (L, taps_mask) in real_registers.items():
        taps = tap_positions(taps_mask, L)
        mismatches = 0
        n_trials = 300
        for _ in range(n_trials):
            state = rng.randrange(1 << L)
            qc = QuantumCircuit(L, L)
            for i in range(L):
                if (state >> i) & 1:
                    qc.x(i)
            append_register_clock(qc, L, taps)
            qc.measure(range(L), range(L))
            result = STABILIZER_SIM.run(qc, shots=1).result()
            (bs, _), = result.get_counts().items()
            bits = bs[::-1]
            q_state = sum((1 << i) for i in range(L) if bits[i] == "1")

            lfsr = LFSR(length=L, taps=taps_mask)
            lfsr.set_state(state)
            lfsr.clock()
            c_state = lfsr.get_state()
            if q_state != c_state:
                mismatches += 1
        print(f"  {name} (L={L}): {n_trials - mismatches}/{n_trials} trials passed")
        all_pass = all_pass and (mismatches == 0)

    record("Register clock (unconditional)", all_pass)
    return all_pass


# ========================================================================
# 2. Register clock (controlled)
# ========================================================================
def test_controlled_register_clock():
    print("=" * 70)
    print("2. REGISTER CLOCK (controlled) -- both control=0 and control=1")
    print("=" * 70)

    all_pass = True
    real_registers = {"R1": (R1_LENGTH, R1_TAPS), "R2": (R2_LENGTH, R2_TAPS),
                       "R3": (R3_LENGTH, R3_TAPS), "R4": (R4_LENGTH, R4_TAPS)}
    rng = random.Random(5678)
    for name, (L, taps_mask) in real_registers.items():
        taps = tap_positions(taps_mask, L)
        mismatches = 0
        n_trials = 150
        for _ in range(n_trials):
            state = rng.randrange(1 << L)
            control = rng.randrange(2)
            qc = QuantumCircuit(L + 1, L + 1)
            for i in range(L):
                if (state >> i) & 1:
                    qc.x(i)
            ctrl = L
            if control:
                qc.x(ctrl)
            append_controlled_register_clock(qc, L, taps, control=ctrl)
            qc.measure(range(L + 1), range(L + 1))
            result = MPS_SIM.run(qc, shots=1).result()
            (bs, _), = result.get_counts().items()
            bits = bs[::-1]
            q_state = sum((1 << i) for i in range(L) if bits[i] == "1")

            if control:
                lfsr = LFSR(length=L, taps=taps_mask)
                lfsr.set_state(state)
                lfsr.clock()
                expected = lfsr.get_state()
            else:
                expected = state
            if q_state != expected:
                mismatches += 1
        print(f"  {name} (L={L}): {n_trials - mismatches}/{n_trials} trials passed")
        all_pass = all_pass and (mismatches == 0)

    record("Register clock (controlled)", all_pass)
    return all_pass


# ========================================================================
# 3. Majority + Equality primitives
# ========================================================================
def test_primitives():
    print("=" * 70)
    print("3. MAJORITY + EQUALITY PRIMITIVES -- exhaustive")
    print("=" * 70)

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
                result = MPS_SIM.run(qc, shots=1).result()
                (bs, _), = result.get_counts().items()
                bits = bs[::-1]
                out_val = int(bits[3])
                expected = classical_majority(a, b, c)
                if out_val != expected:
                    all_pass = False
    print(f"  Majority: 8/8 combinations checked")

    for x in (0, 1):
        for y in (0, 1):
            qc = QuantumCircuit(3, 3)
            if x: qc.x(0)
            if y: qc.x(1)
            append_equality(qc, 0, 1, 2)
            qc.measure(range(3), range(3))
            result = STABILIZER_SIM.run(qc, shots=1).result()
            (bs, _), = result.get_counts().items()
            bits = bs[::-1]
            out_val = int(bits[2])
            expected = int(x == y)
            if out_val != expected:
                all_pass = False
    print(f"  Equality: 4/4 combinations checked")

    record("Majority + Equality primitives", all_pass)
    return all_pass


# ========================================================================
# 4. Output block
# ========================================================================
def test_output_block():
    print("=" * 70)
    print("4. OUTPUT BLOCK -- vs output.OutputFunction, real register lengths")
    print("=" * 70)

    R1_OFFSET, R2_OFFSET = 0, R1_LENGTH
    R3_OFFSET = R1_LENGTH + R2_LENGTH
    M1, M2, M3 = R3_OFFSET + R3_LENGTH, R3_OFFSET + R3_LENGTH + 1, R3_OFFSET + R3_LENGTH + 2
    OUT_Q = M3 + 1
    KS = OUT_Q + 1
    TOTAL = KS + 1

    specs = [
        (tuple(R1_OFFSET + b for b in R1_OUTPUT_MAJORITY_BITS), R1_OFFSET + R1_OUTPUT_XOR_BIT),
        (tuple(R2_OFFSET + b for b in R2_OUTPUT_MAJORITY_BITS), R2_OFFSET + R2_OUTPUT_XOR_BIT),
        (tuple(R3_OFFSET + b for b in R3_OUTPUT_MAJORITY_BITS), R3_OFFSET + R3_OUTPUT_XOR_BIT),
    ]

    all_pass = True
    count = 0
    for r1c in range(16):
        for r2c in range(16):
            for r3c in range(16):
                qc = QuantumCircuit(TOTAL, TOTAL)
                combos = [r1c, r2c, r3c]
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

                append_output_block(qc, specs, [M1, M2, M3], OUT_Q, KS)
                qc.measure(range(TOTAL), range(TOTAL))
                result = MPS_SIM.run(qc, shots=1).result()
                (bs, _), = result.get_counts().items()
                bits = bs[::-1]
                q_ks = int(bits[KS])
                ancillas_clean = all(int(bits[q]) == 0 for q in (M1, M2, M3, OUT_Q))

                r1 = LFSR(length=R1_LENGTH, taps=0)
                r2 = LFSR(length=R2_LENGTH, taps=0)
                r3 = LFSR(length=R3_LENGTH, taps=0)
                for pos, val in bit_dicts[0].items():
                    if val: r1.set_bit(pos, 1)
                for pos, val in bit_dicts[1].items():
                    if val: r2.set_bit(pos, 1)
                for pos, val in bit_dicts[2].items():
                    if val: r3.set_bit(pos, 1)
                expected = OutputFunction({"R1": r1, "R2": r2, "R3": r3}).compute().output_bit

                if q_ks != expected or not ancillas_clean:
                    all_pass = False
                count += 1
    print(f"  {count}/4096 combinations checked (exhaustive, real register lengths)")

    record("Output block", all_pass)
    return all_pass


# ========================================================================
# 5. Full clock cycle (single + chained)
# ========================================================================
def test_full_cycle():
    print("=" * 70)
    print("5. FULL CLOCK CYCLE -- single + chained (2/5/10 cycles)")
    print("=" * 70)

    def build_layout():
        return CipherLayout(REGISTER_LENGTHS, REGISTER_TAPS, CONTROL_BIT_POSITIONS, OUTPUT_SPECS)

    rng = random.Random(2026)
    all_pass = True

    # single cycle, 10 trials
    for _ in range(10):
        states = {name: rng.randrange(1 << REGISTER_LENGTHS[name]) for name in ("R1", "R2", "R3", "R4")}
        layout = build_layout()
        total = layout.total_qubits(n_keystream=1)
        ks_q = layout.keystream_qubit(0)
        qc = QuantumCircuit(total, total)
        for name in ("R1", "R2", "R3", "R4"):
            base = layout.register_offset[name]
            for i in range(REGISTER_LENGTHS[name]):
                if (states[name] >> i) & 1:
                    qc.x(base + i)
        append_full_cycle(qc, layout, include_output=True, keystream_qubit=ks_q)
        qc.measure(range(total), range(total))
        result = MPS_SIM.run(qc, shots=1).result()
        (bs, _), = result.get_counts().items()
        bits = bs[::-1]

        regs = {
            "R1": LFSR(length=R1_LENGTH, taps=R1_TAPS), "R2": LFSR(length=R2_LENGTH, taps=R2_TAPS),
            "R3": LFSR(length=R3_LENGTH, taps=R3_TAPS),
            "R4": LFSR(length=R4_LENGTH, taps=R4_TAPS, clock_bit_positions=CONTROL_BIT_POSITIONS),
        }
        for name, reg in regs.items():
            reg.set_state(states[name])
        ClockController(regs).step()
        expected_ks = OutputFunction(regs).compute().output_bit

        q_ks = int(bits[ks_q])
        scratch_clean = all(int(bits[q]) == 0 for q in
                             (layout.maj, layout.clk1, layout.clk2, layout.clk3, layout.m1, layout.m2, layout.m3, layout.out))
        states_match = all(
            sum((1 << i) for i in range(REGISTER_LENGTHS[n]) if bits[layout.register_offset[n] + i] == "1") == regs[n].get_state()
            for n in ("R1", "R2", "R3", "R4")
        )
        if q_ks != expected_ks or not scratch_clean or not states_match:
            all_pass = False
    print(f"  Single cycle: 10/10 trials checked (states + keystream + ancilla cleanliness)")

    # chained cycles
    for n_cycles in (2, 5, 10):
        chain_pass = True
        for _ in range(5):
            states = {name: rng.randrange(1 << REGISTER_LENGTHS[name]) for name in ("R1", "R2", "R3", "R4")}
            layout = build_layout()
            total = layout.total_qubits(n_cycles)
            qc = QuantumCircuit(total, total)
            for name in ("R1", "R2", "R3", "R4"):
                base = layout.register_offset[name]
                for i in range(REGISTER_LENGTHS[name]):
                    if (states[name] >> i) & 1:
                        qc.x(base + i)
            for c in range(n_cycles):
                append_full_cycle(qc, layout, include_output=True, keystream_qubit=layout.keystream_qubit(c))
            qc.measure(range(total), range(total))
            result = MPS_SIM.run(qc, shots=1).result()
            (bs, _), = result.get_counts().items()
            bits = bs[::-1]
            q_ks = [int(bits[layout.keystream_qubit(c)]) for c in range(n_cycles)]

            regs = {
                "R1": LFSR(length=R1_LENGTH, taps=R1_TAPS), "R2": LFSR(length=R2_LENGTH, taps=R2_TAPS),
                "R3": LFSR(length=R3_LENGTH, taps=R3_TAPS),
                "R4": LFSR(length=R4_LENGTH, taps=R4_TAPS, clock_bit_positions=CONTROL_BIT_POSITIONS),
            }
            for name, reg in regs.items():
                reg.set_state(states[name])
            controller = ClockController(regs)
            output_fn = OutputFunction(regs)
            expected_ks = []
            for _ in range(n_cycles):
                controller.step()
                expected_ks.append(output_fn.compute().output_bit)

            if q_ks != expected_ks:
                chain_pass = False
        print(f"  Chained ({n_cycles} cycles): 5/5 trials checked")
        all_pass = all_pass and chain_pass

    record("Full clock cycle (single + chained)", all_pass)
    return all_pass


# ========================================================================
# 6. Full initialization + keystream
# ========================================================================
def test_initialization():
    print("=" * 70)
    print("6. FULL INITIALIZATION + KEYSTREAM -- real cipher scale")
    print("=" * 70)

    layout = CipherLayout(REGISTER_LENGTHS, REGISTER_TAPS, CONTROL_BIT_POSITIONS, OUTPUT_SPECS, key_length=KEY_LENGTH_BITS)
    n_bits = 32
    total = layout.total_qubits(n_keystream=n_bits)
    print(f"  Total qubits: {total}")

    qc = QuantumCircuit(total, total)
    append_full_initialization(qc, layout, KEY, FRAME_NUMBER, warmup_rounds=MIXING_ROUNDS)
    for i in range(n_bits):
        append_full_cycle(qc, layout, include_output=True, keystream_qubit=layout.keystream_qubit(i))
    qc.measure(range(total), range(total))

    t0 = time.time()
    result = MPS_SIM.run(qc, shots=1).result()
    t1 = time.time()
    (bs, _), = result.get_counts().items()
    bits = bs[::-1]
    quantum_ks = "".join(str(int(bits[layout.keystream_qubit(i)])) for i in range(n_bits))

    regs = {
        "R1": LFSR(length=R1_LENGTH, taps=R1_TAPS), "R2": LFSR(length=R2_LENGTH, taps=R2_TAPS),
        "R3": LFSR(length=R3_LENGTH, taps=R3_TAPS),
        "R4": LFSR(length=R4_LENGTH, taps=R4_TAPS, clock_bit_positions=CONTROL_BIT_POSITIONS),
    }
    Initializer(regs).initialize(KEY, FRAME_NUMBER)
    controller = ClockController(regs)
    output_fn = OutputFunction(regs)
    classical_bits = []
    for _ in range(n_bits):
        controller.step()
        classical_bits.append(output_fn.compute().output_bit)
    classical_ks = "".join(map(str, classical_bits))

    scratch_clean = all(int(bits[q]) == 0 for q in
                         (layout.maj, layout.clk1, layout.clk2, layout.clk3, layout.m1, layout.m2, layout.m3, layout.out))

    print(f"  Quantum:   {quantum_ks}")
    print(f"  Classical: {classical_ks}")
    print(f"  Simulation time: {t1-t0:.2f}s")
    print(f"  Scratch ancillas all clean: {scratch_clean}")

    ok = (quantum_ks == classical_ks) and scratch_clean
    record("Full initialization + keystream", ok)
    return ok


# ========================================================================
# 7. Full cipher public API (DL/UL)
# ========================================================================
def test_full_cipher_api():
    print("=" * 70)
    print("7. FULL CIPHER API -- classical A5GMR1 vs quantum A5GMR1Quantum (DL/UL)")
    print("=" * 70)

    DL_BITS, UL_BITS = 32, 32

    classical = A5GMR1(key=KEY, frame_number=FRAME_NUMBER)
    classical.initialize()
    classical_dl = classical.generate_keystream(DL_BITS)
    classical_ul = classical.generate_keystream(UL_BITS)

    quantum = A5GMR1Quantum(key=KEY, frame_number=FRAME_NUMBER)
    quantum.initialize()
    quantum_dl = quantum.generate_downlink(DL_BITS)
    quantum_ul = quantum.generate_uplink(UL_BITS)

    print(f"  Classical DL: {''.join(map(str, classical_dl))}")
    print(f"  Quantum   DL: {''.join(map(str, quantum_dl))}")
    print(f"  Classical UL: {''.join(map(str, classical_ul))}")
    print(f"  Quantum   UL: {''.join(map(str, quantum_ul))}")

    dl_match = classical_dl == quantum_dl
    ul_match = classical_ul == quantum_ul

    reg_match = True
    for name in ("R1", "R2", "R3", "R4"):
        c_state = classical.get_register_state(name)
        q_state = quantum.get_register_state(name)
        if c_state != q_state:
            reg_match = False
        print(f"  {name}: classical={c_state} quantum={q_state}  [{'OK' if c_state == q_state else 'FAIL'}]")

    ok = dl_match and ul_match and reg_match
    record("Full cipher API (DL/UL)", ok)
    return ok, classical, quantum


# ========================================================================
# 8. Encrypt/decrypt demo (ciphertext, not just keystream)
# ========================================================================
def test_encrypt_decrypt():
    print("=" * 70)
    print("8. ENCRYPT/DECRYPT DEMO -- ciphertext = plaintext XOR keystream")
    print("=" * 70)

    message = "HELLO"
    plaintext_bits = []
    for ch in message:
        byte = ord(ch)
        plaintext_bits.extend([(byte >> i) & 1 for i in range(7, -1, -1)])

    classical = A5GMR1(key=KEY, frame_number=FRAME_NUMBER)
    classical.initialize()
    classical_ciphertext = classical.encrypt(plaintext_bits)

    quantum = A5GMR1Quantum(key=KEY, frame_number=FRAME_NUMBER)
    quantum.initialize()
    quantum_ciphertext = quantum.encrypt(plaintext_bits)

    print(f"  Plaintext:            '{message}'  ({len(plaintext_bits)} bits)")
    print(f"  Classical ciphertext: {''.join(map(str, classical_ciphertext))}")
    print(f"  Quantum ciphertext:   {''.join(map(str, quantum_ciphertext))}")

    ciphertext_match = classical_ciphertext == quantum_ciphertext

    # decrypt with fresh instances (same key/frame) and confirm round-trip
    classical2 = A5GMR1(key=KEY, frame_number=FRAME_NUMBER)
    classical2.initialize()
    recovered = classical2.decrypt(classical_ciphertext)
    recovered_message = "".join(
        chr(int("".join(map(str, recovered[i:i + 8])), 2)) for i in range(0, len(recovered), 8)
    )
    print(f"  Decrypted back to:    '{recovered_message}'")

    ok = ciphertext_match and (recovered_message == message)
    record("Encrypt/decrypt (ciphertext) demo", ok)
    return ok


# ========================================================================
# RUN EVERYTHING
# ========================================================================
if __name__ == "__main__":
    print()
    print("#" * 70)
    print("# A5-GMR-1 QUANTUM REVERSIBLE CIRCUIT -- FULL VERIFICATION SUITE")
    print("#" * 70)
    print()

    t_start = time.time()

    test_register_clock()
    test_controlled_register_clock()
    test_primitives()
    test_output_block()
    test_full_cycle()
    test_initialization()
    _, _, _ = test_full_cipher_api()
    test_encrypt_decrypt()

    t_end = time.time()

    print("#" * 70)
    print("# SUMMARY")
    print("#" * 70)
    all_ok = True
    for name, ok in RESULTS:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")
        all_ok = all_ok and ok
    print()
    print(f"Total time: {t_end - t_start:.1f}s")
    print()
    print("=" * 70)
    print("OVERALL RESULT:", "ALL TESTS PASSED" if all_ok else "SOME TESTS FAILED")
    print("=" * 70)

    sys.exit(0 if all_ok else 1)