"""
utils.py
========

Small, self-contained bit-manipulation helpers used throughout the
A5-GMR-1 implementation.

Every function here is deliberately tiny and does exactly one logical
operation. This matters for two reasons:

1. Readability - each helper can be understood (and unit tested) in
   isolation.
2. Quantum translation - a reversible quantum circuit is built up from
   small elementary reversible/invertible operations. Keeping the
   classical reference implementation broken into the same granularity
   makes the later mapping from "classical function" to "quantum gate
   sequence" far more direct.

No function in this module depends on anything A5-GMR-1 specific.
"""

from typing import List


def get_bit(value: int, position: int) -> int:
    """
    Return the single bit of ``value`` at ``position`` (0 = least
    significant bit).

    :param value: The integer to read a bit from.
    :param position: Zero-based bit index (0 is the least significant bit).
    :return: ``0`` or ``1``.
    """
    return (value >> position) & 1


def set_bit(value: int, position: int, bit: int) -> int:
    """
    Return a copy of ``value`` with the bit at ``position`` set to ``bit``.

    :param value: The integer to modify.
    :param position: Zero-based bit index (0 is the least significant bit).
    :param bit: The new bit value, ``0`` or ``1``.
    :return: The updated integer.
    """
    if bit not in (0, 1):
        raise ValueError("bit must be 0 or 1")
    if bit:
        return value | (1 << position)
    return value & ~(1 << position)


def parity(value: int) -> int:
    """
    Compute the XOR ("parity") of every set bit in ``value``.

    This is used to combine the tapped feedback bits of an LFSR: the
    tap-selected bits are first isolated with a bitwise AND against a tap
    mask, and the resulting value is passed to ``parity`` to fold all of
    the selected bits together into a single feedback bit.

    :param value: The integer whose bits should be XORed together.
    :return: ``0`` or ``1``.
    """
    result = 0
    while value:
        result ^= value & 1
        value >>= 1
    return result


def mask_for_length(length: int) -> int:
    """
    Return a bitmask that keeps exactly the lowest ``length`` bits.

    :param length: Number of bits the mask should cover.
    :return: An integer with ``length`` low bits set to 1.
    """
    return (1 << length) - 1


def bits_to_int(bits: List[int]) -> int:
    """
    Pack a list of bits into a single integer.

    ``bits[0]`` is treated as the most significant bit and the last
    element as the least significant bit, matching the natural reading
    order of a printed bit string (e.g. ``[1, 0, 1]`` -> ``0b101`` -> 5).

    :param bits: A list of ``0``/``1`` values.
    :return: The packed integer value.
    """
    value = 0
    for bit in bits:
        if bit not in (0, 1):
            raise ValueError("all bits must be 0 or 1")
        value = (value << 1) | bit
    return value


def int_to_bits(value: int, length: int) -> List[int]:
    """
    Unpack an integer into a fixed-width list of bits, most significant
    bit first.

    :param value: The integer to unpack.
    :param length: The number of bits to produce.
    :return: A list of ``length`` bits, most significant bit first.
    """
    return [(value >> shift) & 1 for shift in range(length - 1, -1, -1)]


def bytes_to_bits(data: bytes) -> List[int]:
    """
    Unpack a ``bytes`` object into a list of bits, most significant bit
    of the first byte first.

    :param data: The byte string to unpack.
    :return: A list of bits, 8 per input byte.
    """
    bits: List[int] = []
    for byte in data:
        bits.extend(int_to_bits(byte, 8))
    return bits
