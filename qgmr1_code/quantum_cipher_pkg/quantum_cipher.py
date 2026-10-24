"""
cipher/quantum_cipher.py
==========================

Quantum counterpart to cipher.A5GMR1.

Mirrors the classical class's public API (initialize(), generate_keystream(),
generate_downlink()/generate_uplink(), get_register_state(), encrypt()/decrypt())
as closely as the execution model allows.

IMPORTANT DIFFERENCE FROM THE CLASSICAL CLASS: cipher.A5GMR1 is
stateful and genuinely incremental -- generate_bit() clocks the
registers by exactly one step and returns immediately. A quantum
circuit cannot be run "one gate at a time and inspected" without
either (a) measuring mid-circuit, which would be an unnecessary
detour here since nothing about this design needs genuine mid-circuit
measurement, or (b) building the complete circuit up to some point and
simulating once. This class uses (b): every call to generate_keystream()
rebuilds the FULL circuit (initialization + every cycle clocked so far,
including previous calls on this instance) and re-simulates it once,
returning only the newly requested tail of the keystream. This exactly
reproduces the classical class's observable behavior (including the
generate_downlink() -> generate_uplink() continuation convention, where
uplink continues from wherever the registers ended up after downlink)
without requiring true incremental quantum execution.

This rebuild-and-resimulate approach is only cheap because the circuit
never enters superposition (see Doc 08's stabilizer/MPS finding) --
rebuilding a few hundred rounds' worth of gates and re-simulating from
scratch is a sub-second operation at this scale, not an exponential one.

"""

import os
import sys
from typing import List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "classical_ref", "a5_gmr1"))

from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator

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


def _tap_positions(taps: int, length: int):
    return sorted([i for i in range(length) if (taps >> i) & 1])


REGISTER_LENGTHS = {"R1": R1_LENGTH, "R2": R2_LENGTH, "R3": R3_LENGTH, "R4": R4_LENGTH}
REGISTER_TAPS = {n: _tap_positions(t, REGISTER_LENGTHS[n]) for n, t in
                  [("R1", R1_TAPS), ("R2", R2_TAPS), ("R3", R3_TAPS), ("R4", R4_TAPS)]}
OUTPUT_SPECS = {
    "R1": (R1_OUTPUT_MAJORITY_BITS, R1_OUTPUT_XOR_BIT),
    "R2": (R2_OUTPUT_MAJORITY_BITS, R2_OUTPUT_XOR_BIT),
    "R3": (R3_OUTPUT_MAJORITY_BITS, R3_OUTPUT_XOR_BIT),
}

_SIM = AerSimulator(method="matrix_product_state")


class A5GMR1Quantum:
    """
    Quantum reversible-circuit implementation of the A5-GMR-1 stream
    cipher. Mirrors cipher.A5GMR1's public interface.

    :param key: The 8-byte secret session key.
    :param frame_number: The frame number, 0 <= frame_number < 2**19.
    """

    def __init__(self, key: bytes, frame_number: int) -> None:
        self._key = key
        self._frame_number = frame_number
        self._initialized = False
        self._total_keystream_bits_generated = 0
        self._cached_keystream: List[int] = []
        self._cached_register_states = {}

    def initialize(self) -> None:
        """Marks the cipher ready for use. The actual init circuit is
        built lazily on the first generate_keystream() call, since a
        circuit with zero keystream cycles has nothing to simulate."""
        self._initialized = True
        self._total_keystream_bits_generated = 0
        self._cached_keystream = []
        self._cached_register_states = {}

    def _require_initialized(self) -> None:
        if not self._initialized:
            raise RuntimeError("A5GMR1Quantum.initialize() must be called before use")

    def _run_full_circuit(self, total_keystream_bits: int):
        """Build and simulate init + `total_keystream_bits` cycles from
        scratch. Returns (keystream_bits, register_states)."""
        layout = CipherLayout(
            REGISTER_LENGTHS, REGISTER_TAPS, CONTROL_BIT_POSITIONS, OUTPUT_SPECS,
            key_length=KEY_LENGTH_BITS,
        )
        total_qubits = layout.total_qubits(n_keystream=max(total_keystream_bits, 1))
        qc = QuantumCircuit(total_qubits, total_qubits)

        append_full_initialization(qc, layout, self._key, self._frame_number, warmup_rounds=MIXING_ROUNDS)
        for i in range(total_keystream_bits):
            append_full_cycle(qc, layout, include_output=True, keystream_qubit=layout.keystream_qubit(i))

        qc.measure(range(total_qubits), range(total_qubits))
        result = _SIM.run(qc, shots=1).result()
        (bitstring, _), = result.get_counts().items()
        bits = bitstring[::-1]

        keystream = [int(bits[layout.keystream_qubit(i)]) for i in range(total_keystream_bits)]

        def read_reg(name):
            base = layout.register_offset[name]
            L = layout.register_lengths[name]
            val = 0
            for i in range(L):
                if bits[base + i] == "1":
                    val |= (1 << i)
            return val

        register_states = {name: read_reg(name) for name in ("R1", "R2", "R3", "R4")}

        return keystream, register_states

    def generate_keystream(self, n: int) -> List[int]:
        """
        Generate `n` NEW keystream bits, continuing from wherever this
        instance last left off (matching the classical class's
        incremental semantics, via rebuild-and-resimulate).
        """
        self._require_initialized()
        new_total = self._total_keystream_bits_generated + n
        full_keystream, register_states = self._run_full_circuit(new_total)

        new_bits = full_keystream[self._total_keystream_bits_generated:new_total]
        self._total_keystream_bits_generated = new_total
        self._cached_keystream = full_keystream
        self._cached_register_states = register_states
        return new_bits

    def generate_downlink(self, n: int) -> List[int]:
        """Alias for generate_keystream(), matching the classical class's naming convention."""
        return self.generate_keystream(n)

    def generate_uplink(self, n: int) -> List[int]:
        """Alias for generate_keystream(); continues from wherever downlink left off."""
        return self.generate_keystream(n)

    def encrypt(self, plaintext_bits: List[int]) -> List[int]:
        self._require_initialized()
        keystream = self.generate_keystream(len(plaintext_bits))
        return [p ^ k for p, k in zip(plaintext_bits, keystream)]

    def decrypt(self, ciphertext_bits: List[int]) -> List[int]:
        self._require_initialized()
        keystream = self.generate_keystream(len(ciphertext_bits))
        return [c ^ k for c, k in zip(ciphertext_bits, keystream)]

    def get_register_state(self, name: str) -> int:
        """Returns the register state as of the most recent generate_keystream() call."""
        return self._cached_register_states[name]
