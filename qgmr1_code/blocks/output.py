"""
blocks/output.py
==================

Quantum counterpart to output.py.

Mirrors OutputFunction.compute() exactly: for each of R1/R2/R3,
majority(a,b,c) XOR d, then XOR the three contributions together into
the keystream bit. Uses the compute -> copy-out -> uncompute discipline
(Bennett's trick) so only the keystream qubit retains a nonzero value;
all intermediate ancillas (m_1, m_2, m_3, out) return to |0>.

"""

from typing import Sequence, Tuple

from qiskit import QuantumCircuit

from blocks.primitives import append_majority, append_unmajority


def append_output_block(
    qc: QuantumCircuit,
    register_output_specs: Sequence[Tuple[Tuple[int, int, int], int]],
    m_ancillas: Sequence[int],
    out_ancilla: int,
    keystream_qubit: int,
) -> None:
    """
    :param register_output_specs: [(majority_qubits, xor_qubit), ...] for
        R1, R2, R3 in order. majority_qubits mirrors
        (R{k}_OUTPUT_MAJORITY_BITS), xor_qubit mirrors R{k}_OUTPUT_XOR_BIT.
    :param m_ancillas: one ancilla per register (must be |0> on entry)
    :param out_ancilla: combines the 3 contributions (must be |0> on entry)
    :param keystream_qubit: persistent qubit the final bit is copied into
        (NOT uncomputed -- this is the cycle's payload)
    """
    if len(register_output_specs) != len(m_ancillas):
        raise ValueError("register_output_specs and m_ancillas must have the same length")

    # Forward: majority(a,b,c) XOR d, into each m_i
    for (maj_qubits, xor_qubit), m_anc in zip(register_output_specs, m_ancillas):
        a, b, c = maj_qubits
        append_majority(qc, a, b, c, m_anc)
        qc.cx(xor_qubit, m_anc)  # m_anc now holds majority(a,b,c) XOR d

    # Forward: combine the 3 contributions into out_ancilla
    for m_anc in m_ancillas:
        qc.cx(m_anc, out_ancilla)

    # Copy out to persistent keystream qubit
    qc.cx(out_ancilla, keystream_qubit)

    # Uncompute out_ancilla (reverse order)
    for m_anc in reversed(m_ancillas):
        qc.cx(m_anc, out_ancilla)

    # Uncompute m_1, m_2, m_3 (reverse order, registers also reversed)
    for (maj_qubits, xor_qubit), m_anc in zip(reversed(register_output_specs), reversed(m_ancillas)):
        a, b, c = maj_qubits
        qc.cx(xor_qubit, m_anc)  # undo the XOR (self-inverse)
        append_unmajority(qc, a, b, c, m_anc)
