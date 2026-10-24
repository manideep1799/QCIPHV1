"""
initialization/full_initialization.py
========================================

Quantum counterpart to initialization.Initializer.

Mirrors the four classical stages exactly:

  Stage A (reorganize_key): key/frame reorganization. This is a
  classical-data operation (byte-pair swap + XOR with the frame number,
  both fixed, known-in-advance transformations of a classical key/frame
  pair) -- realized here by preparing the "key qubits" directly to the
  classical reorganized-key value via X gates. This produces an
  identical qubit state to "prepare raw key via X gates, then apply the
  same fixed swap+XOR" -- the byte-pair swap is a pure relabeling with
  no data dependency, so eliding it changes nothing observable.

  Stage B (load_key_material): 64 rounds of force-clock-all (register_clock,
  unconditional, all 4 registers) + key-bit injection (CNOT into bit 0).

  Stage C (force_nonzero_bit): force bit 0 of every register to 1. This
  is a genuine overwrite (not XOR), and per Doc 06 / Doc 09 D4 is the
  ONE place in the whole cipher where information is truly discarded --
  realized via copy-out to a persistent history qubit (never
  uncomputed), then unconditional set to 1. This is NOT a bug and NOT
  something Construction B addresses; it is a distinct, already-analyzed
  design decision (D4), orthogonal to the register-clocking question.

  Stage D (run_mixing_rounds): 250 rounds of the full cycle with output
  omitted.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "classical_ref", "a5_gmr1"))

from qiskit import QuantumCircuit

from blocks.register_clock import append_register_clock
from cycle.layout import CipherLayout
from cycle.full_cycle import append_full_cycle
from initialization import Initializer as ClassicalInitializer
from utils import bytes_to_bits


def append_stage_a(qc: QuantumCircuit, layout: CipherLayout, key: bytes, frame_number: int) -> None:
    """Prepare the key qubits to the classical reorganized-key value."""
    reorganized_key = ClassicalInitializer.reorganize_key(key, frame_number)
    key_bits = bytes_to_bits(reorganized_key)
    if len(key_bits) != layout.key_length:
        raise ValueError(f"expected {layout.key_length} key bits, got {len(key_bits)}")
    for i, bit in enumerate(key_bits):
        if bit:
            qc.x(layout.key_offset + i)


def append_stage_b(qc: QuantumCircuit, layout: CipherLayout) -> None:
    """64 rounds: force-clock all 4 registers, then inject the corresponding key bit into bit 0 of each."""
    for i in range(layout.key_length):
        key_qubit = layout.key_offset + i
        for name in ("R1", "R2", "R3", "R4"):
            L = layout.register_lengths[name]
            taps = layout.register_taps[name]
            base = layout.register_offset[name]
            append_register_clock(qc, L, taps, base=base)
        for name in ("R1", "R2", "R3", "R4"):
            base = layout.register_offset[name]
            qc.cx(key_qubit, base + 0)


def append_stage_c(qc: QuantumCircuit, layout: CipherLayout) -> None:
    """Force bit 0 of every register to 1, via copy-then-restore-then-set (Doc 06 D4)."""
    for name in ("R1", "R2", "R3", "R4"):
        base = layout.register_offset[name]
        hist = layout.history[name]
        bit0 = base + 0
        qc.cx(bit0, hist)   # copy out prior value
        qc.cx(hist, bit0)   # restore bit0 to 0 regardless of prior value
        qc.x(bit0)          # force to 1


def append_stage_d(qc: QuantumCircuit, layout: CipherLayout, rounds: int) -> None:
    """`rounds` full clock cycles with output omitted."""
    for _ in range(rounds):
        append_full_cycle(qc, layout, include_output=False)


def append_full_initialization(qc: QuantumCircuit, layout: CipherLayout, key: bytes, frame_number: int, warmup_rounds: int) -> None:
    append_stage_a(qc, layout, key, frame_number)
    append_stage_b(qc, layout)
    append_stage_c(qc, layout)
    append_stage_d(qc, layout, warmup_rounds)
