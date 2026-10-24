"""
initialization.py
==================

Implements the A5-GMR-1 initialization procedure: turning a 64-bit secret
key and a 19-bit frame number into the initial internal state of the four
LFSRs, from which keystream generation can begin.

The procedure has four distinct stages, each implemented as its own
method so every stage can be tested and traced independently:

1. **Key/frame reorganization** - the raw 8-byte key is byte-swapped in
   pairs, and the frame number bits are XORed into specific positions of
   the reorganized key material. This produces the 64-bit value that is
   actually mixed into the registers.
2. **Key loading (forced clocking)** - all four registers start at all
   zero. For each of the 64 bits of the reorganized key (most significant
   bit of byte 0 first), *all four* registers are forced-clocked and then
   that single key bit is XORed into bit 0 of every register.
3. **Forced-bit stage** - after key loading, bit 0 of every register is
   forced to 1. This avoids ever starting from a degenerate all-zero
   LFSR state.
4. **Mixing stage** - the registers are advanced for a fixed number of
   cycles (250) using the *normal* irregular clocking rule (not forced
   clocking), discarding all output. This "warms up" the state so that
   the first true keystream bit does not trivially leak the key.

No simplifications are made to any of these stages relative to the
Osmocom / published GMR-1 specification.
"""

from dataclasses import dataclass, field
from typing import Dict, List

from clocking import ClockController
from constants import (
    FORCED_BIT_POSITION,
    FRAME_NUMBER_MASK,
    KEY_LENGTH_BYTES,
    KEY_MIXING_ROUNDS,
    MIXING_ROUNDS,
    REGISTER_NAMES,
)
from registers import LFSR
from utils import bytes_to_bits, get_bit


@dataclass
class InitializationTrace:
    """
    Records the intermediate values produced while initializing the
    cipher, for use by the debug tracer.

    :param reorganized_key: The 8-byte key after byte-pair swapping and
        frame-number mixing.
    :param key_mixing_bits: The 64 individual bits injected during the
        key-loading stage, in injection order.
    """

    reorganized_key: bytes = b""
    key_mixing_bits: List[int] = field(default_factory=list)


class Initializer:
    """
    Performs A5-GMR-1 initialization over a set of already-constructed
    (but not yet loaded) :class:`~registers.LFSR` instances.

    :param registers: Mapping from register name to :class:`LFSR`
        instance, as used by :class:`~clocking.ClockController`.
    """

    def __init__(self, registers: Dict[str, LFSR]) -> None:
        missing = [name for name in REGISTER_NAMES if name not in registers]
        if missing:
            raise ValueError(f"missing registers: {missing}")
        self._registers = registers
        self._clock_controller = ClockController(registers)
        self.trace = InitializationTrace()

    # ------------------------------------------------------------------
    # Stage 1: key / frame-number reorganization
    # ------------------------------------------------------------------

    @staticmethod
    def reorganize_key(key: bytes, frame_number: int) -> bytes:
        """
        Reorganize the raw session key with the frame number, exactly as
        specified for A5-GMR-1.

        The 8 key bytes are swapped in adjacent pairs (byte 0 <-> byte 1,
        byte 2 <-> byte 3, byte 4 <-> byte 5, byte 6 <-> byte 7), and then
        bits of the (up to 19-bit) frame number are XORed into specific
        byte positions of the result.

        :param key: The 8-byte secret session key.
        :param frame_number: The frame number, 0 <= frame_number < 2**19.
        :return: The 8-byte reorganized key material to be mixed into
            the registers.
        """
        if len(key) != KEY_LENGTH_BYTES:
            raise ValueError(f"key must be exactly {KEY_LENGTH_BYTES} bytes")
        if not (0 <= frame_number <= FRAME_NUMBER_MASK):
            raise ValueError(
                f"frame_number must fit in {FRAME_NUMBER_MASK.bit_length()} bits"
            )

        # Byte-pair swap: [0,1,2,3,4,5,6,7] -> [1,0,3,2,5,4,7,6]
            # equivalently: lkey[i] = key[i ^ 1]
        swapped = bytearray(KEY_LENGTH_BYTES)
        for i in range(KEY_LENGTH_BYTES):
            swapped[i] = key[i ^ 1]

        # Mix frame-number bits into specific byte positions.
        fn = frame_number
        swapped[6] ^= (fn & 0x00F) << 4
        swapped[3] ^= (fn & 0x030) << 2
        swapped[1] ^= (fn & 0x7C0) >> 3
        swapped[0] ^= (fn & 0xF800) >> 11
        swapped[0] ^= (fn & 0x70000) >> 11

        return bytes(swapped)

    # ------------------------------------------------------------------
    # Stage 2: key loading via forced clocking
    # ------------------------------------------------------------------

    def load_key_material(self, reorganized_key: bytes) -> None:
        """
        Inject each bit of the reorganized key into the registers.

        All four registers start at zero. For each of the 64 key bits
        (most significant bit of the first byte first):

        1. Force-clock all four registers (see
           :meth:`clocking.ClockController.force_clock_all`).
        2. XOR the key bit directly into bit 0 of every register.

        :param reorganized_key: The 8-byte value produced by
            :meth:`reorganize_key`.
        """
        for register in self._registers.values():
            register.reset()

        key_bits = bytes_to_bits(reorganized_key)
        if len(key_bits) != KEY_MIXING_ROUNDS:
            raise ValueError(
                f"expected {KEY_MIXING_ROUNDS} key bits, got {len(key_bits)}"
            )

        self.trace.key_mixing_bits = list(key_bits)

        for bit in key_bits:
            self._clock_controller.force_clock_all()
            for register in self._registers.values():
                current = register.get_bit(0)
                register.set_bit(0, current ^ bit)

    # ------------------------------------------------------------------
    # Stage 3: forced-bit stage
    # ------------------------------------------------------------------

    def force_nonzero_bit(self) -> None:
        """
        Force bit 0 of every register to ``1``.

        This guarantees no register is left in the invalid all-zero
        state after key loading, which would otherwise be a fixed point
        of the LFSR feedback function.
        """
        for register in self._registers.values():
            register.set_bit(FORCED_BIT_POSITION, 1)

    # ------------------------------------------------------------------
    # Stage 4: mixing stage
    # ------------------------------------------------------------------

    def run_mixing_rounds(self, rounds: int = MIXING_ROUNDS) -> None:
        """
        Advance the registers using the normal irregular clocking rule
        for a fixed number of rounds, discarding all output.

        :param rounds: Number of mixing rounds to run (default: the
            standard 250 specified for A5-GMR-1).
        """
        for _ in range(rounds):
            self._clock_controller.step()

    # ------------------------------------------------------------------
    # Full procedure
    # ------------------------------------------------------------------

    def initialize(self, key: bytes, frame_number: int) -> None:
        """
        Run the complete initialization procedure: reorganize the key,
        load it via forced clocking, force the non-zero bit, then run
        the mixing rounds.

        :param key: The 8-byte secret session key.
        :param frame_number: The frame number, 0 <= frame_number < 2**19.
        """
        reorganized_key = self.reorganize_key(key, frame_number)
        self.trace.reorganized_key = reorganized_key

        self.load_key_material(reorganized_key)
        self.force_nonzero_bit()
        self.run_mixing_rounds()
