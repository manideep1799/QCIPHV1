"""
cycle/full_cycle.py
======================

Quantum counterpart to clocking.ClockController.step(), composed with
output.OutputFunction.compute().

Mirrors the classical logic exactly:
    1. Sample R4's control bits (positions from CONTROL_BIT_POSITIONS),
       from R4's PRE-clock state.
    2. Majority of the 3 control bits.
    3. Equality: does each control bit match the majority? -> clk_1/2/3
    4. Conditionally clock R1/R2/R3 (Construction B, controlled).
    5. (if include_output) Output block, using the NEW post-clock
       R1/R2/R3 state.
    6. Uncompute clk_1/2/3, then maj -- in exact reverse order.
    7. ONLY NOW clock R4 (Construction B, unconditional).

Step 7's ordering (R4 clocked LAST, after uncomputation) is the
corrected ordering from Doc 05 / Doc 09 D9: R4's control bits (positions
in CONTROL_BIT_POSITIONS) are read again during uncomputation (to
invert the equality computation), so R4 must not be clocked until that
uncomputation is complete -- clocking R4 first would overwrite the very
qubits the uncomputation needs to read.
"""

from qiskit import QuantumCircuit

from blocks.register_clock import append_register_clock, append_controlled_register_clock
from blocks.primitives import append_majority, append_unmajority, append_equality, append_unequality
from blocks.output import append_output_block
from cycle.layout import CipherLayout


def append_full_cycle(qc: QuantumCircuit, layout: CipherLayout, include_output: bool, keystream_qubit: int = None) -> None:
    r4_off = layout.register_offset["R4"]
    cb0 = r4_off + layout.control_bit_positions[0]
    cb1 = r4_off + layout.control_bit_positions[1]
    cb2 = r4_off + layout.control_bit_positions[2]

    # Step 1 (implicit): cb0/cb1/cb2 are read directly, no gates.

    # Step 2: Majority -> maj
    append_majority(qc, cb0, cb1, cb2, layout.maj)

    # Step 3: Equality x3 -> clk_1, clk_2, clk_3
    append_equality(qc, cb0, layout.maj, layout.clk1)
    append_equality(qc, cb1, layout.maj, layout.clk2)
    append_equality(qc, cb2, layout.maj, layout.clk3)

    # Step 4: Conditional clock R1/R2/R3 (Construction B, controlled)
    for name, clk in (("R1", layout.clk1), ("R2", layout.clk2), ("R3", layout.clk3)):
        L = layout.register_lengths[name]
        taps = layout.register_taps[name]
        base = layout.register_offset[name]
        append_controlled_register_clock(qc, L, taps, control=clk, base=base)

    # Step 5 (if generation cycle): Output block, using NEW R1/R2/R3 state
    if include_output:
        if keystream_qubit is None:
            raise ValueError("keystream_qubit required when include_output=True")
        specs = []
        m_ancillas = [layout.m1, layout.m2, layout.m3]
        for name in ("R1", "R2", "R3"):
            base = layout.register_offset[name]
            (a, b, c), xor_bit = layout.output_specs[name]
            specs.append(((base + a, base + b, base + c), base + xor_bit))
        append_output_block(qc, specs, m_ancillas, layout.out, keystream_qubit)

    # Step 6: uncompute clk_3, clk_2, clk_1, then maj -- while cb0/cb1/cb2
    # (R4's bits) are STILL INTACT (R4 has not been clocked yet).
    append_unequality(qc, cb2, layout.maj, layout.clk3)
    append_unequality(qc, cb1, layout.maj, layout.clk2)
    append_unequality(qc, cb0, layout.maj, layout.clk1)
    append_unmajority(qc, cb0, cb1, cb2, layout.maj)

    # Step 7 (CORRECTED ORDERING -- see Doc 05 / Doc 09 D9): R4's
    # unconditional clock happens LAST, only after all uncomputation
    # depending on R4's pre-clock bits is complete.
    L4 = layout.register_lengths["R4"]
    taps4 = layout.register_taps["R4"]
    append_register_clock(qc, L4, taps4, base=r4_off)
