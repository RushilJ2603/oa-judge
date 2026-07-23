# Packaging brief — per-problem I/O contracts

Read this with `FORMAT.md` (the package format) and the completed example
`problems/flipkart-q1-golden-price/` (copy its shape exactly). For each problem below you produce, in
`problems/<id>/`: `problem.json`, `statement.md`, `editorial.md`, `stub.<lang>`, `generator.py`, and
`tests/sample/NN.in`+`NN.out` (transcribe the statement's own worked examples verbatim).

**Do NOT create or edit `reference.cpp` / `reference.py` or anything under `tests/hidden/` — those
already exist and are owned by Claude.** Read the existing `reference.*` in each folder to lock the
exact input/output format your stub and generator must follow. The statement's numeric samples must
match what the reference actually prints (Claude will re-derive hidden tests from the reference and
verify your samples).

The full original statements (clean, already formalized) live under `_migrated_raw/`. Extract the
solver-facing statement from there; **strip** all `::: callout` fences, `[recon]`/`[assumed]` tags,
and transcription commentary. Where a reading was chosen for an ambiguous problem, state it as the
single rule.

General rules:
- `stub.<lang>` must compile/parse as-is (may print nothing) and reproduce the original OA harness
  where one is shown in the source (function signature + `main()` doing I/O + `// WRITE YOUR CODE
  HERE`). For recall-only problems, give a minimal `main()` reading the stated format.
- `generator.py`: `argv[1]`=seed, `argv[2]`=size hint; default SMALL; only emit inputs satisfying the
  constraints. Deterministic per seed.
- `difficulty`/`tags`: your judgement from the algorithm.

---

### flipkart-q2-marathon-checkpoints  (cpp)
- Source statement: `_migrated_raw/flipkart_deshaw/flipkart_coding.md` → "Q2 — Marathon Checkpoints".
- **Reproduce the exact original harness** shown there (it uses VLAs `string str[N-1]` — keep them;
  they compile on g++). Signature `int sumCheckPoints(int N,int S,string pos[],int val[])`.
- Input: line1 `N`; line2 `S`; then `N-1` lines each `S_i X_i` (a path string like `LR` and an int).
  Output: one integer (sum of checkpoints having BOTH children).
- Samples (verbatim from source): `6\n70\nL 50\nLR 65\nLRL 60\nLRR 68\nLRRL 69` → `65`;
  and the 8-checkpoint one → `58`. Constraint `3 <= N <= 100`.
- generator: build a random small binary-tree by growing random L/R paths from the root; emit paths
  + random distinct-ish int values. Keep N ≤ ~12 by default.

### flipkart-q4-shipment-delay-risk  (py)
- Source: `_migrated_raw/flipkart_deshaw/flipkart_q4_logistics.md` (long spec) + `reference.py`.
- **stub.py = the Python harness from the source verbatim** (the `def solve(...)` docstring stub +
  the `main()` reader), with `# WRITE YOUR CODE HERE`. Read `reference.py` for the exact input format
  (6 count lines then the 5 tables) and output format (`Name-LEVEL-score-days` joined by `#`, or `NA`).
- Use BOTH sample inputs/outputs from the source as `tests/sample/01,02`.
- generator: this is a heavy spec problem — a correct random generator is hard. Produce a MODEST one
  that emits a few random shipments/routes/events within the stated constraints; if genuinely
  impractical, omit generator.py (stress will report no_generator). Prioritise correct samples.

### deshaw-q1-music-player  (cpp)
- Source: `_migrated_raw/flipkart_deshaw/deshaw_coding.md` → "Q1 Music Player" + `reference.cpp`.
- Input: `n q`; then the permutation of `1..n`; then `q` lines each `1 u v` (move u before v) or
  `2 k` (print track at 1-indexed position k). Output: one line per type-2 query.
- Sample from source: `5 4 / 3 1 4 5 2 / 2 3 / 1 4 1 / 2 1 / 2 2` → `4`,`3`,`4`.
- generator: random permutation + random mix of move/query ops. Keep n,q ≤ ~10 default.

### deshaw-q2-max-flips  (cpp)
- Source: deshaw_coding.md → "Q2 Max Flips" + `reference.cpp`.
- Input: `n`; then `n` positive integers. Output: one integer (max elements flippable keeping every
  prefix sum strictly > 0). Sample: `5 / 4 1 2 1 3` → `3`.
- generator: random small n, random positive ints (small values by default).

### deshaw-q3-checkerboard-subgrids  (cpp)
- Source: deshaw_coding.md → "Q3 Checkerboard" + `reference.cpp`.
- Input: `n m`; then `n` lines of `m` chars each `0/1`. Output: one integer (count of checkerboard
  subgrids). Samples: `2 2 / 01 / 10` → `9`; a 3×3 checkerboard → `36`.
- generator: random small grid of 0/1.

### millennium-q1-append-reverse  (cpp)
- Source: `_migrated_raw/millennium/millenium_coding.md` → "Q1" + `reference.cpp`.
- Input: one binary string `s`. **Output: the rearranged string s that maximises the final b**
  (unique; the reference prints exactly this — one line). Do NOT ask for b.
- Sample: `0110` → `0101`. Constraint `1 <= |s| <= 10^5`.
- generator: random binary string, small length default.

### millennium-q2-task-walk  (cpp)
- Source: millenium_coding.md → "Q2" + `reference.cpp`.
- Input: `n m`; then `m` lines `u v` (undirected edge, 0-indexed); then `start end k`; then a line of
  `k` task-node ids (may be blank when k=0). Output: shortest walk length start→end visiting all task
  nodes (revisits allowed), or `-1`.
- Sample from source: the 6-node graph → `5`. Constraints `k <= 15`.
- generator: random small connected-ish graph, small k.

### uber-q1-min-penalty-partition  (cpp)
- Source: `_migrated_raw/uber/uber_coding.md` → "Q1" + `reference.cpp`.
- **The judge commits to Reading B** (per-element run penalty; a run of k≥2 costs k*D). State that as
  THE rule in the statement — do not present two readings to the solver.
- Input: `s D Seg` on one line (string, then two integers). Output: one integer (min penalty).
- Sample: `aab 5 3` → `3`; `aaaa 1 10` → `4`. Keep |s| small (DP is O(n²)); set time_ms 2000.
- generator: random short string over a 2–3 letter alphabet + small D, Seg.

### uber-q2-bundling-target  (cpp)
- Source: uber_coding.md → "Q2" + `reference.cpp`.
- Input: `n`; then `n` distinct target values in `1..2n`. Output: `xmin xmax` — the inclusive range of
  feasible min-pick counts (reference prints exactly these two ints). Sample: `3 / 1 3 5` → `1 3`.
- generator: random n, pick n distinct values from 1..2n.

### uber-q3-distinct-flips  (cpp)
- Source: uber_coding.md → "Q3" + `reference.cpp`.
- **Judge commits to: complement one contiguous substring at most once; count distinct results.**
  Answer is `1 + n(n+1)/2`. State that operation as the rule (not reverse, not multiple times).
- Input: one binary string `s`. Output: one integer. Sample: `0110` → `11`.
- generator: random binary string, small length default.
