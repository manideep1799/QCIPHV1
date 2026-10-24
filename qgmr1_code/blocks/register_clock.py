"""
blocks/register_clock.py
==========================

Quantum counterpart to the classical registers.py::LFSR class.

Mirrors the same generic, cipher-agnostic design: a register is
parameterized purely by (length, taps), and knows nothing about which
cipher it belongs to. Where the classical LFSR.clock() computes
feedback and shifts, this module provides the reversible equivalent.

CONSTRUCTION B (accepted design, per corrected Doc 03 SS3.1a / Doc 09 D8):
Feedback is accumulated IN PLACE into the register's own top-bit qubit
(position L-1), rather than into a separate ancilla. This is valid
because every register's tap set includes its own top bit -- i.e.
(L-1) in T -- which is a proven, not assumed, structural fact, checked
explicitly below rather than taken on faith.

Two operations are provided:
  - append_register_clock          : unconditional clock (used for R4,
                                      and for all 4 registers during the
                                      classical Initializer's force-clock
                                      key-loading stage)
  - append_controlled_register_clock : conditional clock, gated by an
                                      external control qubit (used for
                                      R1/R2/R3's majority-based irregular
                                      clocking)

Both are self-inverse-gate-only (X, CNOT, CCX, SWAP, CSWAP), so they
introduce no non-standard phases and are trivially invertible by
re-applying the same gate list in reverse order.
"""

from typing import List

from qiskit import QuantumCircuit


def check_precondition(L: int, taps: List[int]) -> None:
    """
    Verify (L-1) in taps. This is NOT assumed -- Construction B is only
    valid when the register's own top bit is one of its feedback taps
    (proven in Doc 09 D8; the accumulator's correctness depends on the
    top bit's pre-existing value being one of the k XOR terms being
    summed). Raises rather than silently producing wrong results.
    """
    if (L - 1) not in taps:
        raise ValueError(
            f"Construction B requires (L-1) in taps for a register of "
            f"length {L}, but taps={taps} does not include position {L-1}. "
            f"This register cannot use the in-place accumulator; it would "
            f"need the general fresh-ancilla Feedback block instead."
        )


def append_register_clock(qc: QuantumCircuit, L: int, taps: List[int], base: int = 0) -> None:
    """
    Unconditional register clock (Construction B).

    Mirrors classical LFSR.clock() for one register: computes feedback
    = XOR of tapped bits, then shifts (feedback becomes new bit 0,
    every other bit moves up by one, old top bit is consumed by the
    rotation).

    :param qc: circuit to append to
    :param L: register length
    :param taps: tap bit positions (0-indexed within the register)
    :param base: absolute qubit index where this register's bit 0 lives
        (register occupies qubits base..base+L-1)
    """
    check_precondition(L, taps)
    top = base + (L - 1)
    other_taps = [base + t for t in taps if t != (L - 1)]

    # Step 1: accumulate the OTHER (k-1) taps into the top-bit qubit.
    # The top bit's own pre-existing value is already one of the k XOR
    # terms, so after these CNOTs, the top-bit qubit holds the full
    # parity(taps) -- exactly the classical feedback value.
    for t in other_taps:
        qc.cx(t, top)

    # Step 2: rotate the L register qubits by one position (a single
    # L-cycle permutation, L-1 adjacent transpositions). The qubit now
    # holding the feedback value rotates into the bit-0 position.
    for i in range(L - 1, 0, -1):
        qc.swap(base + i, base + i - 1)


def append_controlled_register_clock(qc: QuantumCircuit, L: int, taps: List[int], control: int, base: int = 0) -> None:
    """
    Conditional (controlled) register clock (Construction B, controlled).

    If control=1: identical effect to append_register_clock.
    If control=0: identity (register unchanged).

    Used for R1/R2/R3, gated by the majority-derived clock-decision bit.
    """
    check_precondition(L, taps)
    top = base + (L - 1)
    other_taps = [base + t for t in taps if t != (L - 1)]

    for t in other_taps:
        qc.ccx(t, control, top)

    for i in range(L - 1, 0, -1):
        qc.cswap(control, base + i, base + i - 1)
