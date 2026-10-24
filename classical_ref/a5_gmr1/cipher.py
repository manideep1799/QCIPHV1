"""
cipher.py
=========

The top-level ``A5GMR1`` cipher class.

This class does not implement any cryptographic logic itself -- it only
*orchestrates* the modules defined elsewhere in this package:

- ``registers.LFSR``       - the four shift registers
- ``clocking.ClockController`` - the irregular clocking rule
- ``initialization.Initializer`` - key/frame setup
- ``output.OutputFunction`` - keystream bit derivation
- ``debug.trace.Tracer``    - optional per-round tracing

A user of this module should never need to import or call into any of
the lower-level modules directly; :class:`A5GMR1` exposes the complete
public interface described in the project specification.
"""

from typing import Dict, List

from clocking import ClockController
from constants import (
    R1_LENGTH,
    R1_TAPS,
    R2_LENGTH,
    R2_TAPS,
    R3_LENGTH,
    R3_TAPS,
    R4_LENGTH,
    R4_TAPS,
    CONTROL_BIT_POSITIONS,
)
from debug.trace import RoundTrace, Tracer, bits_string
from initialization import Initializer
from output import OutputFunction
from registers import LFSR


class A5GMR1:
    """
    Reference classical implementation of the A5-GMR-1 stream cipher.

    :param key: The 8-byte secret session key.
    :param frame_number: The frame number, ``0 <= frame_number < 2**19``.
    :param trace: If ``True``, print a detailed per-round trace of the
        internal state to stdout as the generator runs.
    """

    def __init__(self, key: bytes, frame_number: int, trace: bool = False) -> None:
        self._key = key
        self._frame_number = frame_number
        self._trace_enabled = trace
        self._round_number = 0

        self._registers: Dict[str, LFSR] = {
            "R1": LFSR(length=R1_LENGTH, taps=R1_TAPS),
            "R2": LFSR(length=R2_LENGTH, taps=R2_TAPS),
            "R3": LFSR(length=R3_LENGTH, taps=R3_TAPS),
            "R4": LFSR(
                length=R4_LENGTH,
                taps=R4_TAPS,
                clock_bit_positions=CONTROL_BIT_POSITIONS,
            ),
        }

        self._clock_controller = ClockController(self._registers)
        self._initializer = Initializer(self._registers)
        self._output_function = OutputFunction(self._registers)
        self._tracer = Tracer() if trace else None

        self._initialized = False

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """
        Run the full A5-GMR-1 initialization procedure (key/frame
        reorganization, forced-clock key loading, forced non-zero bit,
        and the 250-round mixing stage) using the key and frame number
        supplied to the constructor.

        Must be called once before :meth:`clock`, :meth:`generate_bit`,
        :meth:`generate_keystream`, :meth:`encrypt` or :meth:`decrypt`
        are used.
        """
        self._initializer.initialize(self._key, self._frame_number)
        self._initialized = True
        self._round_number = 0

    def _require_initialized(self) -> None:
        if not self._initialized:
            raise RuntimeError("A5GMR1.initialize() must be called before use")

    # ------------------------------------------------------------------
    # Core generation primitives
    # ------------------------------------------------------------------

    def clock(self) -> None:
        """
        Advance the generator by exactly one clock cycle using the
        normal (post-initialization) irregular clocking rule, without
        producing any output bit.

        Most callers should use :meth:`generate_bit` instead, which
        clocks the generator *and* reads the resulting output bit; this
        method is exposed separately for callers (and tests) that want
        finer-grained control.
        """
        self._require_initialized()
        self._clock_controller.step()

    def generate_bit(self) -> int:
        """
        Advance the generator by one clock cycle and return the
        resulting keystream bit.

        :return: ``0`` or ``1``.
        """
        self._require_initialized()

        registers_before = (
            {name: bits_string(reg) for name, reg in self._registers.items()}
            if self._tracer is not None
            else {}
        )

        decision = self._clock_controller.step()
        output_trace = self._output_function.compute()

        if self._tracer is not None:
            self._round_number += 1
            registers_after = {
                name: bits_string(reg) for name, reg in self._registers.items()
            }
            feedback_bits = {
                name: reg.compute_feedback()
                for name, reg, was_clocked in zip(
                    ("R1", "R2", "R3", "R4"),
                    (
                        self._registers["R1"],
                        self._registers["R2"],
                        self._registers["R3"],
                        self._registers["R4"],
                    ),
                    decision.clocked,
                )
                if was_clocked
            }
            round_trace = RoundTrace(
                round_number=self._round_number,
                registers_before=registers_before,
                clock_decision=decision,
                registers_after=registers_after,
                feedback_bits=feedback_bits,
                output_trace=output_trace,
            )
            self._tracer.print_round(round_trace)

        return output_trace.output_bit

    def generate_keystream(self, n: int) -> List[int]:
        """
        Generate ``n`` keystream bits.

        :param n: Number of bits to generate.
        :return: A list of ``n`` bits (``0``/``1``), in generation
            order.
        """
        self._require_initialized()
        return [self.generate_bit() for _ in range(n)]

    # ------------------------------------------------------------------
    # Encryption / decryption
    # ------------------------------------------------------------------

    def encrypt(self, plaintext_bits: List[int]) -> List[int]:
        """
        Encrypt a list of plaintext bits by XORing them with freshly
        generated keystream bits.

        As a synchronous stream cipher, A5-GMR-1's encryption and
        decryption operations are identical (both are just XOR with the
        keystream); this method and :meth:`decrypt` are provided
        separately only for clarity at call sites.

        :param plaintext_bits: The bits to encrypt.
        :return: The ciphertext bits, the same length as the input.
        """
        self._require_initialized()
        keystream = self.generate_keystream(len(plaintext_bits))
        return [p ^ k for p, k in zip(plaintext_bits, keystream)]

    def decrypt(self, ciphertext_bits: List[int]) -> List[int]:
        """
        Decrypt a list of ciphertext bits by XORing them with freshly
        generated keystream bits.

        :param ciphertext_bits: The bits to decrypt.
        :return: The plaintext bits, the same length as the input.
        """
        self._require_initialized()
        keystream = self.generate_keystream(len(ciphertext_bits))
        return [c ^ k for c, k in zip(ciphertext_bits, keystream)]

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------

    def get_register_state(self, name: str) -> int:
        """
        Return the raw integer state of a named register.

        :param name: One of ``"R1"``, ``"R2"``, ``"R3"``, ``"R4"``.
        :return: The register's current state.
        """
        return self._registers[name].get_state()
