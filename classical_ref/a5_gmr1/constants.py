"""
constants.py
============

Numeric constants that define the A5-GMR-1 keystream generator, taken
directly from the Osmocom reverse-engineered specification
(https://osmocom.org/projects/gmr/wiki/A5-GMR-1), which is itself based on
the published analysis of the algorithm extracted from a Thuraya satellite
phone DSP (Driessen, Hund, Willems, Paar, Holz).

A5-GMR-1 is built from **four** linear feedback shift registers:

    R1 - 19 bits   \
    R2 - 22 bits    |  irregularly clocked, contribute to keystream output
    R3 - 23 bits   /
    R4 - 17 bits   -- always clocked every cycle, controls the clocking
                      of R1/R2/R3 (this is the "clock control register")

No cipher logic lives anywhere else in the codebase except through these
named constants, so that the entire keystream generator can be re-derived
by reading this single file.
"""

from typing import Final, Tuple

# ---------------------------------------------------------------------------
# Register lengths (in bits)
# ---------------------------------------------------------------------------

R1_LENGTH: Final[int] = 19
R2_LENGTH: Final[int] = 22
R3_LENGTH: Final[int] = 23
R4_LENGTH: Final[int] = 17

REGISTER_LENGTHS: Final[Tuple[int, int, int, int]] = (
    R1_LENGTH,
    R2_LENGTH,
    R3_LENGTH,
    R4_LENGTH,
)

# ---------------------------------------------------------------------------
# Feedback taps
# ---------------------------------------------------------------------------
# Each tap set is expressed as a bitmask over the register's *current* state
# (bit 0 = least significant / rightmost bit). When a register is clocked,
# all bits selected by the mask are XORed together (a "parity" computation)
# to produce a single feedback bit. The register is then shifted left by
# one position and the feedback bit is inserted at bit 0.
#
# These masks and the corresponding primitive polynomials are exactly the
# ones reverse engineered by Osmocom / the Driessen et al. paper.

R1_TAPS: Final[int] = 0x072000  # x^19 + x^18 + x^17 + x^14 + 1
R2_TAPS: Final[int] = 0x311000  # x^22 + x^21 + x^17 + x^13 + 1
R3_TAPS: Final[int] = 0x660000  # x^23 + x^22 + x^19 + x^18 + 1
R4_TAPS: Final[int] = 0x013100  # x^17 + x^14 + x^13 + x^9  + 1

REGISTER_TAPS: Final[Tuple[int, int, int, int]] = (
    R1_TAPS,
    R2_TAPS,
    R3_TAPS,
    R4_TAPS,
)

# ---------------------------------------------------------------------------
# Clock control
# ---------------------------------------------------------------------------
# R4 is clocked every single cycle unconditionally ("forced" clocking) and
# never contributes to the output directly. Instead, three of its bit
# positions are sampled and fed into a majority function; R1, R2 and R3 are
# each clocked only if their associated control bit agrees with the
# majority value. This is the same "stop/go" family of clock control used
# in A5/1, but here the control signal is taken from an entirely separate
# register (R4) rather than from bits of R1/R2/R3 themselves.
#
# Mapping: control bit for R1 <- R4 bit 15
#          control bit for R2 <- R4 bit 6
#          control bit for R3 <- R4 bit 1

R4_CONTROL_BIT_FOR_R1: Final[int] = 15
R4_CONTROL_BIT_FOR_R2: Final[int] = 6
R4_CONTROL_BIT_FOR_R3: Final[int] = 1

CONTROL_BIT_POSITIONS: Final[Tuple[int, int, int]] = (
    R4_CONTROL_BIT_FOR_R1,
    R4_CONTROL_BIT_FOR_R2,
    R4_CONTROL_BIT_FOR_R3,
)

# ---------------------------------------------------------------------------
# Output function
# ---------------------------------------------------------------------------
# Each of R1, R2, R3 contributes one bit to the keystream output on every
# clock cycle. For a given register, three bits are sampled and combined
# with a majority function, and the result is XORed with one further bit
# from the same register. The three per-register results are then XORed
# together to form the single output keystream bit.
#
#   contribution(Rk) = majority(Rk[a], Rk[b], Rk[c]) XOR Rk[d]

R1_OUTPUT_MAJORITY_BITS: Final[Tuple[int, int, int]] = (1, 6, 15)
R1_OUTPUT_XOR_BIT: Final[int] = 11

R2_OUTPUT_MAJORITY_BITS: Final[Tuple[int, int, int]] = (3, 8, 14)
R2_OUTPUT_XOR_BIT: Final[int] = 1

R3_OUTPUT_MAJORITY_BITS: Final[Tuple[int, int, int]] = (4, 15, 19)
R3_OUTPUT_XOR_BIT: Final[int] = 0

# ---------------------------------------------------------------------------
# Initialization parameters
# ---------------------------------------------------------------------------

KEY_LENGTH_BYTES: Final[int] = 8
KEY_LENGTH_BITS: Final[int] = KEY_LENGTH_BYTES * 8  # 64

# Number of clock cycles used while mixing the key/frame-number bits into
# the (initially all-zero) registers. One key bit is injected per cycle.
KEY_MIXING_ROUNDS: Final[int] = KEY_LENGTH_BITS  # 64

# After key mixing, bit 0 of every register is forced to 1. This guarantees
# that no register is left in the all-zero state (which would be a
# degenerate, non-maximal-length state for an LFSR).
FORCED_BIT_POSITION: Final[int] = 0

# Number of additional (irregularly clocked) rounds run after key mixing
# and before any keystream bits are produced. This "warms up" the
# generator so that early keystream bits do not leak the raw key/frame
# structure.
MIXING_ROUNDS: Final[int] = 250

# Maximum size of the frame number field used during initialization
# (19 bits per the published GMR-1 specification).
FRAME_NUMBER_BITS: Final[int] = 19
FRAME_NUMBER_MASK: Final[int] = (1 << FRAME_NUMBER_BITS) - 1

# Register names, used throughout the codebase for indexing/tracing.
REGISTER_NAMES: Final[Tuple[str, str, str, str]] = ("R1", "R2", "R3", "R4")
