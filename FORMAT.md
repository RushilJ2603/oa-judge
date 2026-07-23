# Problem package format

Every problem is a folder `problems/<id>/`. `<id>` is kebab-case, `company-qN-slug`
(e.g. `deshaw-q2-max-flips`). The server loads whatever is present; missing optional files degrade
gracefully. **`problems/flipkart-q1-golden-price/` is the reference implementation — clone its shape.**

```
problems/<id>/
  problem.json      required   metadata (schema below)
  statement.md      required   the problem statement shown to the solver
  editorial.md      optional   solution writeup + traps (bundled in-app; shown after solving)
  stub.cpp          required if "cpp" in languages   starter code the user edits
  stub.py           required if "py"  in languages
  reference.cpp     (Claude adds)   verified reference solution — DO NOT WRITE; Claude owns these
  reference.py      (Claude adds)
  generator.py      optional but wanted   prints ONE random valid input to stdout (stress mode)
  tests/
    sample/  01.in 01.out ...          visible in both modes; mirror the statement's examples
    edge/    NN.in (curated inputs)     LC/OA-grade edge cases — hand-written INPUTS only
    hidden/  (Claude generates)         built by make_hidden.py = solved edge/ + random generator
```

### Test-design standard (what "hidden" must cover)

`make_hidden.py` builds `tests/hidden/` from two layers, both with outputs computed by running the
verified reference (never hand-written):

1. **Curated edge cases** — hand-written `tests/edge/*.in`. This is the LC/OA-grade coverage and is
   required for every runnable problem. Cover, as applicable:
   - **Bounds:** minimum (n=1, empty where legal) and maximum sizes; values at the constraint limits.
   - **Degenerate/structural:** all-equal, all-distinct, already-sorted, reverse-sorted, single
     element, no-valid-answer case, everything-valid case.
   - **Adversarial:** inputs that break the common wrong solutions — overflow triggers (values forcing
     64-bit), the strict-vs-nonstrict boundary, unordered input when order isn't guaranteed, decoy
     records that must be ignored.
   - **Scale:** at least one maximum-size input, to separate a correct solution from a TLE one.
2. **Random cases** — from `generator.py` across a spread of sizes (including the max).

`tests/edge/` holds only `.in` files and is durable — rerunning `make_hidden.py` recomputes the `.out`
from the reference but never deletes the curated inputs.

## problem.json schema

```json
{
  "id": "flipkart-q1-golden-price",
  "title": "Golden Price",
  "company": "Flipkart",
  "difficulty": "Easy",                 // Easy | Medium | Hard
  "tags": ["math", "digits", "brute-force"],
  "languages": ["cpp"],                 // subset of ["cpp","py"]
  "runnable": true,                     // false => statement-only (no reference/tests yet)
  "io_mode": "stdin_stdout",            // v1 always this
  "compare": "tokens",                  // "tokens" (default) | "exact"
  "limits": {"time_ms": 2000, "memory_mb": 256},
  "origin": "Flipkart HirePro OA (transcribed from 45 photos)",
  "links": [                            // filled by the research agent; [] if none found
    {"site": "LeetCode", "url": "https://leetcode.com/problems/...", "note": "similar structure"}
  ]
}
```

Notes:
- `difficulty` is your best judgement from the algorithm required.
- `tags` should be the real techniques (e.g. `bitmask-dp`, `bfs`, `greedy`, `sqrt-decomposition`).
- Set `time_ms` generously (2000 default; 3000 for heavy DP). `memory_mb` 256 default.
- If a problem has no random-generatable structure (rare), omit `generator.py`; stress mode will
  report `no_generator`.

## statement.md conventions

Plain Markdown. Include, in order: the problem prose, **Input** format, **Output** format,
**Constraints**, and at least one worked **Example** with input/output. Do **not** carry over the
notes' `::: callout` fences, `[recon]`/`[assumed]` margin tags, or meta-commentary about
transcription — this is the clean solver-facing statement. Keep the actual constraints and samples;
drop the authoring narrative.

Where the source problem was ambiguous and a reading was chosen (Uber Q1, Uber Q3), state the chosen
rule plainly as *the* rule. Do not present multiple readings to the solver — the judge commits to one.

## stub conventions

The stub is what the solver starts from. Reproduce the **original OA harness** where one existed
(the `main()` that does I/O + the function signature with `// WRITE YOUR CODE HERE`), because
practising against the real harness is the point. For problems that never had a fixed harness
(the recall-only ones), provide a minimal `main()` that reads the stated input format and a clearly
marked spot to solve, matching the reference's I/O exactly.

The stub must **compile as-is** (it may print nothing or a wrong answer, but g++ must accept it), so
the solver's first Run doesn't error on a syntax problem they didn't cause.

## generator.py conventions

- Prints exactly one valid input instance to stdout, in the problem's input format.
- Reads an optional integer seed from `argv[1]`; if absent, seed from entropy. Deterministic per seed.
- Accepts an optional `argv[2]` "size" hint (small by default) so stress mode can start tiny and grow;
  keep default instances SMALL (n ≤ ~12) so shrinking is fast and counterexamples are readable.
- Must only ever emit inputs that satisfy the stated constraints.

## What the packaging agent produces vs. what Claude owns

**You (Gemini) produce:** `problem.json`, `statement.md`, `editorial.md`, `stub.cpp`/`stub.py`,
`generator.py`, and the `tests/sample/*` files (transcribe the statement's own examples verbatim).

**Claude owns and will add:** `reference.cpp`/`reference.py` (already verified — copied from
`_migrated_raw/*/src/`), and all of `tests/hidden/*` (generated by running the reference). Never write
or overwrite a `reference.*` file or anything under `tests/hidden/`.
