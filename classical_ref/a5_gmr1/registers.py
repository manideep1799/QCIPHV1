"""
registers.py
============

A completely generic Linear Feedback Shift Register (LFSR).

This class contains **no** A5-GMR-1 specific knowledge whatsoever. It only
knows how to:

- hold a state of a fixed bit length,
- compute a Fibonacci-style feedback bit from a configurable tap mask,
- shift its state left by one position on each clock, inserting the
  feedback bit at position 0,
- report individual bits of its current state.

Any cipher built from LFSRs (A5-GMR-1, A5/1, and many others) can be
assembled by instantiating several ``LFSR`` objects with different
lengths/taps and wiring them together with cipher-specific glue code
(see ``clocking.py``, ``initialization.py`` and ``output.py``).
"""

from typing import List, Optional, Sequence

from utils import get_bit, mask_for_length, parity, set_bit


class LFSR:
    """
    A generic, configurable Linear Feedback Shift Register.

    The register stores its state as a single Python integer, bit 0 being
    the least significant / "rightmost" bit. Feedback is computed in the
    classic Fibonacci configuration: a fixed set of tap bits is read from
    the *current* state, XORed together, and the result becomes the new
    bit 0 after the rest of the register is shifted left by one place.

    :param length: Number of bits in the register.
    :param taps: Bitmask selecting which bit positions feed back into the
        register on each clock. Bit ``i`` of ``taps`` being set means
        "include bit ``i`` of the current state in the feedback XOR".
    :param clock_bit_positions: Bit positions of this register that may be
        used by an external clock controller to decide whether to clock
        this (or other) registers. This is metadata only -- the ``LFSR``
        class itself never reads this value to decide anything; it exists
        purely so that a clock controller can ask a register "which
        bit(s) do you expose for clock control?" instead of the cipher
        layer hardcoding positions.
    :param output_bit_position: Default bit position read by
        :meth:`get_output_bit` when no explicit position is supplied.
    """

    def __init__(
        self,
        length: int,
        taps: int,
        clock_bit_positions: Sequence[int] = (),
        output_bit_position: Optional[int] = None,
    ) -> None:
        if length <= 0:
            raise ValueError("length must be a positive integer")
        if taps < 0 or taps >= (1 << length):
            raise ValueError("taps must fit within 'length' bits")
        for position in clock_bit_positions:
            if not (0 <= position < length):
                raise ValueError("clock_bit_positions must be within the register")
        if output_bit_position is not None and not (0 <= output_bit_position < length):
            raise ValueError("output_bit_position must be within the register")

        self._length: int = length
        self._taps: int = taps
        self._mask: int = mask_for_length(length)
        self._clock_bit_positions: tuple = tuple(clock_bit_positions)
        self._output_bit_position: Optional[int] = output_bit_position

        self._state: int = 0

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def load(self, bits: List[int]) -> None:
        """
        Load an explicit bit pattern into the register.

        :param bits: A list of ``0``/``1`` values, most significant bit
            first, whose length must equal the register length.
        """
        if len(bits) != self._length:
            raise ValueError(
                f"expected {self._length} bits, got {len(bits)}"
            )
        value = 0
        for bit in bits:
            if bit not in (0, 1):
                raise ValueError("all bits must be 0 or 1")
            value = (value << 1) | bit
        self._state = value & self._mask

    def get_state(self) -> int:
        """Return the current register state as an integer."""
        return self._state

    def set_state(self, state: int) -> None:
        """
        Directly set the register state.

        :param state: The new state. Must fit within the register length.
        """
        if state < 0 or state >= (1 << self._length):
            raise ValueError("state does not fit within the register length")
        self._state = state

    def reset(self) -> None:
        """Reset the register state to all zeros."""
        self._state = 0

    # ------------------------------------------------------------------
    # Bit access
    # ------------------------------------------------------------------

    def get_bit(self, position: int) -> int:
        """
        Return a single bit of the current state.

        :param position: Zero-based bit index (0 is the least
            significant bit).
        :return: ``0`` or ``1``.
        """
        if not (0 <= position < self._length):
            raise ValueError("position out of range for this register")
        return get_bit(self._state, position)

    def set_bit(self, position: int, bit: int) -> None:
        """
        Set a single bit of the current state.

        :param position: Zero-based bit index (0 is the least
            significant bit).
        :param bit: The new bit value, ``0`` or ``1``.
        """
        if not (0 <= position < self._length):
            raise ValueError("position out of range for this register")
        self._state = set_bit(self._state, position, bit)

    def get_clock_bit(self, index: int = 0) -> int:
        """
        Return one of the register's designated "clock control" bits.

        :param index: Which entry of ``clock_bit_positions`` to read.
        :return: ``0`` or ``1``.
        """
        if not self._clock_bit_positions:
            raise ValueError("this register has no clock_bit_positions configured")
        return self.get_bit(self._clock_bit_positions[index])

    def get_output_bit(self) -> int:
        """
        Return the register's designated default output bit.

        :return: ``0`` or ``1``.
        """
        if self._output_bit_position is None:
            raise ValueError("this register has no output_bit_position configured")
        return self.get_bit(self._output_bit_position)

    # ------------------------------------------------------------------
    # Clocking
    # ------------------------------------------------------------------

    def compute_feedback(self) -> int:
        """
        Compute the feedback bit for the *current* state without
        modifying it.

        This is the XOR ("parity") of every bit selected by the tap
        mask.

        :return: ``0`` or ``1``.
        """
        return parity(self._state & self._taps)

    def clock(self) -> int:
        """
        Advance the register by one clock cycle: compute the feedback
        bit, shift the state left by one position (discarding any bit
        that would overflow the register length), and insert the
        feedback bit at position 0.

        :return: The feedback bit that was inserted, for callers (such
            as the debug tracer) that want to observe it.
        """
        feedback = self.compute_feedback()
        self._state = ((self._state << 1) & self._mask) | feedback
        return feedback

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def length(self) -> int:
        """Number of bits in this register."""
        return self._length

    def get_bits(self) -> List[int]:
        """Return the current state as a list of bits, MSB first."""
        return [self.get_bit(pos) for pos in range(self._length - 1, -1, -1)]

    def __repr__(self) -> str:
        bits = "".join(str(b) for b in self.get_bits())
        return f"LFSR(length={self._length}, state=0b{bits})"
