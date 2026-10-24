"""
blocks/primitives.py
=======================

Quantum counterpart to majority.py, plus the equality ("does this
control bit match the majority?") building block clocking.py needs but
doesn't itself define classically (it's just `==` there; here it needs
its own reversible circuit).

Both gates below are provided as *inline append* functions (append
gates directly to an existing circuit) rather than wrapped Gate objects,
because plain gate lists simulate far faster under Aer than wrapped
custom Gates requiring transpile()/decompose() before running.
"""

from qiskit import QuantumCircuit


def append_majority(qc: QuantumCircuit, a: int, b: int, c: int, out: int) -> None:
    """
    Reversible majority: out ^= maj(a,b,c) = ab XOR ac XOR bc.

    Mirrors majority.majority(a,b,c): "1 if at least two of a,b,c are 1".
    `out` must be |0> on entry. a, b, c are left unchanged.

    Self-inverse-gate-only (3 Toffolis); append_unmajority below is the
    literal gate-reversal, not a distinct construction.
    """
    qc.ccx(a, b, out)
    qc.ccx(a, c, out)
    qc.ccx(b, c, out)


def append_unmajority(qc: QuantumCircuit, a: int, b: int, c: int, out: int) -> None:
    """Exact inverse of append_majority (reverse gate order; CCX is self-inverse)."""
    qc.ccx(b, c, out)
    qc.ccx(a, c, out)
    qc.ccx(a, b, out)


def append_equality(qc: QuantumCircuit, x: int, y: int, out: int) -> None:
    """
    Reversible equality: out ^= (x == y), i.e. XNOR(x, y) = 1 XOR x XOR y.

    Mirrors the `control_bits[i] == majority_value` comparison in
    clocking.ClockController.step(). `out` must be |0> on entry.
    """
    qc.x(out)
    qc.cx(x, out)
    qc.cx(y, out)


def append_unequality(qc: QuantumCircuit, x: int, y: int, out: int) -> None:
    """Exact inverse of append_equality (reverse gate order; all self-inverse)."""
    qc.cx(y, out)
    qc.cx(x, out)
    qc.x(out)
