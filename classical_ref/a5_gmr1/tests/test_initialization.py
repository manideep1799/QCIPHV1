"""
tests/test_initialization.py
=============================

Unit tests for ``initialization.Initializer``, covering key/frame
reorganization, forced-clock key loading, the forced non-zero bit, and
the mixing stage.
"""

import pytest

from constants import (
    CONTROL_BIT_POSITIONS,
    FORCED_BIT_POSITION,
    KEY_LENGTH_BYTES,
    MIXING_ROUNDS,
    R1_LENGTH,
    R1_TAPS,
    R2_LENGTH,
    R2_TAPS,
    R3_LENGTH,
    R3_TAPS,
    R4_LENGTH,
    R4_TAPS,
)
from initialization import Initializer
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


def test_reorganize_key_swaps_byte_pairs_with_zero_frame_number() -> None:
    key = bytes(range(KEY_LENGTH_BYTES))  # 0,1,2,...,7
    reorganized = Initializer.reorganize_key(key, frame_number=0)
    # With frame_number = 0, no XOR mixing occurs, so we should see a
    # pure byte-pair swap: [0,1,2,3,4,5,6,7] -> [1,0,3,2,5,4,7,6]
    assert list(reorganized) == [1, 0, 3, 2, 5, 4, 7, 6]


def test_reorganize_key_rejects_wrong_length() -> None:
    with pytest.raises(ValueError):
        Initializer.reorganize_key(b"\x00" * 7, frame_number=0)


def test_reorganize_key_rejects_out_of_range_frame_number() -> None:
    with pytest.raises(ValueError):
        Initializer.reorganize_key(b"\x00" * KEY_LENGTH_BYTES, frame_number=1 << 19)
    with pytest.raises(ValueError):
        Initializer.reorganize_key(b"\x00" * KEY_LENGTH_BYTES, frame_number=-1)


def test_reorganize_key_changes_with_frame_number() -> None:
    key = bytes(range(KEY_LENGTH_BYTES))
    reorganized_a = Initializer.reorganize_key(key, frame_number=0)
    reorganized_b = Initializer.reorganize_key(key, frame_number=1)
    assert reorganized_a != reorganized_b


def test_missing_register_raises() -> None:
    registers = _build_registers()
    del registers["R2"]
    with pytest.raises(ValueError):
        Initializer(registers)


def test_load_key_material_resets_registers_first() -> None:
    registers = _build_registers()
    registers["R1"].load([1] * R1_LENGTH)  # dirty state

    initializer = Initializer(registers)
    reorganized_key = Initializer.reorganize_key(b"\x00" * KEY_LENGTH_BYTES, 0)
    initializer.load_key_material(reorganized_key)

    # After loading an all-zero key, feedback taps only ever see zero
    # bits and the injected key bit is always zero, so every register
    # must end up back at all-zero.
    for register in registers.values():
        assert register.get_state() == 0


def test_load_key_material_records_trace_bits() -> None:
    registers = _build_registers()
    initializer = Initializer(registers)
    reorganized_key = Initializer.reorganize_key(bytes(range(KEY_LENGTH_BYTES)), 5)
    initializer.load_key_material(reorganized_key)
    assert len(initializer.trace.key_mixing_bits) == 64
    assert set(initializer.trace.key_mixing_bits) <= {0, 1}


def test_force_nonzero_bit_sets_bit_zero_on_all_registers() -> None:
    registers = _build_registers()
    initializer = Initializer(registers)
    for register in registers.values():
        register.reset()
    initializer.force_nonzero_bit()
    for register in registers.values():
        assert register.get_bit(FORCED_BIT_POSITION) == 1


def test_run_mixing_rounds_advances_state_deterministically() -> None:
    registers_a = _build_registers()
    registers_b = _build_registers()
    for registers in (registers_a, registers_b):
        registers["R1"].load([1, 0] + [0] * (R1_LENGTH - 2))
        registers["R2"].load([0, 1] + [0] * (R2_LENGTH - 2))
        registers["R3"].load([1, 1] + [0] * (R3_LENGTH - 2))
        registers["R4"].load([0, 1] + [0] * (R4_LENGTH - 2))

    Initializer(registers_a).run_mixing_rounds(rounds=10)
    Initializer(registers_b).run_mixing_rounds(rounds=10)

    for name in registers_a:
        assert registers_a[name].get_state() == registers_b[name].get_state()


def test_full_initialize_produces_nonzero_state_and_is_deterministic() -> None:
    key = bytes([0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF])
    frame_number = 12345

    registers_a = _build_registers()
    initializer_a = Initializer(registers_a)
    initializer_a.initialize(key, frame_number)

    registers_b = _build_registers()
    initializer_b = Initializer(registers_b)
    initializer_b.initialize(key, frame_number)

    for name in registers_a:
        state_a = registers_a[name].get_state()
        state_b = registers_b[name].get_state()
        assert state_a == state_b  # deterministic
        assert state_a != 0  # forced non-zero bit guarantees this


def test_different_frame_numbers_produce_different_states() -> None:
    key = bytes([0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF])

    registers_a = _build_registers()
    Initializer(registers_a).initialize(key, frame_number=1)

    registers_b = _build_registers()
    Initializer(registers_b).initialize(key, frame_number=2)

    states_a = tuple(reg.get_state() for reg in registers_a.values())
    states_b = tuple(reg.get_state() for reg in registers_b.values())
    assert states_a != states_b


def test_mixing_rounds_constant_matches_specification() -> None:
    assert MIXING_ROUNDS == 250
