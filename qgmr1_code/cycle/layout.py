"""
cycle/layout.py
==================

Qubit layout bookkeeping for the full cipher circuit. Not present in
the classical code (which just uses Python integers for register
state) -- this is the quantum-specific piece of plumbing needed to
track which absolute qubit index corresponds to "register R1, bit 5"
etc.

Layout (in order):
    R1 (L1 qubits) | R2 (L2) | R3 (L3) | R4 (L4)
    | key (64 qubits)
    | maj | clk1 | clk2 | clk3 | m1 | m2 | m3 | out    (8 scratch ancillas)
    | history_R1 | history_R2 | history_R3 | history_R4  (4 Stage-C ancillas)
    | keystream_0 .. keystream_{N-1}                    (N output qubits)
"""

from typing import Dict, Tuple


class CipherLayout:
    def __init__(
        self,
        register_lengths: Dict[str, int],
        register_taps: Dict[str, list],
        control_bit_positions: Tuple[int, int, int],
        output_specs: Dict[str, Tuple[Tuple[int, int, int], int]],
        key_length: int = 0,
    ):
        self.register_lengths = register_lengths
        self.register_taps = register_taps
        self.control_bit_positions = control_bit_positions
        self.output_specs = output_specs
        self.key_length = key_length

        offset = 0
        self.register_offset = {}
        for name in ("R1", "R2", "R3", "R4"):
            self.register_offset[name] = offset
            offset += register_lengths[name]
        self.total_register_qubits = offset

        self.key_offset = offset
        offset += key_length

        self.maj = offset; offset += 1
        self.clk1 = offset; offset += 1
        self.clk2 = offset; offset += 1
        self.clk3 = offset; offset += 1
        self.m1 = offset; offset += 1
        self.m2 = offset; offset += 1
        self.m3 = offset; offset += 1
        self.out = offset; offset += 1

        self.history = {}
        for name in ("R1", "R2", "R3", "R4"):
            self.history[name] = offset
            offset += 1

        self.pre_keystream_qubits = offset

    def register_qubit(self, name: str, local_pos: int) -> int:
        return self.register_offset[name] + local_pos

    def keystream_qubit(self, cycle_index: int) -> int:
        return self.pre_keystream_qubits + cycle_index

    def total_qubits(self, n_keystream: int) -> int:
        return self.pre_keystream_qubits + n_keystream

