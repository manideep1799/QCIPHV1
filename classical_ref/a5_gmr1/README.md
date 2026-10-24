# A5-GMR-1 Reference Classical Implementation

A clean, modular, pure-Python (3.11+) implementation of the **A5-GMR-1**
stream cipher, based on the Osmocom reverse-engineered specification
(https://osmocom.org/projects/gmr/wiki/A5-GMR-1) and the published
academic analysis of the algorithm (Driessen, Hund, Willems, Paar, Holz,
*"Don't Trust Satellite Phones"*, and Driessen, *"Initialisation flaws in
the A5-GMR-1 satphone encryption algorithm"*).

**This is not production cryptographic software.** A5-GMR-1 is a broken,
deprecated satellite-phone cipher; this code exists purely as a
well-documented **reference classical implementation**, intended as the
starting point for a later **reversible (Qiskit-based) quantum
implementation** and **Grover oracle construction**. Every function was
written to correspond to one clearly delimited logical operation so that
it can be translated into a small reversible quantum sub-circuit later,
rather than to be fast or idiomatic "clever" Python.

---

## 1. What the cipher does, in one paragraph

A5-GMR-1 is a synchronous stream cipher built from four Linear Feedback
Shift Registers (LFSRs): **R1** (19 bits), **R2** (22 bits), **R3** (23
bits), and **R4** (17 bits, dedicated purely to clock control). Given a
64-bit secret key and a 19-bit frame number, the cipher mixes them into
the (initially all-zero) registers, runs 250 "warm-up" clock cycles, and
then produces one keystream bit per clock cycle thereafter. Plaintext is
encrypted (and ciphertext decrypted) simply by XORing it with this
keystream.

---

## 2. Architecture / module map

```
a5_gmr1/
├── constants.py       Every magic number in the cipher (lengths, taps,
│                      control-bit positions, output formula positions,
│                      round counts). Nothing elsewhere hardcodes numbers.
│
├── utils.py           Generic bit-twiddling helpers (get_bit, set_bit,
│                      parity, bit <-> int packing). No cipher knowledge.
│
├── registers.py        `LFSR` — a fully generic, reusable linear feedback
│                      shift register. Knows nothing about A5-GMR-1.
│
├── majority.py         `majority(a, b, c)` — the 3-input majority
│                      function, used both for clock control and output.
│
├── clocking.py         `ClockController` — implements A5-GMR-1's specific
│                      irregular-clocking rule (R4 always clocks and
│                      supplies the control signal; R1/R2/R3 clock only
│                      when their control bit matches the majority).
│
├── initialization.py   `Initializer` — key/frame reorganization, forced-
│                      clock key loading, forced non-zero bit, and the
│                      250-round mixing stage.
│
├── output.py           `OutputFunction` — derives one keystream bit per
│                      cycle from the current states of R1/R2/R3.
│
├── cipher.py            `A5GMR1` — the only class a user needs. Wires the
│                      above modules together and exposes initialize(),
│                      clock(), generate_bit(), generate_keystream(),
│                      encrypt(), decrypt().
│
├── debug/
│   └── trace.py         `Tracer` — optional, purely presentational
│                      per-round trace printer (activated via
│                      `A5GMR1(..., trace=True)`).
│
├── tests/               Independent unit tests for every module above.
│
└── main.py              End-to-end example usage.
```

Each module is independently unit-testable and has **no upward
dependency** on `cipher.py` — `cipher.py` is purely an orchestrator that
imports everything else, never the other way around.

---

## 3. Execution flow

### 3.1 Initialization (`Initializer.initialize`)

1. **Reorganize key + frame number** (`Initializer.reorganize_key`)
   The 8 raw key bytes are swapped in adjacent pairs
   (`[0,1,2,3,4,5,6,7] -> [1,0,3,2,5,4,7,6]`), then bits of the (up to
   19-bit) frame number are XORed into specific byte positions of the
   result. This produces the 64-bit value that is actually mixed into
   the registers.

2. **Load key material via forced clocking**
   (`Initializer.load_key_material`)
   All four registers start at all-zero. For each of the 64
   reorganized-key bits (MSB of byte 0 first):
   - `ClockController.force_clock_all()` unconditionally clocks **all
     four** registers (this is different from the normal irregular
     clocking rule used later).
   - The key bit is then XORed directly into bit 0 of every register.

3. **Force non-zero bit** (`Initializer.force_nonzero_bit`)
   Bit 0 of every register is forced to `1`, guaranteeing no register is
   left in the degenerate all-zero LFSR state.

4. **Mixing stage** (`Initializer.run_mixing_rounds`)
   The registers are advanced for 250 cycles using the *normal*
   irregular clocking rule (`ClockController.step`), and all output is
   discarded. This "warms up" the internal state.

### 3.2 Keystream generation (`A5GMR1.generate_bit` / `generate_keystream`)

Once initialized, each call to `generate_bit()`:

1. Runs one cycle of `ClockController.step()`:
   - Samples 3 control bits out of R4's *current* state (bit 15 controls
     R1, bit 6 controls R2, bit 1 controls R3).
   - Computes `majority()` of those 3 bits.
   - Clocks R1, R2, R3 individually if (and only if) their control bit
     matches the majority value.
   - Always clocks R4 (the control register itself never "skips" a
     cycle).
2. Runs `OutputFunction.compute()` against the *new* register states:
   for each of R1, R2, R3, three tapped bits are combined via
   `majority()` and the result is XORed with one further tapped bit;
   the three per-register contributions are then XORed together to
   form the single output keystream bit.

`generate_keystream(n)` simply calls `generate_bit()` `n` times and
collects the results.

### 3.3 Encryption / decryption

Because A5-GMR-1 is a synchronous stream cipher, `encrypt()` and
`decrypt()` are both implemented as "generate a keystream the same
length as the input, then XOR it in" — the two methods exist separately
purely for readability at call sites, not because the underlying
operation differs.

---

## 4. Debug trace mode

Passing `trace=True` to the `A5GMR1` constructor causes every call to
`generate_bit()` (and therefore `generate_keystream()`) to print a
labeled block describing that round's internal state:

```
--------------------------------

Round 37

R1
101001101...

R2
011010011...

R3
110100010...

R4
001101...

Clock bits
1 0 1

Majority
1

Registers Clocked
R1
R3
R4

Feedback Bits
R1 = 0
R2 = 1
R3 = 1
R4 = 0

Output Bit
1

--------------------------------
```

- The register bit-strings shown are the state **before** that round's
  clocking is applied.
- "Feedback Bits" lists the feedback value computed for every register
  that was actually clocked that round (a register that was skipped by
  the irregular clocking rule contributes no feedback bit that round).
- Note that R4 is always present in "Registers Clocked" and "Feedback
  Bits", since it is unconditionally clocked every cycle.

This tracing is implemented entirely in `debug/trace.py` and `cipher.py`
— none of `registers.py`, `clocking.py`, `initialization.py`, or
`output.py` know that tracing exists.

---

## 5. Usage

```python
from cipher import A5GMR1

cipher = A5GMR1(
    key=bytes([0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF]),
    frame_number=42,
)
cipher.initialize()

keystream = cipher.generate_keystream(114)
print(keystream)

# Encryption / decryption
plaintext = [1, 0, 1, 1, 0, 0, 1, 0] * 14

enc_cipher = A5GMR1(key=..., frame_number=42)
enc_cipher.initialize()
ciphertext = enc_cipher.encrypt(plaintext)

dec_cipher = A5GMR1(key=..., frame_number=42)
dec_cipher.initialize()
recovered = dec_cipher.decrypt(ciphertext)
assert recovered == plaintext

# Debug trace mode
traced = A5GMR1(key=..., frame_number=42, trace=True)
traced.initialize()
traced.generate_keystream(3)  # prints a trace block per round
```

Run the bundled example directly:

```bash
cd a5_gmr1
python3 main.py
```

---

## 6. Running the tests

```bash
cd a5_gmr1
pip install pytest
python3 -m pytest tests/ -v
```

Tests are organized to mirror the module structure:

| Test file                    | Covers                                            |
|-------------------------------|----------------------------------------------------|
| `test_majority.py`            | All 8 input combinations of `majority()`           |
| `test_register.py`            | Generic `LFSR` behavior (load, clock, feedback, maximal-length cycling) |
| `test_clocking.py`            | Irregular clocking decisions and forced clocking   |
| `test_initialization.py`      | Key/frame reorganization, key loading, forced bit, mixing, determinism |
| `test_cipher.py`               | End-to-end orchestration, determinism, encrypt/decrypt round trip, trace mode |

---

## 7. A note on correctness and provenance

The register lengths, tap masks, clock-control bit positions, and output
formula in `constants.py` were derived from the Osmocom project's
publicly reverse-engineered A5-GMR-1 specification and cross-checked
against the peer-reviewed academic literature describing the same
algorithm's structure and known initialization weaknesses. Because
A5-GMR-1 was reverse-engineered from a compiled DSP binary rather than
published as an official standard, no independent, universally agreed
"official" test vector set is available; `tests/test_cipher.py` includes
a regression test that pins the implementation's own output down, so
future refactors cannot silently change generator behavior.

## 8. Why this design, for the future quantum port

- **No global state, no hidden mutation**: every stateful object
  (`LFSR`, `ClockController`, `Initializer`, `OutputFunction`, `A5GMR1`)
  is an explicit, constructor-injected object graph. A reversible
  circuit needs explicit wiring between named quantum registers; this
  mirrors that directly.
- **Small, single-purpose functions**: `majority()`, `parity()`,
  `compute_feedback()`, and the per-register `_contribution()` helper in
  `output.py` each correspond to one elementary reversible operation
  (a Toffoli-like majority gate, a chain of CNOTs, etc.).
- **No shortcuts**: nothing is memoized, precomputed, or otherwise
  short-circuited across cycles, since a reversible circuit must be able
  to run every cycle's logic (forward and backward) explicitly.
