# Flipkart + DE Shaw OA — inventory & state

Mirrors the `cisco_questions/` pattern. Created 2026-07-18. **All work in this folder is COMPLETE
and folded into both PDFs** (appendix Part VII, plus the new debugging section in Part I-B).

## Sources on disk
- `../Flipkart & de shaw oa questions/` — 45 phone photos of the HirePro OA screen + one recall
  `.txt` for the DE Shaw questions. All 46 files are now registered in `NOTES_MANIFEST.json`.

## Contents
| File | Contents | Status |
|---|---|---|
| `flipkart_coding.md` | Q1 Golden Price (C++ harness), Q2 Marathon Checkpoints (C++ harness) | complete, `[recon]` marked |
| `flipkart_q4_logistics.md` | Q4 Shipment Delay-Risk — full spec, both samples, Python harness | complete, `[recon]` resolved |
| `flipkart_sql.md` | Hospital Management System SQL question + answer | complete, `[recon]` marked |
| `deshaw_coding.md` | 3 DE Shaw questions formalized from recall, `[assumed]` marked | complete |
| `solutions.md` | All 7 optimal solutions, every one compiled + verified | complete |
| `src/` | Working sources: `q1_golden.cpp`, `q2_marathon.cpp`, `ds_q1_player.cpp`, `ds_q2_flips.cpp`, `ds_q3_checker.cpp`, `q4_logistics.py` | all verified |

Transcription policy followed throughout: orchestrator vision only, no OCR, no subagents. All 45
photos were read; frames overlapped heavily (same question at different scroll offsets), so ~30
distinct screens produced the four transcription files.

## Verification record

| Problem | Verified against | Result |
|---|---|---|
| Flipkart Q1 Golden Price | both statement samples | `495`, `63270` ✓ |
| Flipkart Q2 Marathon | both statement samples | `65`, `58` ✓ |
| Flipkart Q4 Logistics | both statement samples | exact string match ✓ |
| Flipkart SQL | statement sample | `Bob,Williams` ✓ |
| DE Shaw Q1 Music Player | 300 random cases vs. naive `vector` | all match ✓ |
| DE Shaw Q2 Max Flips | 400 random cases vs. exhaustive 2ⁿ | all match ✓ |
| DE Shaw Q3 Checkerboard | 250 random grids vs. O((nm)²) brute force | all match ✓ |

**The brute-force checks caught two errors in the hand-written examples** — DE Shaw Q2's answer is 3,
not the 2 originally reasoned out, and DE Shaw Q1's example header declared 5 queries while supplying
4. Both are documented in place in `deshaw_coding.md` as worked lessons rather than quietly corrected,
because the failure mode they illustrate (trusting a hand-derived expected value, then "fixing"
correct code) is exactly what the debugging section is about.

## Platform facts (these drove the debugging section)
- Platform is **HirePro** (`inapp.hirepro.ai`), screen-share enforced.
- The editor gives a **fixed signature + a `main()` that does all the I/O**; you fill
  `// WRITE YOUR CODE HERE`. You cannot see the test cases.
- Both C++ statements warn: *"Do not print arbitrary strings anywhere in the program, as these
  contribute to the output and test cases will fail."* → **no debug `cout` survives**.
- Stubs seed the answer with a sentinel (`int sum = -1;`, `final_output = "NONE"`) — decoys.
- Q2's harness uses **VLAs** (`string str[N-1]`) — a GCC extension, not standard C++.
- Q4's stub is **Python 3** while Q1/Q2 are C++ — the platform is multi-language per question.

## Where this landed in the book
- **`sections/s30_oa_papers.md`** — the five files above, assembled with headings demoted one level,
  rendered as **Part VII · Appendix: Real OA Papers**.
- **`sections/s29_oa_debugging.md`** — "Debugging C++ Blind", Part I-B beside the OA Survival Kit.
  Authored by the orchestrator directly per explicit user directive (no Gemini, no subagents).

Both are registered in `NOTES_MANIFEST.json` and present in both rendered PDFs
(main 730 pp / 21.42 MB, concise 70 pp / 1.07 MB).

## Nothing outstanding in this folder.
Remaining project-level odds and ends are recorded in the `2026-07-18a` entry of `../NOTES_RULES.md`:
the manifest's `concepts: []` is still empty, and one pre-existing stray screenshot
(`ss/trees/…NVIDIA GeForce Overlay.png`) is still unassigned.
