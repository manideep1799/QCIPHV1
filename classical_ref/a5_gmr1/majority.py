"""
majority.py
===========

The majority function used both by the clock controller (to decide which
registers get clocked) and by the output function (to combine tapped
bits from each register into a keystream contribution).

Kept as a standalone, single-purpose module so it can be exhaustively
unit tested in isolation and later translated directly into a small
reversible quantum sub-circuit (a 3-input majority gate is a well known,
simple building block in quantum arithmetic circuits).
"""


def majority(a: int, b: int, c: int) -> int:
    """
    Compute the boolean majority of three single-bit inputs.

    :param a: First input bit, ``0`` or ``1``.
    :param b: Second input bit, ``0`` or ``1``.
    :param c: Third input bit, ``0`` or ``1``.
    :return: ``1`` if at least two of ``a``, ``b``, ``c`` are ``1``,
        otherwise ``0``.
    """
    for name, value in (("a", a), ("b", b), ("c", c)):
        if value not in (0, 1):
            raise ValueError(f"{name} must be 0 or 1, got {value!r}")
    return 1 if (a + b + c) >= 2 else 0
