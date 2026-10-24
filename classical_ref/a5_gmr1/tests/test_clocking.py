"""
tests/test_clocking.py
=======================

Unit tests for ``clocking.ClockController``, verifying both the
majority-based irregular clocking decision and the forced-clocking mode
used during initialization.
"""

import pytest

from clocking import ClockController
from constants import (
    CONTROL_BIT_POSITIONS,
    R1_LENGTH,
    R1_TAPS,
    R2_LENGTH,
    R2_TAPS,
    R3_LENGTH,
    R3_TAPS,
    R4_LENGTH,
    R4_TAPS,
)
from registers import LFSR


def _build_registers():
    return {
        "R1": LFSR(length=R1_LENGTH, taps=R1_TAPS),
        "R2": LFSR(length=R2_LENGTH, taps=R2_TAPS),
        "R3": LFSR(length=R3_LENGTH, taps=R3_TAPS),
        "R4": LFSR(
            length=R4_LENGTH, taps=R4_TAPS, clock_bit_positions=CONTROL_BIT_POSITIONS
        ),
    }


def _set_control_bits(registers, bit_for_r1: int, bit_for_r2: int, bit_for_r3: int) -> None:
    """Force R4's three control bits to specific values without touching
    any other bit of its state."""
    r4 = registers["R4"]
    for position, value in zip(CONTROL_BIT_POSITIONS, (bit_for_r1, bit_for_r2, bit_for_r3)):
        r4.set_bit(position, value)


def test_missing_register_raises() -> None:
    registers = _build_registers()
    del registers["R3"]
    with pytest.raises(ValueError):
        ClockController(registers)


@pytest.mark.parametrize(
    "control_bits, expected_majority, expected_clocked",
    [
        ((0, 0, 0), 0, (True, True, True)),
        ((1, 1, 1), 1, (True, True, True)),
        ((1, 0, 0), 0, (False, True, True)),
        ((0, 1, 0), 0, (True, False, True)),
        ((0, 0, 1), 0, (True, True, False)),
        ((0, 1, 1), 1, (False, True, True)),
        ((1, 0, 1), 1, (True, False, True)),
        ((1, 1, 0), 1, (True, True, False)),
    ],
)
def test_step_clocks_registers_matching_majority(
    control_bits, expected_majority, expected_clocked
) -> None:
    registers = _build_registers()
    _set_control_bits(registers, *control_bits)

    controller = ClockController(registers)
    decision = controller.step()

    assert decision.control_bits == control_bits
    assert decision.majority_value == expected_majority
    assert decision.clocked == (*expected_clocked, True)  # R4 always clocked


def test_step_always_clocks_r4() -> None:
    registers = _build_registers()
    registers["R4"].load([1, 0, 1] + [0] * (R4_LENGTH - 3))
    expected_r4 = LFSR(length=R4_LENGTH, taps=R4_TAPS)
    expected_r4.set_state(registers["R4"].get_state())
    expected_r4.clock()

    controller = ClockController(registers)
    decision = controller.step()

    assert decision.clocked[3] is True
    assert registers["R4"].get_state() == expected_r4.get_state()


def test_force_clock_all_clocks_every_register() -> None:
    # Build two independent, identically-loaded sets of registers: one
    # advanced directly through LFSR.clock(), the other advanced through
    # ClockController.force_clock_all(). They must end up in the same
    # states, proving force_clock_all() clocks every register exactly
    # once via the standard clocking operation.
    registers_direct = _build_registers()
    registers_forced = _build_registers()

    initial_patterns = {
        "R1": [1, 0, 1] + [0] * (R1_LENGTH - 3),
        "R2": [0, 1, 1] + [0] * (R2_LENGTH - 3),
        "R3": [1, 1, 0] + [0] * (R3_LENGTH - 3),
        "R4": [1, 0, 0] + [0] * (R4_LENGTH - 3),
    }
    for name, pattern in initial_patterns.items():
        registers_direct[name].load(pattern)
        registers_forced[name].load(pattern)

    for reg in registers_direct.values():
        reg.clock()

    controller = ClockController(registers_forced)
    controller.force_clock_all()

    for name in initial_patterns:
        assert registers_direct[name].get_state() == registers_forced[name].get_state()
