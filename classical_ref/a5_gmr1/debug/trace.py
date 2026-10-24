"""
debug/trace.py
==============

A small, self-contained tracer used to print the internal state of the
A5-GMR-1 generator on every clock round when ``trace=True`` is passed to
:class:`cipher.A5GMR1`.

The tracer knows nothing about *how* the cipher works; it is simply
handed the already-computed pieces of information for a round (register
bit strings, clock decision, output trace, etc.) and formats them.
"""

from dataclasses import dataclass
from typing import Dict, Optional

from clocking import ClockDecision
from output import OutputTrace
from registers import LFSR


@dataclass
class RoundTrace:
    """
    All of the information about a single clock round that the tracer
    needs in order to print it.

    :param round_number: 1-based index of this round.
    :param registers_before: Snapshot of each register's bit string
        *before* clocking, keyed by register name.
    :param clock_decision: The :class:`~clocking.ClockDecision` for this
        round.
    :param registers_after: Snapshot of each register's bit string
        *after* clocking, keyed by register name.
    :param feedback_bits: The feedback bit computed for each register
        that was actually clocked this round (registers not clocked are
        omitted).
    :param output_trace: The :class:`~output.OutputTrace` for this round,
        or ``None`` if this round did not produce keystream output (e.g.
        during initialization).
    """

    round_number: int
    registers_before: Dict[str, str]
    clock_decision: ClockDecision
    registers_after: Dict[str, str]
    feedback_bits: Dict[str, int]
    output_trace: Optional[OutputTrace]


class Tracer:
    """Formats and prints :class:`RoundTrace` instances to stdout."""

    SEPARATOR = "-" * 32

    def print_round(self, trace: RoundTrace) -> None:
        """
        Print a single round's trace in a human-readable, labeled block.

        :param trace: The round information to print.
        """
        lines = [self.SEPARATOR, "", f"Round {trace.round_number}", ""]

        for name, bits in trace.registers_before.items():
            lines.append(name)
            lines.append(bits)
            lines.append("")

        lines.append("Clock bits")
        lines.append(" ".join(str(b) for b in trace.clock_decision.control_bits))
        lines.append("")

        lines.append("Majority")
        lines.append(str(trace.clock_decision.majority_value))
        lines.append("")

        clocked_names = [
            name
            for name, was_clocked in zip(
                ("R1", "R2", "R3", "R4"), trace.clock_decision.clocked
            )
            if was_clocked
        ]
        lines.append("Registers Clocked")
        lines.extend(clocked_names)
        lines.append("")

        lines.append("Feedback Bits")
        for name in ("R1", "R2", "R3", "R4"):
            if name in trace.feedback_bits:
                lines.append(f"{name} = {trace.feedback_bits[name]}")
        lines.append("")

        if trace.output_trace is not None:
            lines.append("Output Bit")
            lines.append(str(trace.output_trace.output_bit))
            lines.append("")

        lines.append(self.SEPARATOR)

        print("\n".join(lines))


def bits_string(register: LFSR) -> str:
    """
    Convenience helper: render a register's current state as a bit
    string (MSB first), for use when building a :class:`RoundTrace`.

    :param register: The register to render.
    :return: A string of ``0``/``1`` characters.
    """
    return "".join(str(bit) for bit in register.get_bits())
