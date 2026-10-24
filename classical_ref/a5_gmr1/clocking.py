"""
clocking.py
===========

The A5-GMR-1 clock controller.

Unlike classic A5/1 (where R1, R2 and R3 each expose their own clock
control bit and vote on their own majority), A5-GMR-1 uses a dedicated
fourth register, R4, purely as a clock-control generator:

- R4 is clocked on *every* cycle, unconditionally.
- Three specific bits of R4's state are sampled and fed into the
  majority function.
- R1, R2 and R3 are each clocked only if their associated control bit
  (from R4) equals the majority value.

This means anywhere from zero to three of {R1, R2, R3} are clocked on a
given cycle (R4 always is), which is what makes the generator's period
and statistics resistant to simple linear analysis.

This module contains only the *decision* and *orchestration* logic; it
knows nothing about how an ``LFSR`` computes its own feedback -- that is
entirely encapsulated inside ``registers.LFSR``.
"""

from dataclasses import dataclass
from typing import Dict, Tuple

from constants import (
    CONTROL_BIT_POSITIONS,
    REGISTER_NAMES,
)
from majority import majority
from registers import LFSR


@dataclass(frozen=True)
class ClockDecision:
    """
    The outcome of a single clock-control evaluation.

    :param control_bits: The three sampled control bits, in
        ``(for_R1, for_R2, for_R3)`` order.
    :param majority_value: The majority of ``control_bits``.
    :param clocked: Which of R1/R2/R3/R4 were actually clocked this
        cycle, in ``REGISTER_NAMES`` order.
    """

    control_bits: Tuple[int, int, int]
    majority_value: int
    clocked: Tuple[bool, bool, bool, bool]


class ClockController:
    """
    Implements the A5-GMR-1 irregular clocking rule over four named
    registers.

    :param registers: A mapping from register name (``"R1"``..``"R4"``)
        to the corresponding :class:`~registers.LFSR` instance. Must
        contain all four names defined in ``constants.REGISTER_NAMES``.
    """

    def __init__(self, registers: Dict[str, LFSR]) -> None:
        missing = [name for name in REGISTER_NAMES if name not in registers]
        if missing:
            raise ValueError(f"missing registers: {missing}")
        self._registers = registers

    def _sample_control_bits(self) -> Tuple[int, int, int]:
        """Read the three clock-control bits out of R4's current state."""
        control_register = self._registers["R4"]
        return tuple(
            control_register.get_bit(position) for position in CONTROL_BIT_POSITIONS
        )  # type: ignore[return-value]

    def force_clock_all(self) -> None:
        """
        Unconditionally clock all four registers.

        Used only during the key-mixing stage of initialization, where
        every register advances on every cycle regardless of the normal
        clocking rule.
        
        """
        for name in REGISTER_NAMES:
            self._registers[name].clock()

    def step(self) -> ClockDecision:
        """
        Perform one cycle of the normal (post key-mixing) irregular
        clocking rule:

        1. R4 is always clocked first (it generates the control signal
           for *this* cycle from its state *before* being clocked, so we
           sample before clocking it).
        2. Three control bits are sampled from R4's pre-clock state.
        3. The majority of those three bits is computed.
        4. R1, R2, R3 are each clocked if and only if their associated
           control bit equals the majority value.

        :return: A :class:`ClockDecision` describing what happened, for
            use by the debug tracer.
        """
        control_bits = self._sample_control_bits()
        majority_value = majority(*control_bits)

        clock_r1 = control_bits[0] == majority_value
        clock_r2 = control_bits[1] == majority_value
        clock_r3 = control_bits[2] == majority_value

        if clock_r1:
            self._registers["R1"].clock()
        if clock_r2:
            self._registers["R2"].clock()
        if clock_r3:
            self._registers["R3"].clock()
        # R4 always clocks, every cycle.
        self._registers["R4"].clock()

        return ClockDecision(
            control_bits=control_bits,
            majority_value=majority_value,
            clocked=(clock_r1, clock_r2, clock_r3, True),
        )
