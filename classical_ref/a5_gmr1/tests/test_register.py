"""
tests/test_register.py
=======================

Unit tests for the generic ``registers.LFSR`` class, independent of any
A5-GMR-1 specific configuration.
"""

import pytest

from registers import LFSR


def test_load_and_get_state() -> None:
    lfsr = LFSR(length=4, taps=0b0011)
    lfsr.load([1, 0, 1, 1])  # MSB first -> 0b1011 = 11
    assert lfsr.get_state() == 0b1011


def test_load_rejects_wrong_length() -> None:
    lfsr = LFSR(length=4, taps=0b0011)
    with pytest.raises(ValueError):
        lfsr.load([1, 0, 1])


def test_load_rejects_non_binary_bits() -> None:
    lfsr = LFSR(length=4, taps=0b0011)
    with pytest.raises(ValueError):
        lfsr.load([1, 0, 2, 1])


def test_reset() -> None:
    lfsr = LFSR(length=4, taps=0b0011)
    lfsr.load([1, 1, 1, 1])
    lfsr.reset()
    assert lfsr.get_state() == 0


def test_set_state_and_get_state() -> None:
    lfsr = LFSR(length=5, taps=0b00101)
    lfsr.set_state(0b10110)
    assert lfsr.get_state() == 0b10110


def test_set_state_rejects_out_of_range() -> None:
    lfsr = LFSR(length=4, taps=0b0011)
    with pytest.raises(ValueError):
        lfsr.set_state(1 << 4)
    with pytest.raises(ValueError):
        lfsr.set_state(-1)


def test_get_bit_and_set_bit() -> None:
    lfsr = LFSR(length=4, taps=0b0011)
    lfsr.load([0, 0, 0, 0])
    assert lfsr.get_bit(0) == 0
    lfsr.set_bit(0, 1)
    assert lfsr.get_bit(0) == 1
    assert lfsr.get_state() == 0b0001


def test_compute_feedback_is_parity_of_tapped_bits() -> None:
    # taps select bits 0 and 1; state 0b0011 -> bits 0,1 are 1,1 -> parity 0
    lfsr = LFSR(length=4, taps=0b0011)
    lfsr.load([0, 0, 1, 1])
    assert lfsr.compute_feedback() == 0

    # state 0b0001 -> bit0=1, bit1=0 -> parity 1
    lfsr.load([0, 0, 0, 1])
    assert lfsr.compute_feedback() == 1


def test_clock_shifts_left_and_inserts_feedback() -> None:
    # A 4-bit register with taps on bits 0 and 1.
    lfsr = LFSR(length=4, taps=0b0011)
    lfsr.load([0, 0, 0, 1])  # state = 0b0001
    feedback = lfsr.clock()
    # feedback = parity(bit0=1, bit1=0) = 1
    assert feedback == 1
    # shift left: 0b0001 -> 0b0010, then OR in feedback at bit0 -> 0b0011
    assert lfsr.get_state() == 0b0011


def test_clock_masks_overflow_bits() -> None:
    # Ensure bits shifted beyond the register length are discarded.
    lfsr = LFSR(length=3, taps=0b000)  # no taps -> feedback always 0
    lfsr.load([1, 0, 1])  # state = 0b101
    lfsr.clock()
    # shift left: 0b101 -> 0b1010, masked to 3 bits -> 0b010
    assert lfsr.get_state() == 0b010


def test_maximal_length_sequence_never_repeats_within_one_period() -> None:
    # A 4-bit maximal-length LFSR (taps at bits 0 and 3) should visit all
    # 15 non-zero states before repeating, since 0b1001 was empirically
    # verified to produce a full-period sequence under this feedback
    # scheme (feedback = parity(state & taps), then shift-left-and-insert).
    lfsr = LFSR(length=4, taps=0b1001)
    lfsr.load([0, 0, 0, 1])
    seen = set()
    state = lfsr.get_state()
    for _ in range(15):
        assert state not in seen
        seen.add(state)
        lfsr.clock()
        state = lfsr.get_state()
    assert len(seen) == 15
    assert lfsr.get_state() == 0b0001  # back to the start after 15 clocks


def test_get_clock_bit_and_get_output_bit() -> None:
    lfsr = LFSR(
        length=4,
        taps=0b0011,
        clock_bit_positions=(2,),
        output_bit_position=3,
    )
    lfsr.load([1, 0, 1, 1])  # state = 0b1011: bit2=0, bit3=1
    assert lfsr.get_clock_bit() == 0
    assert lfsr.get_output_bit() == 1


def test_get_clock_bit_without_configuration_raises() -> None:
    lfsr = LFSR(length=4, taps=0b0011)
    with pytest.raises(ValueError):
        lfsr.get_clock_bit()


def test_get_output_bit_without_configuration_raises() -> None:
    lfsr = LFSR(length=4, taps=0b0011)
    with pytest.raises(ValueError):
        lfsr.get_output_bit()


def test_constructor_rejects_invalid_configuration() -> None:
    with pytest.raises(ValueError):
        LFSR(length=0, taps=0)
    with pytest.raises(ValueError):
        LFSR(length=4, taps=1 << 4)
    with pytest.raises(ValueError):
        LFSR(length=4, taps=0, clock_bit_positions=(4,))
    with pytest.raises(ValueError):
        LFSR(length=4, taps=0, output_bit_position=4)
