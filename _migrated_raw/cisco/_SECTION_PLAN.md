# Plan for the authored PDF section: "The OA Survival Kit — from LeetCode logic to real OA harnesses"

Placement: a prominent new section (the user's current #1 priority). Sits well right after Part I
(C++/STL) since it is syntax/I-O heavy, OR as its own front-of-book "Part 0.5". Decide at assembly.

## Hard authoring directives (from the user — obey exactly)
- **Maximally STRUCTURED.** Clear hierarchy: the gap → reading custom input → the harness anatomy →
  per-syntax deep dives → worked OA problems → a reusable template library.
- **Beginner-friendly C++.** Assume the reader can write `class Solution` logic but freezes at I/O/harness
  syntax. Hand-hold.
- **Explain EVERY syntax element, EXHAUSTIVELY.** When a keyword appears (e.g. `static`), do not gloss it —
  give ALL its meanings/uses in C++ (static local var, static global/file linkage, static member, static
  member function, static in a struct), each with a tiny example, then say which meaning the harness uses
  and why. Same treatment for: `struct` vs `class`, references `&` vs pointers `*` vs `->`, `scanf`/`printf`
  format specifiers (`%d %lld %s %c` …), `cin`/`getline`/`>>`, `ios_base::sync_with_stdio(false)` + `cin.tie`,
  `malloc`/`free`/`sizeof`, `vector`/`vector<vector<>>`/`pair`/`make_pair`/`.first`/`.second`,
  `typedef`/`using`, `const`, `size_t`, `(void)D;`, `to_string`, `fputs`/`fwrite`, out-param arrays, `%` modulo.
- **LOADS of real, researched OA examples** (the user said "litter it with examples"): use the two CISCO
  coding questions + their C AND C++ harnesses as the spine, plus the researched scaffolding patterns
  from other companies (De Shaw, Microsoft, Uber, Google, …).

## Content spine
1. **The gap**: LeetCode gives you `class Solution`; OAs give you `main` + `parse_input` + a `struct` + a
   fixed `solve` signature and stdin/stdout. The logic is easy; the wrapping is the wall.
2. **Reading custom input** (the #1 skill): line/token formats, `cin >>` token loop, reading N then N lines,
   grids, reading until EOF, `getline` vs `>>`, mixing them (the trailing-newline trap), `scanf` equivalents.
3. **The harness anatomy**: dissect the CISCO drone + sniper harnesses line by line (both C and C++).
4. **Exhaustive syntax deep-dives** (the `static`-style treatment for every element listed above).
5. **Output formatting**: exact format, `"\n"` vs `endl`, building a string + `fputs`/`fwrite` for speed,
   out-param arrays (the C sniper harness), printing `-1` sentinels.
6. **Worked OA problems** (CISCO Q1 & Q2 fully, then researched analogues): statement → identify the trivial
   logic → fill the harness → verified C++.
7. **A copy-paste template library**: fast I/O header, grid reader, adjacency-list reader, multi-test-case
   loop, the state-BFS template, the sliding-window template.
8. **The conceptual "read-and-fix" style** (from the CISCO sets): how OAs test code-reading and precise
   bug characterisation; the hasPathSum/merge/KV-store/queue examples as worked specimens.

## Sources on disk (this folder)
- `coding.md` (Q1 drone, Q2 sniper — statements, C & C++ harnesses, examples, verified solutions)
- `conceptual_dsa.md`, `conceptual_systems.md` (5 read-and-fix sets + answers)
- `mcq_*.md` (OS/networking/electronics/dsa/aptitude MCQs + answers)
- research digest (to be produced by the agy fan-out) on OA scaffolding across companies
