"""
output.py
=========

The A5-GMR-1 keystream output function.

On every clock cycle (after the registers have been clocked according to
the irregular clocking rule), a single keystream bit is derived from the
*current* states of R1, R2 and R3 (R4 never contributes directly to the
output -- it only ever drives the clock controller).

For each of R1, R2, R3 the contribution is:

    contribution(Rk) = majority(Rk[a], Rk[b], Rk[c]) XOR Rk[d]

where ``a, b, c`` are three tapped bit positions specific to that
register and ``d`` is one further tapped bit position. The final output
bit is the XOR of the three per-register contributions.
"""
from dataclasses import dataclass
from typing import Dict, Tuple

from constants import (
    R1_OUTPUT_MAJORITY_BITS,
    R1_OUTPUT_XOR_BIT,
    R2_OUTPUT_MAJORITY_BITS,
    R2_OUTPUT_XOR_BIT,
    R3_OUTPUT_MAJORITY_BITS,
    R3_OUTPUT_XOR_BIT,
)
from majority import majority
from registers import LFSR


@dataclass(frozen=True)
class OutputTrace:
    """
    Records the per-register contributions that produced a single
    keystream bit, for use by the debug tracer.

    :param contributions: The individual (post-majority, post-XOR)
        contribution of R1, R2 and R3, in that order.
    :param output_bit: The final keystream bit (XOR of ``contributions``).
    """

    contributions: Tuple[int, int, int]
    output_bit: int


class OutputFunction:
    """
    Computes A5-GMR-1 keystream bits from the current state of R1, R2 and
    R3.

    :param registers: Mapping from register name to :class:`LFSR`
        instance. Must contain at least ``"R1"``, ``"R2"``, ``"R3"``.
    """

    def __init__(self, registers: Dict[str, LFSR]) -> None:
        for name in ("R1", "R2", "R3"):
            if name not in registers:
                raise ValueError(f"missing register: {name}")
        self._registers = registers

    @staticmethod
    def _contribution(
        register: LFSR,
        majority_bits: Tuple[int, int, int],
        xor_bit: int,
    ) -> int:
        """
        Compute a single register's contribution to the output bit:
        majority of three tapped bits, XORed with one further bit.
        """
        a = register.get_bit(majority_bits[0])
        b = register.get_bit(majority_bits[1])
        c = register.get_bit(majority_bits[2])
        d = register.get_bit(xor_bit)
        return majority(a, b, c) ^ d


    def compute(self) -> OutputTrace:
        """
        Compute the current keystream output bit from the present
        register states, without clocking anything.

        :return: An :class:`OutputTrace` with both the per-register
            contributions and the final combined bit.
        """
        r1_contribution = self._contribution(
            self._registers["R1"], R1_OUTPUT_MAJORITY_BITS, R1_OUTPUT_XOR_BIT
        )
        r2_contribution = self._contribution(
            self._registers["R2"], R2_OUTPUT_MAJORITY_BITS, R2_OUTPUT_XOR_BIT
        )
        r3_contribution = self._contribution(
            self._registers["R3"], R3_OUTPUT_MAJORITY_BITS, R3_OUTPUT_XOR_BIT
        )

        output_bit = r1_contribution ^ r2_contribution ^ r3_contribution

        return OutputTrace(
            contributions=(r1_contribution, r2_contribution, r3_contribution),
            output_bit=output_bit,
        )
